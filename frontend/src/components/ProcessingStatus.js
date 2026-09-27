import React from 'react';
import { Loader2 } from 'lucide-react';

const ProcessingStatus = ({ status, message, progress = 0 }) => {
  if (!status || status === 'idle') return null;

  return (
    <div className="fixed inset-0 z-50 bg-white/80 backdrop-blur-lg flex items-center justify-center animate-fade-in">
      <div className="max-w-md w-full bg-white p-8 rounded-3xl shadow-2xl border border-slate-100 text-center relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-slate-100">
          <div
            className="h-full bg-brand-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          ></div>
        </div>

        <div className="w-16 h-16 bg-brand-50 text-brand-600 rounded-2xl mx-auto mb-6 flex items-center justify-center">
          <Loader2 size={32} className="animate-spin" />
        </div>

        <h3 className="text-xl font-bold text-slate-800 mb-2">Elaborazione in corso</h3>
        <p className="text-slate-500 mb-6 min-h-[3rem]">{message}</p>
      </div>
    </div>
  );
};

export default ProcessingStatus;