/**
 * MemoriaDescriptiva.jsx — Paso 7 del flujo FARADYNE
 *
 * Vista previa de la Memoria Descriptiva SPDA según Ley 19.587 / Decreto 351/79
 * e IRAM 2184. Muestra en orden:
 *   1. Datos del proyecto
 *   2. Nivel de protección y zona ceráunica
 *   3. Plano base 2D con mástiles (imagen de GeometriaViewerMastiles)
 *   4. Vistas 3D a elección: isométrica, caballera, militar, frontal, planta y lateral
 *      (imágenes de Modelo3DViewer)
 *   5. Cobertura SPDA: totales, cubiertas, ternas sin esfera
 *   6. Listado de materiales
 *
 * Lógica de captura de imágenes:
 *   - Los visores se montan off-screen (position:absolute, left muy negativo).
 *   - Se espera onReady de cada visor, se captura con capturarVista / capturarImagen
 *     y se desmonta. Si falla una captura, se muestra "Imagen no disponible".
 *   - NO se usa display:none porque el canvas 3D necesita ancho > 0.
 *
 * Se capturan TODAS las vistas una sola vez; el usuario elige cuáles se insertan en el PDF
 * (la elección se recuerda en el navegador) y solo esas viajan al backend.
 *
 * TODOS los datos vienen del endpoint GET /memorias/proyecto/{id}/vista-previa.
 * No se recalcula ni se inventan valores.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  CheckCircle2, CloudUpload, Download, Loader2, AlertTriangle, RefreshCw,
  FileText, Shield, Map, Box, Package, ChevronDown, ChevronUp, CheckSquare, Square, Image as ImageIcon,
} from 'lucide-react';
import { memoriasApi } from '../api/memorias';
import { GeometriaViewerMastiles } from '../components/GeometriaViewerMastiles/GeometriaViewerMastiles';
import { Modelo3DViewer } from '../components/Modelo3DViewer/Modelo3DViewer';
import { VISTAS_CAPTURA } from '../components/Modelo3DViewer/vistasTecnicas';

// ──────────────────────────────────────────────────────────────────────────────
// HELPERS
// ──────────────────────────────────────────────────────────────────────────────

const fmt = (v, d = 2) => (v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—');
const fmtPct = (v) => (v != null && Number.isFinite(Number(v)) ? `${Number(v).toFixed(2)} %` : '—');
const fmtDate = (v) => {
  if (!v) return 'No disponible';
  try { return new Date(v).toLocaleDateString('es-AR'); } catch { return String(v); }
};
const nvl = (v, fallback = 'No disponible') => (v != null && v !== '' ? v : fallback);

const ESTADO_PRISMA = {
  protegido:    { label: 'Protegido',    cls: 'text-emerald-700', dot: 'bg-emerald-500' },
  parcial:      { label: 'Parcial',      cls: 'text-amber-700',   dot: 'bg-amber-500'   },
  desprotegido: { label: 'Desprotegido', cls: 'text-red-700',     dot: 'bg-red-500'     },
};

const NIVEL_LABELS = { 'I+': 'Nivel I+', I: 'Nivel I', II: 'Nivel II', III: 'Nivel III', IV: 'Nivel IV' };

// ──────────────────────────────────────────────────────────────────────────────
// CÁLCULO DEL NIVEL DE PROTECCIÓN (mismas fórmulas que la pantalla «Nivel de Protección»)
// ──────────────────────────────────────────────────────────────────────────────

// Anexo E (Tablas E.1 a E.5): criterio que corresponde a cada valor de factor.
const FACTORES_ANEXO_E = [
  { k: 'a', nombre: 'A · Ocupación', tabla: 'E.1', opciones: {
    0.3: 'Casas u otras estructuras de porte equivalente', 0.7: 'Casas con antena exterior',
    1.0: 'Fábricas, oficinas y laboratorios', 1.2: 'Oficinas, hoteles, departamentos, residenciales',
    1.3: 'Locales de afluencia de público', 1.7: 'Escuelas, hospitales, actividades múltiples' } },
  { k: 'b', nombre: 'B · Construcción', tabla: 'E.2', opciones: {
    0.2: 'Acero recubierto, cubierta no metálica', 0.4: 'Hormigón armado, cubierta no metálica',
    0.8: 'Acero u hormigón armado con cubierta metálica',
    1.0: 'Mampostería o concreto simple, sin cubierta metálica ni paja',
    1.7: 'Madera, mampostería o concreto simple, con cubierta metálica',
    2.0: 'Cualquier estructura con techo de paja' } },
  { k: 'c', nombre: 'C · Contenido', tabla: 'E.3', opciones: {
    0.3: 'Residencias, oficinas, fábricas sin objetos de valor', 0.8: 'Industrial o agrícola con objetos de valor',
    1.0: 'Subestaciones, centrales, telefónicas, radio', 1.3: 'Industrias estratégicas, museos, monumentos',
    1.7: 'Escuelas, hospitales, guarderías, afluencia pública' } },
  { k: 'd', nombre: 'D · Localización', tabla: 'E.4', opciones: {
    0.4: 'Área con estructuras o árboles iguales o más altos', 1.0: 'Área con pocas estructuras de altura similar',
    2.0: 'Estructura aislada o mucho más alta que su entorno' } },
  { k: 'e', nombre: 'E · Topografía', tabla: 'E.5', opciones: {
    0.3: 'Planicie', 1.0: 'Elevaciones moderadas, colinas', 1.3: 'Montañas de 300 a 900 m', 1.7: 'Montañas de más de 900 m' } },
];

const aNum = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);

const criterioFactor = (opciones, v) => {
  if (v == null) return 'No disponible';
  const clave = Object.keys(opciones).find((o) => Math.abs(Number(o) - v) < 1e-9);
  return clave !== undefined ? opciones[clave] : 'Valor fuera de tabla';
};

/** Factores A–E guardados con el nivel: {factores|factores_riesgo|factor_a_e: {a..e}} o columnas factor_a … factor_e. */
const leerFactores = (nivel) => {
  const crudo = nivel.factores || nivel.factores_riesgo || nivel.factor_a_e || {};
  return Object.fromEntries(['a', 'b', 'c', 'd', 'e'].map((k) => [k, aNum(crudo[k] ?? crudo[`factor_${k}`] ?? nivel[`factor_${k}`])]));
};

