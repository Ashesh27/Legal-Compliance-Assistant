import React from 'react';
import { ListChecks, Download } from 'lucide-react';

const RequirementsViewer = ({ requirements, onDownload, title = "Requisiti Normativi Estratti" }) => {
    if (!requirements || requirements.length === 0) return null;

    return (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden animate-fade-in mb-12">
            <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <div className="bg-emerald-50 text-emerald-600 p-2 rounded-lg">
                        <ListChecks size={24} />
                    </div>
                    <div>
                        <h3 className="text-xl font-bold text-slate-800">{title}</h3>
                        <p className="text-sm text-slate-500">Identificati {requirements.length} macro-obblighi dalla documentazione.</p>
                    </div>
                </div>

                {onDownload && (
                    <button
                        onClick={onDownload}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition-colors"
                    >
                        <Download size={18} />
                        Scarica TXT
                    </button>
                )}
            </div>

            <div className="p-6 bg-slate-50/50">
                <div className="grid gap-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                    {requirements.map((req, idx) => (
                        <div key={idx} className="bg-white p-5 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between gap-4 mb-2">
                                <h4 className="font-bold text-slate-800 text-lg">Requisito #{req.numero}</h4>
                                <span className="px-2 py-1 rounded text-xs font-bold uppercase tracking-wide bg-blue-50 text-blue-600">
                                    NORMAL
                                </span>
                            </div>
                            <p className="text-slate-600 text-sm leading-relaxed mb-3">{req.requisito}</p>

                            {req.domanda_audit && (
                                <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-500 italic">
                                    <strong>Audit Question:</strong> {req.domanda_audit}
                                </div>
                            )}

                            <div className="mt-2 text-[10px] text-slate-400">
                                Fonte: {req.file_sorgente}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default RequirementsViewer;
