import React, { useState, useEffect } from 'react';
import { History, FileText, Calendar, ChevronRight, X } from 'lucide-react';

function AnalysisHistory({ onSelectAnalysis, onClose }) {
    const [mappings, setMappings] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchMappings();
    }, []);

    const fetchMappings = async () => {
        try {
            const res = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-mappings`);
            if (res.ok) {
                const data = await res.json();
                // Sort by date if available, otherwise by name
                const sortedData = data.sort((a, b) => {
                    if (a.metadata?.processing_date && b.metadata?.processing_date) {
                        return new Date(b.metadata.processing_date) - new Date(a.metadata.processing_date);
                    }
                    return 0;
                });
                setMappings(sortedData);
            }
        } catch (error) {
            console.error("Error fetching mappings:", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 rounded-t-2xl">
                    <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <History className="text-brand-600" />
                        Analisi Effettuate
                    </h3>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-500"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="overflow-y-auto p-6 space-y-3">
                    {loading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
                        </div>
                    ) : mappings.length === 0 ? (
                        <div className="text-center py-12 text-slate-400">
                            <History size={48} className="mx-auto mb-4 opacity-20" />
                            <p>Nessuna analisi trovata</p>
                        </div>
                    ) : (
                        mappings.map((mapping, idx) => (
                            <button
                                key={idx}
                                onClick={() => onSelectAnalysis(mapping)}
                                className="w-full text-left bg-white border border-slate-200 hover:border-brand-300 hover:shadow-md hover:bg-brand-50/30 p-4 rounded-xl transition-all group flex items-center justify-between"
                            >
                                <div className="flex items-start gap-4">
                                    <div className="p-3 bg-brand-100 text-brand-600 rounded-lg group-hover:scale-110 transition-transform">
                                        <FileText size={20} />
                                    </div>
                                    <div>
                                        <h4 className="font-bold text-slate-800 group-hover:text-brand-700 transition-colors">
                                            {mapping.name}
                                        </h4>
                                        <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                                            <span className="flex items-center gap-1">
                                                <Calendar size={12} />
                                                {mapping.metadata?.processing_date || 'Data sconosciuta'}
                                            </span>
                                            {mapping.metadata?.total_chunk_files && (
                                                <span className="bg-slate-100 px-2 py-0.5 rounded-full">
                                                    {mapping.metadata.total_chunk_files} documenti
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <ChevronRight className="text-slate-300 group-hover:text-brand-500 group-hover:translate-x-1 transition-all" />
                            </button>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

export default AnalysisHistory;
