import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { LogoFaradyne } from './LogoFaradyne';
import { proyectosApi } from '../api/proyectos';
import { authApi } from '../api/auth';
import { getApiErrorMessage } from '../api/apiErrors';
import { TOKEN_KEY, USER_KEY } from '../api/client';
import { Plus, Trash2, FolderOpen, LogOut, ChevronDown, User, Lock, Mail, X, Check, Sun, Moon, Loader2, RefreshCw } from 'lucide-react';

const SLUGS = ['datos', 'plano', 'modelo3d', 'nivel', 'mastiles', 'materiales', 'memoria'];

const ProyectosDashboard = ({ onLogout }) => {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const [proyectos, setProyectos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCuenta, setShowCuenta] = useState(false);
  const [usuario, setUsuario] = useState(() => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; }
  });
  const [cargandoCuenta, setCargandoCuenta] = useState(false);
  const [errorCuenta, setErrorCuenta] = useState(null);

  // cuenta form
  const [nombre, setNombre] = useState(usuario?.nombre || '');
  const [email, setEmail] = useState(usuario?.email || '');
  const [passActual, setPassActual] = useState('');
  const [passNueva, setPassNueva] = useState('');
  const [passConfirm, setPassConfirm] = useState('');
  const [cuentaMsg, setCuentaMsg] = useState(null);
  const [cuentaSaving, setCuentaSaving] = useState(false);

  const [eliminando, setEliminando] = useState(null);

  const cargar = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await proyectosApi.listarProyectos();
      setProyectos(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(getApiErrorMessage(err, 'No se pudieron cargar los proyectos.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { cargar(); }, []);

  const cargarUsuario = useCallback(async () => {
    setCargandoCuenta(true);
    setErrorCuenta(null);
    try {
      const u = await authApi.me();
      setUsuario(u);
      localStorage.setItem(USER_KEY, JSON.stringify(u));
      setNombre(u?.nombre || '');
      setEmail(u?.email || '');
      setPassActual('');
      setPassNueva('');
      setPassConfirm('');
    } catch (err) {
      setErrorCuenta(getApiErrorMessage(err, 'No se pudieron cargar los datos de la cuenta.'));
    } finally {
      setCargandoCuenta(false);
    }
  }, []);

  // refrescar usuario al montar
  useEffect(() => {
    cargarUsuario();
  }, [cargarUsuario]);

  // sincronizar campos cuando cambie el usuario (p. ej. tras guardar)
  useEffect(() => {
    if (usuario) {
      setNombre(usuario.nombre || '');
      setEmail(usuario.email || '');
    }
  }, [usuario]);

  const toggleCuenta = () => {
    setShowCuenta((v) => {
      const next = !v;
      if (next) cargarUsuario();
      return next;
    });
  };

  const abrirProyecto = (p) => {
    const paso = SLUGS[p.ultimo_paso || 0] || 'datos';
    navigate(`/proyecto/${p.id_proyecto}/${paso}`);
  };

  const nuevoProyecto = () => navigate('/proyecto/nuevo/datos');

  const eliminarProyecto = async (id) => {
    if (!window.confirm('¿Está seguro de eliminar este proyecto? Esta acción no se puede deshacer.')) return;
    setEliminando(id);
    try {
      await proyectosApi.eliminarProyecto(id);
      setProyectos((prev) => prev.filter((p) => String(p.id_proyecto) !== String(id)));
    } catch (err) {
      setError(getApiErrorMessage(err, 'No se pudo eliminar el proyecto.'));
    } finally {
      setEliminando(null);
    }
  };

  const guardarCuenta = async (e) => {
    e.preventDefault();
    setCuentaMsg(null);
    if (passNueva && passNueva !== passConfirm) {
      setCuentaMsg({ tipo: 'error', texto: 'Las contraseñas nuevas no coinciden.' });
      return;
    }
    if (passNueva && passNueva.length < 8) {
      setCuentaMsg({ tipo: 'error', texto: 'La contraseña debe tener al menos 8 caracteres.' });
      return;
    }
    setCuentaSaving(true);
    try {
      const payload = {};
      if (nombre && nombre !== usuario?.nombre) payload.nombre = nombre;
      if (email && email !== usuario?.email) payload.email = email;
      if (passNueva) {
        payload.password_actual = passActual;
        payload.password_nueva = passNueva;
      }
      if (Object.keys(payload).length === 0) {
        setCuentaMsg({ tipo: 'info', texto: 'No hay cambios para guardar.' });
        setCuentaSaving(false);
        return;
      }
      const updated = await authApi.updateMe(payload);
      setUsuario(updated);
      localStorage.setItem(USER_KEY, JSON.stringify(updated));
      setPassActual(''); setPassNueva(''); setPassConfirm('');
      setCuentaMsg({ tipo: 'ok', texto: 'Datos actualizados correctamente.' });
    } catch (err) {
      setCuentaMsg({ tipo: 'error', texto: getApiErrorMessage(err, 'No se pudo actualizar la cuenta.') });
    } finally {
      setCuentaSaving(false);
    }
  };

  return (
    <div className={`min-h-screen ${isDark ? 'bg-slate-900 text-slate-100' : 'bg-slate-50 text-gray-900'}`}>
      <header className="bg-brand-dark text-white px-6 py-3 flex items-center justify-between border-b border-slate-800 shadow-md">
        <LogoFaradyne />
        <div className="flex items-center gap-3">
          {/* spacer */}
        </div>
        <div className="relative">
          <button
            type="button"
            onClick={toggleCuenta}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-slate-100 transition text-sm"
          >
            <User className="w-4 h-4" />
            <span className="font-semibold">{usuario?.nombre || 'Cuenta'}</span>
            <ChevronDown className="w-4 h-4" />
          </button>
          {showCuenta && (
            <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-md shadow-lg z-20 p-4 text-gray-900">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800">Mi cuenta</h3>
                <button type="button" onClick={() => setShowCuenta(false)} className="text-gray-400 hover:text-gray-700">
                  <X className="w-4 h-4" />
                </button>
              </div>
              {cargandoCuenta ? (
                <div className="flex items-center gap-2 py-6 justify-center text-gray-500 text-xs">
                  <Loader2 className="w-4 h-4 animate-spin text-brand-blue" />
                  Cargando datos de la cuenta...
                </div>
              ) : errorCuenta ? (
                <div className="space-y-3">
                  <div className="text-xs text-red-600">{errorCuenta}</div>
                  <button
                    type="button"
                    onClick={cargarUsuario}
                    className="w-full px-3 py-2 border border-slate-300 rounded text-xs font-semibold text-gray-700 hover:bg-slate-50 flex items-center justify-center gap-1"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Reintentar
                  </button>
                </div>
              ) : (
              <form onSubmit={guardarCuenta} className="space-y-3">
                <div>
                  <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Nombre</label>
                  <input value={nombre} onChange={(e) => setNombre(e.target.value)} className="w-full p-2 border border-gray-300 rounded text-xs text-gray-900" />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Email</label>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full p-2 border border-gray-300 rounded text-xs text-gray-900" />
                </div>
                <div className="pt-2 border-t border-slate-200">
                  <div className="text-[11px] font-bold text-gray-600 uppercase mb-2">Cambiar contraseña</div>
                  <input type="password" placeholder="Contraseña actual" value={passActual} onChange={(e) => setPassActual(e.target.value)} className="w-full p-2 border border-gray-300 rounded text-xs mb-2 text-gray-900" />
                  <input type="password" placeholder="Nueva contraseña" value={passNueva} onChange={(e) => setPassNueva(e.target.value)} className="w-full p-2 border border-gray-300 rounded text-xs mb-2 text-gray-900" />
                  <input type="password" placeholder="Confirmar nueva" value={passConfirm} onChange={(e) => setPassConfirm(e.target.value)} className="w-full p-2 border border-gray-300 rounded text-xs text-gray-900" />
                </div>
                {cuentaMsg && (
                  <div className={`text-xs ${cuentaMsg.tipo === 'error' ? 'text-red-600' : cuentaMsg.tipo === 'ok' ? 'text-emerald-600' : 'text-gray-600'}`}>
                    {cuentaMsg.texto}
                  </div>
                )}
                <div className="flex gap-2">
                  <button type="submit" disabled={cuentaSaving || cargandoCuenta} className="flex-1 px-3 py-2 bg-brand-blue text-white rounded text-xs font-semibold disabled:opacity-60">
                    {cuentaSaving ? 'Guardando...' : 'Guardar cambios'}
                  </button>
                  <button type="button" onClick={onLogout} className="px-3 py-2 border border-slate-300 rounded text-xs font-semibold text-gray-700 hover:bg-slate-100 flex items-center gap-1">
                    <LogOut className="w-3.5 h-3.5" /> Salir
                  </button>
                </div>
              </form>
              )}
            </div>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold font-condensed text-gray-900">Mis proyectos</h1>
          <button
            type="button"
            onClick={nuevoProyecto}
            className="flex items-center gap-2 px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded text-xs transition"
          >
            <Plus className="w-4 h-4" /> Nuevo proyecto
          </button>
        </div>

        {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-xs">{error}</div>}

        {loading ? (
          <div className="text-xs text-gray-400">Cargando proyectos...</div>
        ) : proyectos.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-md p-8 text-center text-gray-500 text-sm">
            No tenés proyectos todavía. Creá uno nuevo para comenzar.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {proyectos.map((p) => (
              <div key={p.id_proyecto} className="bg-white border border-slate-200 rounded-md p-4 shadow-sm flex flex-col gap-3">
                <div>
                  <h3 className="font-bold text-gray-800 text-sm truncate">{p.nombre}</h3>
                  <p className="text-[11px] text-gray-500 truncate">{p.cliente || '—'} · {p.ubicacion || '—'}</p>
                  <p className="text-[10px] text-gray-400 mt-1">Estado: {p.estado || 'borrador'}</p>
                </div>
                <div className="flex gap-2 mt-auto">
                  <button
                    type="button"
                    onClick={() => abrirProyecto(p)}
                    className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-blue text-white rounded text-xs font-semibold hover:bg-brand-hover transition"
                  >
                    <FolderOpen className="w-3.5 h-3.5" /> Abrir
                  </button>
                  <button
                    type="button"
                    onClick={() => eliminarProyecto(p.id_proyecto)}
                    disabled={eliminando === p.id_proyecto}
                    className="px-3 py-2 border border-red-200 text-red-600 rounded text-xs font-semibold hover:bg-red-50 transition disabled:opacity-60"
                    title="Eliminar proyecto"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <button
        type="button"
        onClick={toggle}
        className="theme-toggle fixed bottom-5 right-5 z-50 flex h-11 w-11 items-center justify-center rounded-full text-xs font-bold shadow-lg transition"
        aria-label={isDark ? 'Activar modo claro' : 'Activar modo nocturno'}
        title={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo nocturno'}
      >
        {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      </button>
    </div>
  );
};

const ZapIcon = () => (
  <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white">
    <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
  </svg>
);

export default ProyectosDashboard;
export { ProyectosDashboard };