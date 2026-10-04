import React, { useState } from 'react';
import { ArrowRight, Eye, EyeOff, Lock, User } from 'lucide-react';
import { authApi } from '../../api/auth';
import { getApiErrorMessage } from '../../api/apiErrors';

export const LoginForm = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await authApi.login(email, password);
      onLogin(data);
    } catch (err) {
      setError(getApiErrorMessage(err, 'No se pudo iniciar sesión.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Usuario / Email</label>
        <div className="relative">
          <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="proyectista@faradyne.com" className="input-electric w-full pl-9 pr-3 py-2 border border-gray-300 rounded text-xs" />
          <User className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
        </div>
      </div>
      <div>
        <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Contraseña</label>
        <div className="relative">
          <input type={showPassword ? 'text' : 'password'} required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Ingresá tu contraseña" className="password-input input-electric w-full pl-9 pr-9 py-2 border border-gray-300 rounded text-xs" />
          <Lock className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
          <button type="button" onClick={() => setShowPassword((current) => !current)} disabled={!password} className="absolute right-2.5 top-2.5 text-gray-400 hover:text-brand-blue transition disabled:cursor-not-allowed disabled:opacity-40" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button type="submit" disabled={loading} className="btn-electric w-full py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition flex items-center justify-center gap-1.5 disabled:opacity-60">
        {loading ? 'Ingresando...' : 'Ingresar al Sistema'} <ArrowRight className="w-4 h-4" />
      </button>
    </form>
  );
};