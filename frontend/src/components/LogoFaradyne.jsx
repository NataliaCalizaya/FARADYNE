import React from 'react';
import { Link } from 'react-router-dom';
import { Zap } from 'lucide-react';

export const LogoFaradyne = ({ to = '/proyectos' }) => (
  <Link to={to} className="flex items-center gap-2 shrink-0">
    <div className="w-8 h-8 bg-brand-blue rounded flex items-center justify-center text-white">
      <Zap className="w-5 h-5 fill-white" />
    </div>
    <span className="font-condensed font-extrabold text-lg text-white tracking-wide">FARADYNE</span>
  </Link>
);

export default LogoFaradyne;