const PasoHeader = ({ numero, titulo, colorClass = 'bg-brand-blue' }) => (
  <div className="flex items-center gap-2 mb-2">
    <div className={`w-5 h-5 rounded-full ${colorClass} text-white text-[10px] font-bold flex items-center justify-center shrink-0`}>
      {numero}
    </div>
    <h3 className="text-[11px] font-bold text-gray-700 uppercase tracking-wide">{titulo}</h3>
  </div>
);

/** Fórmula → reemplazo de valores → resultado */
const CajaFormula = ({ formula, reemplazo, resultado, unidad, colorClass = 'text-brand-blue' }) => (
  <div className="bg-slate-50 border border-slate-200 rounded-md p-3 space-y-1.5 font-mono">
    <div className="text-[10px] text-gray-500 uppercase tracking-wide font-sans font-semibold">Fórmula (Anexo)</div>
    <div className="text-xs text-gray-700">{formula}</div>
    <div className="text-[10px] text-gray-500 uppercase tracking-wide font-sans font-semibold pt-1">Reemplazo de valores</div>
    <div className="text-xs text-gray-700 break-words">{reemplazo}</div>
    <div className="flex items-baseline gap-2 pt-2 border-t border-slate-200">
      <span className="text-[10px] text-gray-500 uppercase font-sans font-semibold">Resultado</span>
      <span className={`text-base font-bold font-condensed ${colorClass}`}>
        {resultado} <span className="text-xs font-normal">{unidad}</span>
      </span>
    </div>
  </div>
);

const SeccionNivel = ({ nivel }) => {
  const zona = nivel.zona_ceraunica || {};
  const fac = leerFactores(nivel);
  const l = aNum(nivel.longitud_edificacion);
  const w = aNum(nivel.anchura_edificacion);
  const h = aNum(nivel.altura_edificacion);
  const ng = aNum(zona.ng ?? nivel.densidad_ng);
  const ae = aNum(nivel.ae);
  const nd = aNum(nivel.nd);
  const nc = aNum(nivel.nc);
  const ef = aNum(nivel.eficiencia_minima);
  const npCalc = nivel.nivel_proteccion;
  const npRec = nivel.nivel_proteccion_recomendado;

  const m = aNum(nivel.margen_lateral);
  const margen1 = m != null ? Math.round(m) === 1 : (h != null && h >= 11 && h <= 60);
  const requiere = nd != null && nc != null ? nd > nc : Boolean(ef);
  const eVal = ef ?? (requiere && nd ? 1 - nc / nd : null);

  const formulaAe = margen1 ? 'Ae = L·W + 2H·(L+W) + π·H²' : 'Ae = L·W + 6H·(L+W) + 9·π·H²';
  const reemplazoAe = margen1
    ? `Ae = ${fmt(l)}·${fmt(w)} + 2·${fmt(h)}·(${fmt(l)}+${fmt(w)}) + π·${fmt(h)}²`
    : `Ae = ${fmt(l)}·${fmt(w)} + 6·${fmt(h)}·(${fmt(l)}+${fmt(w)}) + 9·π·${fmt(h)}²`;
  const justAe = margen1
    ? `Margen lateral H=1 porque la altura de la estructura (H = ${fmt(h)} m) está en el rango 11 m ≤ H ≤ 60 m (Fig. B.4; Anexo G, AEA 92305-11).`
    : `Margen lateral H=3 porque la altura de la estructura (H = ${fmt(h)} m) está en el rango 2 m ≤ H ≤ 10 m (Fig. B.1; Anexo G, AEA 92305-11).`;

  const thCls = 'p-2 text-left font-bold text-gray-700';
  return (
    <div className="space-y-4">
      {/* Fichas resumen */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ['Nivel adoptado', NIVEL_LABELS[npCalc] || nvl(npCalc)],
          ['Nivel recomendado', NIVEL_LABELS[npRec] || nvl(npRec)],
          ['Radio esfera rodante', `R = ${fmt(nivel.radio_esfera, 0)} m`],
        ].map(([rotulo, valor]) => (
          <div key={rotulo} className="p-3 bg-blue-50 border-l-4 border-brand-blue rounded">
            <div className="text-[10px] text-brand-blue font-bold uppercase">{rotulo}</div>
            <div className="text-lg font-bold font-condensed text-slate-900">{valor}</div>
          </div>
        ))}
      </div>

      {/* Datos de partida */}
      <div>
        <PasoHeader numero={1} titulo="Zona y datos identificados del proyecto" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
          {[
            ['Zona ceráunica', [zona.nombre, zona.ciudad].filter(Boolean).join(', ') || 'No disponible', 'text-xs leading-tight mt-1'],
            ['Ng adoptado', fmt(ng), 'text-lg'],
            ['Longitud (L)', l != null ? `${fmt(l)} m` : '—', 'text-lg'],
            ['Anchura (W)', w != null ? `${fmt(w)} m` : '—', 'text-lg'],
            ['Altura (H)', h != null ? `${fmt(h)} m` : '—', 'text-lg'],
          ].map(([rotulo, valor, cls]) => (
            <div key={rotulo} className="p-2 bg-slate-50 border border-slate-200 rounded flex flex-col justify-center">
              <div className="text-[10px] text-gray-500 uppercase">{rotulo}</div>
              <div className={`font-bold text-brand-blue ${cls}`}>{valor}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Factores elegidos */}
      <div>
        <PasoHeader numero={2} titulo="Factores de riesgo elegidos — Anexo E" />
        <table className="w-full text-xs border-collapse border-t-2 border-b-2 border-gray-800">
          <thead>
            <tr className="border-b border-gray-800">
              <th className={thCls}>Factor</th>
              <th className={thCls}>Criterio adoptado</th>
              <th className="p-2 text-center font-bold text-gray-700">Tabla</th>
              <th className="p-2 text-right font-bold text-gray-700">Valor</th>
            </tr>
          </thead>
          <tbody>
            {FACTORES_ANEXO_E.map(({ k, nombre, tabla, opciones }) => (
              <tr key={k}>
                <td className="p-2 text-gray-700">{nombre}</td>
                <td className="p-2 text-gray-800">{criterioFactor(opciones, fac[k])}</td>
                <td className="p-2 text-center font-mono text-gray-500">{tabla}</td>
                <td className="p-2 text-right font-mono font-semibold">{fmt(fac[k], 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Ae */}
      <div>
        <PasoHeader numero={3} titulo="Área colectora equivalente (Ae) — Anexo B" colorClass="bg-indigo-600" />
        <CajaFormula formula={formulaAe} reemplazo={reemplazoAe} resultado={fmt(ae)} unidad="m²" colorClass="text-indigo-700" />
        <p className="mt-1.5 text-[11px] text-gray-500">{justAe}</p>
      </div>

      {/* Nd */}
      <div>
        <PasoHeader numero={4} titulo="Frecuencia esperable de descargas directas (Nd) — Anexo D" colorClass="bg-sky-600" />
        <CajaFormula
          formula="Nd = Ng · Ae · 10⁻⁶  [descargas directas/año]"
          reemplazo={`Nd = ${fmt(ng)} · ${fmt(ae)} · 10⁻⁶`}
          resultado={fmt(nd)}
          unidad="descargas directas/año"
          colorClass="text-sky-700"
        />
      </div>

      {/* Nc */}
      <div>
        <PasoHeader numero={5} titulo="Frecuencia aceptable corregida (Nc) — Anexo E" colorClass="bg-amber-600" />
        <CajaFormula
          formula="Nc = (A · B · C · D · E) · Nd"
          reemplazo={`Nc = (${['a', 'b', 'c', 'd', 'e'].map((k) => fmt(fac[k], 1)).join(' · ')}) · ${fmt(nd)}`}
          resultado={fmt(nc)}
          unidad="descargas/año"
          colorClass="text-amber-700"
        />
      </div>

      {/* Criterio F.1 */}
      <div>
        <PasoHeader numero={6} titulo="Criterio F.1 — Nivel de protección" colorClass="bg-emerald-600" />
        <div className="grid grid-cols-2 gap-3 mb-2">
          <div className="p-2 bg-slate-50 border border-slate-200 rounded text-center">
            <div className="text-[10px] text-gray-500 uppercase">Nd (impactos directos)</div>
            <div className="text-sm font-bold text-gray-800">{fmt(nd)}</div>
          </div>
          <div className="p-2 bg-slate-50 border border-slate-200 rounded text-center">
            <div className="text-[10px] text-gray-500 uppercase">Nc (frec. aceptable)</div>
            <div className="text-sm font-bold text-gray-800">{fmt(nc)}</div>
          </div>
        </div>
        <div className={`p-3 rounded-md border text-[11px] ${requiere ? 'bg-amber-50 border-amber-200 text-amber-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'}`}>
          <div className="text-xs font-bold uppercase">
            {requiere ? 'Se requiere SPCR (Nd > Nc)' : 'No se requiere SPCR obligatorio (Nd ≤ Nc)'}
          </div>
          {requiere && (
            <div className="mt-1">
              Eficiencia requerida: <strong>E = 1 − (Nc/Nd) = {fmt(eVal)}</strong> → Tabla F.1
            </div>
          )}
          <div className="mt-1.5">
            Nivel recomendado: <strong>{NIVEL_LABELS[npRec] || nvl(npRec)}</strong>
            {' · '}Nivel adoptado: <strong>{NIVEL_LABELS[npCalc] || nvl(npCalc)}</strong>
          </div>
        </div>
      </div>
    </div>
  );
};


// ──────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTES DE LAYOUT
// ──────────────────────────────────────────────────────────────────────────────

/** Sección A4 con título e hijo */
const Seccion = ({ id, numero, titulo, icon: Icon, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section id={id} className="mb-6 break-inside-avoid">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 mb-3 text-left group"
      >
        <span className="flex items-center justify-center w-6 h-6 rounded-full bg-brand-blue text-white text-[10px] font-bold shrink-0">
          {numero}
        </span>
        {Icon && <Icon className="w-4 h-4 text-brand-blue shrink-0" />}
        <h2 className="flex-1 text-xs font-bold uppercase tracking-wider text-brand-blue">
          {titulo}
        </h2>
        {open ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
      </button>
      {open && <div className="pl-8">{children}</div>}
    </section>
  );
};

/** Fila de dato simple */
const Dato = ({ label, value }) => (
  <div className="flex items-baseline gap-1 min-w-0">
    <span className="text-gray-500 shrink-0">{label}:</span>
    <span className="font-medium text-gray-800 break-words">{nvl(value)}</span>
  </div>
);

/** Imagen capturada, con estados "generando" y "no disponible" (con reintento) */
const ImagenCaptura = ({ src, alt, cargando = false, onRetry = null, className = '' }) => {
  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        className={`rounded border border-gray-200 w-full object-contain bg-white ${className}`}
      />
    );
  }
  return (
    <div className={`flex items-center justify-center bg-slate-50 border border-dashed border-gray-300 rounded text-xs text-gray-400 ${className}`}>
      <div className="text-center p-4">
        {cargando ? (
          <>
            <Loader2 className="w-6 h-6 mx-auto mb-1 animate-spin text-brand-blue" />
            Generando imagen...
          </>
        ) : (
          <>
            <AlertTriangle className="w-6 h-6 mx-auto mb-1 text-gray-300" />
            Imagen no disponible
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-2 mx-auto flex items-center gap-1 px-2 py-1 border border-gray-300 rounded text-[11px] text-gray-600 hover:bg-white"
              >
                <RefreshCw className="w-3 h-3" /> Reintentar
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// CAPTURA DE IMÁGENES (visores montados off-screen)
// ──────────────────────────────────────────────────────────────────────────────

/** Texto de error seguro para React: `detail` puede ser un string (HTTPException) o un arreglo (422 de Pydantic). */
const mensajeError = (err, porDefecto) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => d?.msg).filter(Boolean).join(' · ');
    if (msgs) return msgs;
  }
  return porDefecto;
};

const CAPTURA_2D = { width: 1100, height: 700 };
const CAPTURA_3D = { width: 1400, height: 900 };
const TIMEOUT_CAPTURA_MS = 30000;
const SIN_MASTILES = [];

// Imágenes que se pueden insertar en el PDF: el plano 2D y cada vista del modelo 3D.
const OPCIONES_IMAGEN = [
  { key: 'plano', label: 'Plano 2D', detalle: 'Plano base con los mástiles colocados' },
  ...VISTAS_CAPTURA.map((v) => ({ ...v, label: `3D · ${v.label}` })),
];
const CLAVES_IMAGEN = OPCIONES_IMAGEN.map((o) => o.key);
const SIN_CAPTURAS = Object.fromEntries(CLAVES_IMAGEN.map((k) => [k, null]));

const CACHE_CAPTURAS_KEY = (id) => `memoriaCapturas:${id}`;
const leerCacheCapturas = (id) => {
  try {
    const raw = sessionStorage.getItem(CACHE_CAPTURAS_KEY(id));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || !parsed.capturas) return null;
    return parsed;
  } catch {
    return null;
  }
};
const escribirCacheCapturas = (id, capturas) => {
  try {
    sessionStorage.setItem(CACHE_CAPTURAS_KEY(id), JSON.stringify({ capturas, ts: Date.now() }));
  } catch {
    /* ignore */
  }
};

// Selección inicial: lo que llevaba la memoria antes (plano + isométrica + frontal).
const SELECCION_INICIAL = {
  plano: true, iso: true, iso_der: false, caballera: false, militar: false, front: true, top: false, side: false,
};
const CLAVE_STORAGE_SELECCION = 'faradyne_memoria_imagenes';

// localStorage puede no estar disponible (ventana privada, datos bloqueados): se envuelve en try/catch.
const leerSeleccion = () => {
  try {
    const raw = localStorage.getItem(CLAVE_STORAGE_SELECCION);
    if (raw) return { ...SELECCION_INICIAL, ...JSON.parse(raw) };
  } catch { /* se usa la selección inicial */ }
  return SELECCION_INICIAL;
};

/** Panel para elegir qué imágenes se insertan en el PDF (miniaturas con casilla). */
const SelectorImagenes = ({ capturas, seleccion, onToggle, onTodas, onNinguna, cargando, onRetry }) => {
  const elegidas = CLAVES_IMAGEN.filter((k) => seleccion[k] && capturas[k]).length;
  return (
    <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ImageIcon className="w-4 h-4 text-brand-blue" />
          <span className="text-xs font-bold uppercase text-gray-700">Imágenes del PDF</span>
          <span className="text-[11px] text-gray-500">
            {cargando ? 'Generando vistas...' : `${elegidas} seleccionada${elegidas === 1 ? '' : 's'}`}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px]">
          <button type="button" onClick={onTodas} className="px-2 py-1 border border-gray-300 rounded text-gray-600 hover:bg-gray-50">
            Todas
          </button>
          <button type="button" onClick={onNinguna} className="px-2 py-1 border border-gray-300 rounded text-gray-600 hover:bg-gray-50">
            Ninguna
          </button>
          {!cargando && (
            <button type="button" onClick={onRetry} className="px-2 py-1 border border-gray-300 rounded text-gray-600 hover:bg-gray-50 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Volver a generar
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2">
        {OPCIONES_IMAGEN.map(({ key, label, detalle }) => {
          const src = capturas[key];
          const marcada = Boolean(seleccion[key]);
          const Casilla = marcada ? CheckSquare : Square;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onToggle(key)}
              title={detalle}
              className={`text-left rounded border p-1.5 space-y-1 transition ${
                marcada ? 'border-brand-blue bg-blue-50/60' : 'border-gray-200 bg-white hover:bg-slate-50'
              }`}
            >
              <div className="aspect-[14/9] bg-slate-100 rounded overflow-hidden flex items-center justify-center">
                {src ? (
                  <img src={src} alt={label} className="w-full h-full object-contain bg-white" />
                ) : cargando ? (
                  <Loader2 className="w-4 h-4 animate-spin text-brand-blue" />
                ) : (
                  <span className="text-[10px] text-gray-400">No disponible</span>
                )}
              </div>
              <div className="flex items-center gap-1 text-[11px] font-medium text-gray-800">
                <Casilla className={`w-3.5 h-3.5 shrink-0 ${marcada ? 'text-brand-blue' : 'text-gray-400'}`} />
                <span className="truncate">{label}</span>
              </div>
            </button>
          );
        })}
      </div>
      <p className="text-[10px] text-gray-500">
        Se insertan en el PDF en este orden: primero el plano 2D y después las vistas 3D elegidas.
      </p>
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// PÁGINA PRINCIPAL
// ──────────────────────────────────────────────────────────────────────────────

export const MemoriaDescriptiva = ({ projectData, idProyecto, idModelo2D, idModelo3D }) => {
  const [generating, setGenerating] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [error, setError] = useState(null);
  const [datos, setDatos] = useState(null); // respuesta de vista-previa

  // ── Captura de imágenes (secciones 3 y 4) ───────────────────────────────────
  const ref2d = useRef(null);
  const ref3d = useRef(null);
  const [fase, setFase] = useState('idle');          // 'idle' | 'capturando' | 'listo'
  const [estado2d, setEstado2d] = useState('espera'); // 'espera' | 'ok' | 'error'
  const [estado3d, setEstado3d] = useState('espera');
  const [capturado2d, setCapturado2d] = useState(false);
  const [capturado3d, setCapturado3d] = useState(false);
  const [capturas, setCapturas] = useState(SIN_CAPTURAS);
  const [seleccion, setSeleccion] = useState(leerSeleccion);

  // ── Carga de datos ──────────────────────────────────────────────────────────

  const cargarVistaPrevia = useCallback(async () => {
    if (!idProyecto) return;
    setLoadingPreview(true);
    setError(null);
    try {
      const data = await memoriasApi.vistaPrevia(idProyecto);
      setDatos(data);
    } catch (err) {
      setError(mensajeError(err, 'No se pudieron cargar los datos de la memoria descriptiva.'));
    } finally {
      setLoadingPreview(false);
    }
  }, [idProyecto]);

  useEffect(() => {
    cargarVistaPrevia();
  }, [cargarVistaPrevia]);

  // ── Captura automática de plano 2D y vistas 3D ──────────────────────────────

  const iniciarCaptura = useCallback((d) => {
    const hay2d = Boolean(d?.ids?.id_modelo2d);
    const hay3d = Boolean(d?.ids?.id_modelo3d);
    setCapturas(SIN_CAPTURAS);
    setCapturado2d(!hay2d);
    setCapturado3d(!hay3d);
    if (!hay2d && !hay3d) {
      setFase('listo');
      return;
    }
    setEstado2d(hay2d ? 'espera' : 'error');
    setEstado3d(hay3d ? 'espera' : 'error');
    setFase('capturando');
  }, []);

  // Al llegar los datos arranca la captura.
  useEffect(() => {
    if (!datos) return;
    const cache = leerCacheCapturas(idProyecto);
    if (cache?.capturas) {
      setCapturas(cache.capturas);
      setFase('listo');
      setCapturado2d(true);
      setCapturado3d(true);
    } else {
      iniciarCaptura(datos);
    }
  }, [datos, iniciarCaptura, idProyecto]);

  // Captura independiente del plano 2D apenas esté listo (no espera al 3D).
  useEffect(() => {
    if (fase !== 'capturando' || capturado2d) return undefined;
    if (estado2d === 'espera') return undefined;

    const t = setTimeout(() => {
      setCapturas((prev) => {
        const nuevas = { ...prev };
        if (estado2d === 'ok') {
          try {
            nuevas.plano = ref2d.current?.capturarImagen({ pixelRatio: 2 }) || null;
          } catch (err) {
            console.error('[Memoria] Falló la captura del plano 2D:', err);
          }
        }
        return nuevas;
      });
      setCapturado2d(true);
    }, 100);

    return () => clearTimeout(t);
  }, [fase, estado2d, capturado2d]);

  // Captura independiente de las vistas 3D apenas esté listo (no espera al 2D).
  useEffect(() => {
    if (fase !== 'capturando' || capturado3d) return undefined;
    if (estado3d === 'espera') return undefined;

    let cancelled = false;
    const run = async () => {
      await new Promise((r) => setTimeout(r, 100));
      if (cancelled) return;
      const nuevas = {};
      if (estado3d === 'ok') {
        for (const { key } of VISTAS_CAPTURA) {
          await new Promise((r) => setTimeout(r, 16));
          if (cancelled) return;
          try {
            nuevas[key] = ref3d.current?.capturarVista(key, CAPTURA_3D) || null;
          } catch (err) {
            console.error(`[Memoria] Falló la captura 3D (${key}):`, err);
            nuevas[key] = null;
          }
          setCapturas((prev) => ({ ...prev, ...nuevas }));
        }
      }
      setCapturado3d(true);
    };
    run();
    return () => { cancelled = true; };
  }, [fase, estado3d, capturado3d]);

  // Cuando ambas capturas terminaron, desmontar los visores.
  useEffect(() => {
    if (fase !== 'capturando') return undefined;
    if (!capturado2d || !capturado3d) return undefined;
    const t = setTimeout(() => setFase('listo'), 50);
    return () => clearTimeout(t);
  }, [fase, capturado2d, capturado3d]);

  // Persistir capturas en sessionStorage para que aparezcan en la vista previa
  // aunque se recargue la página.
  useEffect(() => {
    if (fase === 'listo' && capturas && Object.values(capturas).some(Boolean)) {
      escribirCacheCapturas(idProyecto, capturas);
    }
  }, [fase, capturas, idProyecto]);

  // Si un visor no avisa a tiempo, se abandona: queda "Imagen no disponible".
  useEffect(() => {
    if (fase !== 'capturando') return undefined;
    const t = setTimeout(() => {
      setEstado2d((e) => (e === 'espera' ? 'error' : e));
      setEstado3d((e) => (e === 'espera' ? 'error' : e));
    }, TIMEOUT_CAPTURA_MS);
    return () => clearTimeout(t);
  }, [fase]);

  const reintentarCapturas = () => iniciarCaptura(datos);

  useEffect(() => {
    try {
      localStorage.setItem(CLAVE_STORAGE_SELECCION, JSON.stringify(seleccion));
    } catch { /* sin almacenamiento: la elección vale solo para esta sesión */ }
  }, [seleccion]);

  const alternarImagen = (clave) => setSeleccion((s) => ({ ...s, [clave]: !s[clave] }));
  const elegirTodas = () => setSeleccion(Object.fromEntries(CLAVES_IMAGEN.map((k) => [k, true])));
  const elegirNinguna = () => setSeleccion(Object.fromEntries(CLAVES_IMAGEN.map((k) => [k, false])));

  // Imágenes elegidas y disponibles, en el orden del documento (plano y luego vistas 3D).
  const imagenesPdf = CLAVES_IMAGEN.filter((k) => seleccion[k] && capturas[k]);
  const vistas3dElegidas = VISTAS_CAPTURA.filter((v) => seleccion[v.key]);

  // ── Generar y descargar PDF (flujo anterior, sin cambios) ───────────────────

  const generarYDescargar = async () => {
    if (!idProyecto) return;
    setGenerating(true); setError(null);
    try {
      await memoriasApi.generar(idProyecto, {
        declaracion_decreto_351_79: true,
        imagenes: imagenesPdf.map((clave) => ({ clave, data_url: capturas[clave] })),
      });
      const pdf = await memoriasApi.descargar(idProyecto);
      const url = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url; link.download = `memoria-proyecto-${idProyecto}.pdf`; link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(mensajeError(err, 'No se pudo generar la memoria descriptiva.'));
    } finally { setGenerating(false); }
  };

  // ── Derivados ───────────────────────────────────────────────────────────────

  const proyecto  = datos?.proyecto        || {};
  const nivel     = datos?.nivel_proteccion || null;
  const cobertura = datos?.cobertura        || null;
  const materiales = datos?.materiales      || [];
  const totalMastilesMat = datos?.total_mastiles_materiales || 0;

  const prismas = cobertura?.prismas || [];
  const ternas  = cobertura?.triangulos_sin_esfera || [];

  // Resumen de cubiertas
  const totalCubiertas = prismas.length;
  const cubProtegidas  = prismas.filter(p => p.estado === 'protegido').length;
  const cubDesproteg   = prismas.filter(p => p.estado === 'desprotegido').length;
  const cubParciales   = prismas.filter(p => p.estado === 'parcial').length;

  // Zonas desprotegidas: área total
  const zonasDesp = cobertura?.zonas_desprotegidas || [];
  const areaDesp  = zonasDesp.reduce((sum, z) => sum + (Number(z.area_m2 ?? z.area ?? 0)), 0);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="w-full space-y-4 px-3">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Memoria Descriptiva &amp; Documento Final
      </h1>

      {/* Aviso paso */}
      <div className="workflow-notice p-3 bg-emerald-50/95 border border-emerald-200 text-emerald-800 rounded-md flex items-center gap-2 text-xs">
        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        <div>
          <strong>Paso 7 de 7 (FINAL):</strong> Vista previa de la Memoria Descriptiva
          según Ley 19.587 / Decreto 351/79 e IRAM 2184.
        </div>
      </div>

      {/* Estado de carga */}
      {loadingPreview && (
        <div className="flex items-center gap-2 py-10 justify-center text-slate-500 text-sm">
          <Loader2 className="w-5 h-5 animate-spin text-brand-blue" />
          Cargando datos de la memoria...
        </div>
      )}

      {/* Error global */}
      {error && !loadingPreview && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}


      {/* ── Documento A4 ─────────────────────────────────────────────────────── */}
      {!loadingPreview && datos && (
        <div
          id="memoria-documento"
          className="bg-white border border-gray-300 rounded-lg shadow-lg overflow-hidden print:shadow-none print:border-none"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          {/* Encabezado del documento */}
          <div className="bg-gradient-to-r from-slate-900 to-brand-blue p-5 text-white flex justify-between items-start gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-blue-200 font-semibold">
                Memoria Descriptiva
              </div>
              <div className="text-lg font-bold font-condensed">
                Sistema de Protección contra Rayos (SPDA)
              </div>
              <div className="text-xs text-blue-100 mt-0.5">
                Decreto 351/79 · Ley 19.587 · IRAM 2184
              </div>
            </div>
            <div className="bg-white/10 backdrop-blur px-3 py-2 rounded text-right border border-white/20 shrink-0">
              <div className="text-[9px] text-blue-200 uppercase">Proyecto N°</div>
              <div className="text-sm font-bold font-mono">{nvl(proyecto.id_proyecto)}</div>
            </div>
          </div>

          {/* Cuerpo del documento */}
          <div className="p-6 space-y-1 text-xs text-gray-800 leading-relaxed">

            {/* ── SECCIÓN 1: Datos del proyecto ─────────────────────────────── */}
            <Seccion id="sec-proyecto" numero="1" titulo="Datos del Proyecto" icon={FileText}>
              <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 bg-slate-50 p-3 rounded border border-gray-100">
                <Dato label="Nombre del proyecto"   value={proyecto.nombre} />
                <Dato label="Cliente"               value={proyecto.cliente} />
                <Dato label="Proyectista"            value={proyecto.proyectista} />
                <Dato label="Estado"                 value={proyecto.estado} />
                <Dato label="Ubicación"              value={proyecto.ubicacion} />
                <Dato label="Departamento"           value={proyecto.departamento} />
                <Dato label="Provincia"              value={proyecto.provincia} />
                <Dato label="Localidad"              value={proyecto.localidad} />
                <Dato label="Fecha del proyecto"     value={fmtDate(proyecto.fecha_del_proyecto)} />
                <Dato label="Fecha de creación"      value={fmtDate(proyecto.fecha_creacion)} />
                {proyecto.descripcion && (
                  <div className="col-span-2 mt-1">
                    <span className="text-gray-500">Descripción:</span>{' '}
                    <span className="font-medium text-gray-800">{proyecto.descripcion}</span>
                  </div>
                )}
              </div>
            </Seccion>

            <hr className="border-gray-100 my-4" />

            {/* ── SECCIÓN 2: Nivel de protección ───────────────────────────── */}
            <Seccion id="sec-nivel" numero="2" titulo="Cálculo del Nivel de Protección" icon={Shield}>
              {!nivel ? (
                <p className="text-gray-400 italic text-xs">
                  No se encontró un cálculo de nivel de protección para este proyecto.
                </p>
              ) : (
                <SeccionNivel nivel={nivel} />
              )}
            </Seccion>

            <hr className="border-gray-100 my-4" />

            {/* ── SECCIÓN 3: Modelo 2D ─────────────────────────────────────── */}
            <Seccion id="sec-2d" numero="3" titulo="Plano Base 2D con Mástiles" icon={Map}>
              <div className="space-y-2">
                <p className="text-gray-500 text-[11px]">
                  Plano con la geometría validada y los {datos.mastiles?.length ?? 0} mástiles
                  captores ubicados (Modelo 2D ID: {nvl(datos.ids?.id_modelo2d)}).
                </p>
                {seleccion.plano ? (
                  <ImagenCaptura
                    src={capturas.plano}
                    alt="Plano 2D con los mástiles colocados"
                    cargando={fase === 'capturando'}
                    onRetry={reintentarCapturas}
                    className="aspect-[1100/700]"
                  />
                ) : (
                  <p className="text-gray-400 italic text-[11px]">
                    El plano 2D no se incluye en el PDF (se puede activar en «Imágenes del PDF»).
                  </p>
                )}
              </div>
            </Seccion>
            {/* ── Selección de imágenes para el PDF ─────────────────────────────────── */}
            <hr className="border-gray-100 my-4 print:hidden" />
              <SelectorImagenes
                capturas={capturas}
                seleccion={seleccion}
                onToggle={alternarImagen}
                onTodas={elegirTodas}
                onNinguna={elegirNinguna}
                cargando={fase === 'capturando'}
                onRetry={reintentarCapturas}
              />

            {/* ── SECCIÓN 4: Modelo 3D ─────────────────────────────────────── */}
            <Seccion id="sec-3d" numero="4" titulo="Vistas del Modelo 3D con Cobertura SPDA" icon={Box}>
              <div className="space-y-2">
                <p className="text-gray-500 text-[11px]">
                  Vistas del modelo 3D con los mástiles y la cobertura de los pararrayos
                  (Modelo 3D ID: {nvl(datos.ids?.id_modelo3d)}).
                </p>
                {vistas3dElegidas.length === 0 ? (
                  <p className="text-gray-400 italic text-[11px]">
                    No hay vistas 3D seleccionadas para el PDF (se eligen en «Imágenes del PDF»).
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {vistas3dElegidas.map(({ key, label }) => (
                      <figure key={key} className="space-y-1">
                        <ImagenCaptura
                          src={capturas[key]}
                          alt={`Modelo 3D: vista ${label.toLowerCase()}`}
                          cargando={fase === 'capturando'}
                          onRetry={reintentarCapturas}
                          className="aspect-[1400/900]"
                        />
                        <figcaption className="text-[10px] text-gray-500 text-center">
                          Vista {label.toLowerCase()}
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </div>
            </Seccion>

            <hr className="border-gray-100 my-4" />

            {/* ── SECCIÓN 5: Cobertura ─────────────────────────────────────── */}
            <Seccion id="sec-cobertura" numero="5" titulo="Detalle de Cobertura SPDA" icon={Shield}>
              {!cobertura ? (
                <p className="text-gray-400 italic text-xs">
                  Sin datos de cobertura. Confirme la ubicación de mástiles en el Paso 5.
                </p>
              ) : (
                <div className="space-y-4">

                  {/* Fichas de resumen */}
                  <div className="grid grid-cols-4 gap-3">
                    <div className="p-3 bg-emerald-50 border-l-4 border-emerald-500 rounded">
                      <div className="text-[10px] text-emerald-700 font-bold uppercase">Cobertura SPDA</div>
                      <div className="text-xl font-bold font-condensed text-emerald-800">
                        {fmtPct(cobertura.porcentaje_cobertura)}
                      </div>
                    </div>
                    <div className="p-3 bg-slate-50 border-l-4 border-slate-400 rounded">
                      <div className="text-[10px] text-slate-600 font-bold uppercase">Total mástiles</div>
                      <div className="text-xl font-bold font-condensed text-slate-800">
                        {cobertura.total_mastiles ?? '—'}
                      </div>
                    </div>
                    <div className="p-3 bg-red-50 border-l-4 border-red-400 rounded">
                      <div className="text-[10px] text-red-700 font-bold uppercase">Zonas desprotegidas</div>
                      <div className="text-xl font-bold font-condensed text-red-800">
                        {zonasDesp.length}
                      </div>
                      {areaDesp > 0 && (
                        <div className="text-[10px] text-red-600">{fmt(areaDesp, 2)} m²</div>
                      )}
                    </div>
                    <div className="p-3 bg-blue-50 border-l-4 border-brand-blue rounded">
                      <div className="text-[10px] text-brand-blue font-bold uppercase">Radio esfera</div>
                      <div className="text-xl font-bold font-condensed text-slate-800">
                        R = {fmt(cobertura.radio_esfera_rodante_r, 0)} m
                      </div>
                    </div>
                  </div>

                  {/* Áreas */}
                  <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 bg-slate-50 p-3 rounded border border-gray-100">
                    <Dato label="Área total de cubiertas"    value={`${fmt(cobertura.area_total_m2, 2)} m²`} />
                    <Dato label="Área cubierta protegida"    value={`${fmt(cobertura.area_protegida_m2, 2)} m²`} />
                    <Dato label="Total de cubiertas"         value={totalCubiertas} />
                    <Dato label="Cubiertas protegidas"       value={cubProtegidas} />
                    <Dato label="Cubiertas parciales"        value={cubParciales} />
                    <Dato label="Cubiertas desprotegidas"    value={cubDesproteg} />
                  </div>

                  {/* Advertencias */}
                  {cobertura.advertencias?.length > 0 && (
                    <div className="space-y-1">
                      {cobertura.advertencias.map((a, i) => (
                        <div
                          key={i}
                          className="flex gap-1.5 items-start text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 text-[11px]"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                          <span>{a}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tabla de cubiertas */}
                  {prismas.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs border-collapse border-t-2 border-b-2 border-gray-800">
                        <thead>
                          <tr className="border-b border-gray-800">
                            <th className="p-2 text-left font-bold text-gray-700">Cubierta</th>
                            <th className="p-2 text-left font-bold text-gray-700">Estado</th>
                            <th className="p-2 text-right font-bold text-gray-700">Cobertura (%)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {prismas.map((p) => {
                            const est = ESTADO_PRISMA[p.estado] || {
                              label: p.estado, cls: 'text-slate-500', dot: 'bg-slate-400',
                            };
                            return (
                              <tr key={p.id} className="hover:bg-slate-50">
                                <td className="p-2 text-gray-700 font-mono text-[11px]">{p.id}</td>
                                <td className="p-2">
                                  <span className={`flex items-center gap-1.5 ${est.cls}`}>
                                    <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${est.dot}`} />
                                    {est.label}
                                  </span>
                                </td>
                                <td className="p-2 text-right font-semibold tabular-nums">
                                  {fmt(p.porcentaje_cobertura, 1)} %
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Ternas sin esfera */}
                  {ternas.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded p-3">
                      <div className="text-[10px] font-bold uppercase text-amber-800 mb-1">
                        Ternas sin esfera posible: {ternas.length}
                      </div>
                      <p className="text-[11px] text-amber-700">
                        Existen {ternas.length} terna(s) de mástiles en las que la esfera rodante
                        no puede ser tangente a los tres sin tocar la cubierta. Revise las alturas
                        y separaciones en el Paso 5.
                      </p>
                    </div>
                  )}
                  {ternas.length === 0 && prismas.length > 0 && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded px-3 py-2 text-[11px] text-emerald-700">
                      Todas las ternas admiten esfera rodante.
                    </div>
                  )}
                </div>
              )}
            </Seccion>

            <hr className="border-gray-100 my-4" />

            {/* ── SECCIÓN 6: Listado de materiales ─────────────────────────── */}
            <Seccion id="sec-materiales" numero="6" titulo="Listado de Materiales" icon={Package}>
              {materiales.length === 0 ? (
                <p className="text-gray-500 italic text-xs">
                  Sin materiales: el proyecto no tiene mástiles colocados.
                </p>
              ) : (
                <div className="space-y-2">
                  <p className="text-[11px] text-gray-500">
                    Cómputo métrico según {totalMastilesMat} mástil(es) del proyecto
                    (todos los modelos 2D del proyecto).
                    {datos.ids?.id_modelo2d && datos.mastiles && datos.mastiles.length !== totalMastilesMat && (
                      <span className="ml-1 text-amber-700">
                        — Nota: el modelo 2D activo tiene {datos.mastiles.length} mástil(es);
                        el listado incluye todos los del proyecto.
                      </span>
                    )}
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs border-collapse border-t-2 border-b-2 border-gray-800">
                      <thead>
                        <tr className="border-b border-gray-800">
                          <th className="p-2 text-left font-bold text-gray-700">Código</th>
                          <th className="p-2 text-left font-bold text-gray-700">Descripción</th>
                          <th className="p-2 text-center font-bold text-gray-700">Cantidad</th>
                        </tr>
                      </thead>
                      <tbody>
                        {materiales.map((m, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="p-2 font-mono text-gray-600">{m.codigo || '—'}</td>
                            <td className="p-2 text-gray-800">{m.descripcion}</td>
                            <td className="p-2 text-center font-semibold text-brand-blue">{m.cantidad}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Seccion>

            {/* Declaración de cumplimiento */}
            <div className="bg-emerald-50 border border-emerald-200 p-3 rounded text-emerald-900 mt-6">
              <div className="font-bold uppercase text-[10px] text-emerald-800 mb-1">
                Declaración de Cumplimiento Legal (Decreto 351/79 Anexo VI)
              </div>
              <p className="text-justify text-[11px]">
               El calculo de este informe se hizo conforme a las normativas de
                seguridad laboral vigentes (Ley 19.587, Decreto 351/79 Anexo VI e IRAM 2184).
              </p>
            </div>

          </div>
          {/* Pie de página */}
          <div className="border-t border-gray-100 px-6 py-3 flex justify-between items-center text-[10px] text-gray-400 bg-slate-50">
            <span>FARADYNE — Sistema de Protección contra Descargas Atmosféricas</span>
            <span>Generado el {new Date().toLocaleDateString('es-AR')}</span>
          </div>
        </div>
      )}

      {/* ── Visores off-screen: solo existen mientras se capturan las imágenes ──
          Con tamaño real (NO display:none): el canvas 3D necesita ancho > 0. */}
      {fase === 'capturando' && datos && (
        <div
          aria-hidden="true"
          style={{ position: 'fixed', left: -20000, top: 0, pointerEvents: 'none' }}
        >
          {datos.ids?.id_modelo2d && (
            <div style={{ width: CAPTURA_2D.width, height: CAPTURA_2D.height }}>
              <GeometriaViewerMastiles
                ref={ref2d}
                idModelo2D={datos.ids.id_modelo2d}
                masts={datos.mastiles ?? SIN_MASTILES}
                radioEsfera={Number(datos.cobertura?.radio_esfera_rodante_r) || 30}
                soloLectura
                width={CAPTURA_2D.width}
                height={CAPTURA_2D.height}
                onReady={() => setEstado2d('ok')}
                onError={() => setEstado2d('error')}
              />
            </div>
          )}
          {datos.ids?.id_modelo3d && (
            <div style={{ width: CAPTURA_3D.width, height: CAPTURA_3D.height }}>
              {/* Solo idModelo3D: con idModelo2D el visor podría regenerar el modelo */}
              <Modelo3DViewer
                ref={ref3d}
                idModelo3D={datos.ids.id_modelo3d}
                masts={datos.mastiles ?? SIN_MASTILES}
                coverageData={datos.coverage_data ?? null}
                soloLectura
                onReady={() => setEstado3d('ok')}
                onError={() => setEstado3d('error')}
              />
            </div>
          )}
        </div>
      )}

      {/* ── Controles de exportación ────────────────────────────────────────── */}
      <div className="flex gap-3">
        <button
          type="button"
          onClick={generarYDescargar}
          disabled={generating || fase === 'capturando' || !idProyecto}
          className="btn-electric flex-1 py-2.5 bg-brand-blue hover:bg-brand-hover disabled:opacity-60 text-white font-bold rounded text-xs flex items-center justify-center gap-2 transition"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          {generating
            ? 'Generando PDF...'
            : fase === 'capturando'
              ? 'Preparando imágenes...'
              : `Generar y descargar PDF (${imagenesPdf.length} imagen${imagenesPdf.length === 1 ? '' : 'es'})`}
        </button>

        <button
          type="button"
          disabled
          className="py-2.5 px-4 bg-gray-100 border border-gray-300 text-gray-400 font-bold rounded text-xs cursor-not-allowed flex items-center gap-2"
          title="Pendiente: guardar versión en backend"
        >
          <CloudUpload className="w-4 h-4" /> Guardar Versión (Deshabilitado)
        </button>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
};

export default MemoriaDescriptiva;
