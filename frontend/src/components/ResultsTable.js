import React, { useState } from 'react';
import { ChevronDown, FileText, AlertCircle, CheckCircle2, HelpCircle, Download, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

function ResultsTable({ results, excelPath }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [filterCoverage, setFilterCoverage] = useState('all');
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [sortDirection, setSortDirection] = useState(null); // null, 'asc', 'desc'

  if (!results || results.length === 0) {
    return null;
  }

  const handleDownload = () => {
    if (excelPath) {
      window.location.href = `${process.env.REACT_APP_API_URL}/api/download-mapping-excel?file=${encodeURIComponent(excelPath)}`;
    } else {
      alert("File Excel non disponibile.");
    }
  };

  const filteredResults = results.filter(r => {
    if (filterCoverage === 'all') return true;
    return r.analysis?.livello_copertura === Number(filterCoverage);
  });

  const sortedResults = [...filteredResults].sort((a, b) => {
    if (!sortDirection) return 0;
    const valA = a.analysis?.livello_copertura || 0;
    const valB = b.analysis?.livello_copertura || 0;
    // Descending: High to Low (5 -> 1) is usually more useful for 'Coverage' but typically 'desc' means 5->1
    return sortDirection === 'asc' ? valA - valB : valB - valA;
  });

  const effectiveItemsPerPage = itemsPerPage === 'all' ? sortedResults.length : itemsPerPage;
  const totalPages = Math.ceil(sortedResults.length / effectiveItemsPerPage);
  const startIndex = (currentPage - 1) * effectiveItemsPerPage;
  const currentResults = sortedResults.slice(startIndex, startIndex + effectiveItemsPerPage);

  const handleSortToggle = () => {
    // Cycle: null -> desc (high to low) -> asc (low to high) -> null
    if (sortDirection === null) setSortDirection('desc');
    else if (sortDirection === 'desc') setSortDirection('asc');
    else setSortDirection(null);
  };

  const toggleRowExpansion = (idx) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(idx)) {
      newExpanded.delete(idx);
    } else {
      newExpanded.add(idx);
    }
    setExpandedRows(newExpanded);
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 5: return 'bg-emerald-500';
      case 4: return 'bg-emerald-400';
      case 3: return 'bg-yellow-400';
      case 2: return 'bg-orange-400';
      case 1: return 'bg-red-500';
      default: return 'bg-slate-400';
    }
  };

  const getTypeBadge = (type) => {
    const colors = {
      generale: 'bg-blue-100 text-blue-700 border-blue-200',
      divieto: 'bg-red-100 text-red-700 border-red-200',
      formazione: 'bg-green-100 text-green-700 border-green-200',
      documentazione: 'bg-cyan-100 text-cyan-700 border-cyan-200',
      comunicazione: 'bg-purple-100 text-purple-700 border-purple-200',
      monitoraggio: 'bg-orange-100 text-orange-700 border-orange-200',
      default: 'bg-slate-100 text-slate-700 border-slate-200'
    };
    const style = colors[type?.toLowerCase()] || colors.default;
    return (
      <span className={`px-2 py-1 rounded-md text-xs font-bold border ${style} uppercase tracking-wider`}>
        {type || 'N/A'}
      </span>
    );
  };

  const ensureArray = (item) => {
    if (Array.isArray(item)) return item;
    if (typeof item === 'string') return [item];
    if (!item) return [];
    return [];
  };

  return (
    <div className="mt-12 animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-center mb-6 gap-4">
        <h3 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
          <CheckCircle2 className="text-brand-600" />
          Risultati Analisi <span className="text-slate-400 text-lg font-normal">({results.length} requisiti)</span>
        </h3>

        <div className="flex items-center gap-3">
          <button
            onClick={handleDownload}
            disabled={!excelPath}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold shadow-lg transition-all 
              ${excelPath
                ? 'bg-emerald-500 hover:bg-emerald-600 text-white hover:scale-105 active:scale-95 shadow-emerald-500/20'
                : 'bg-slate-300 text-slate-500 cursor-not-allowed'}`}
          >
            <Download size={18} />
            Scarica Excel
          </button>

          <div className="flex items-center gap-3 bg-white p-2 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-sm text-slate-500 font-medium pl-2">Mostra:</span>
            <select
              value={itemsPerPage}
              onChange={(e) => {
                setItemsPerPage(e.target.value === 'all' ? 'all' : Number(e.target.value));
                setCurrentPage(1);
              }}
              className="bg-slate-50 border-none rounded-lg text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-brand-500 py-1.5 pl-3 pr-8 cursor-pointer"
            >
              <option value={10}>10 per pagina</option>
              <option value={25}>25 per pagina</option>
              <option value={50}>50 per pagina</option>
              <option value="all">Tutti</option>
            </select>
          </div>

          <div className="flex items-center gap-3 bg-white p-2 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-sm text-slate-500 font-medium pl-2">Filtra:</span>
            <select
              value={filterCoverage}
              onChange={(e) => {
                setFilterCoverage(e.target.value);
                setCurrentPage(1);
              }}
              className="bg-slate-50 border-none rounded-lg text-sm font-semibold text-slate-700 focus:ring-2 focus:ring-brand-500 py-1.5 pl-3 pr-8 cursor-pointer"
            >
              <option value="all">Tutti i livelli</option>
              <option value="1">Copertura 1 (Critica)</option>
              <option value="2">Copertura 2 (Bassa)</option>
              <option value="3">Copertura 3 (Parziale)</option>
              <option value="4">Copertura 4 (Buona)</option>
              <option value="5">Copertura 5 (Completa)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-3xl shadow-xl border border-slate-200/60 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider w-16">ID</th>
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider w-[30%]">Requisito</th>
                <th className="px-6 py-4 text-left text-xs font-bold text-slate-500 uppercase tracking-wider w-[25%]">Domanda Audit</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Tipo</th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">
                  <button
                    onClick={handleSortToggle}
                    className="inline-flex items-center gap-1 hover:text-brand-600 transition-colors"
                  >
                    COPERTURA
                    {sortDirection === null && <ArrowUpDown size={14} className="opacity-50" />}
                    {sortDirection === 'asc' && <ArrowUp size={14} className="text-brand-500" />}
                    {sortDirection === 'desc' && <ArrowDown size={14} className="text-brand-500" />}
                  </button>
                </th>
                <th className="px-6 py-4 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">Azioni</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {currentResults.map((result, idx) => {
                const globalIdx = startIndex + idx;
                const isExpanded = expandedRows.has(globalIdx);

                return (
                  <React.Fragment key={globalIdx}>
                    <tr className={`transition-colors hover:bg-slate-50/50 ${isExpanded ? 'bg-slate-50' : 'bg-white'}`}>
                      <td className="px-6 py-4 text-sm font-bold text-slate-400">
                        #{result.requirement_id || globalIdx + 1}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-slate-800 font-medium leading-relaxed">
                          {result.requirement_original || 'N/A'}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {result.audit_question ? (
                          <div className="flex items-start gap-2 text-xs text-slate-600">
                            <HelpCircle size={14} className="mt-0.5 text-slate-400 flex-shrink-0" />
                            <span className="italic">{result.audit_question}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400 italic">N/A</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center">
                        {getTypeBadge(result.requirement_type)}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className={`inline-flex items-center justify-center px-3 py-1 rounded-full text-xs font-bold text-white ${getLevelColor(result.analysis?.livello_copertura)} shadow-sm`}>
                          {result.analysis?.livello_copertura || 'N/A'}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 font-medium uppercase tracking-wide">
                          {result.analysis?.descrizione_livello}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <button
                          onClick={() => toggleRowExpansion(globalIdx)}
                          className={`
                            p-2 rounded-full transition-all duration-200 border
                            ${isExpanded
                              ? 'bg-brand-50 text-brand-600 border-brand-200 rotate-180'
                              : 'bg-white text-slate-400 border-slate-200 hover:border-brand-300 hover:text-brand-500'
                            }
                          `}
                        >
                          <ChevronDown size={18} />
                        </button>
                      </td>
                    </tr>

                    {isExpanded && (
                      <tr>
                        <td colSpan="7" className="p-0">
                          <div className="bg-slate-50/80 border-y border-slate-200 p-6 animate-fade-in">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                              {/* Left Column */}
                              <div className="space-y-6">
                                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                                  <h4 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                                    <CheckCircle2 size={16} className="text-emerald-500" />
                                    Analisi Allineamento
                                  </h4>
                                  <p className="text-sm text-slate-600 leading-relaxed">
                                    {result.analysis?.allineamento || 'Nessuna analisi disponibile'}
                                  </p>
                                </div>

                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Aspetti Coperti</h4>
                                  <ul className="space-y-2">
                                    {ensureArray(result.analysis?.aspetti_coperti).map((item, i) => (
                                      <li key={i} className="flex items-start gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200/50">
                                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5"></div>
                                        {item}
                                      </li>
                                    ))}
                                    {ensureArray(result.analysis?.aspetti_coperti).length === 0 && (
                                      <li className="text-sm text-slate-400 italic">Nessun aspetto rilevato</li>
                                    )}
                                  </ul>
                                </div>



                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">File di Origine</h4>
                                  <div className="flex flex-wrap gap-2">
                                    {result.matches?.map(m => m.chunk?.source_file).filter((v, i, a) => a.indexOf(v) === i).map((file, i) => (
                                      <div key={i} className="flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-600">
                                        <FileText size={12} className="text-brand-500" />
                                        <span className="truncate max-w-[200px]">{file.split('/').pop()}</span>
                                      </div>
                                    )) || <span className="text-sm text-slate-400 italic">Nessun file collegato</span>}
                                  </div>
                                </div>
                              </div>

                              {/* Right Column */}
                              <div className="space-y-6">
                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Aspetti Mancanti</h4>
                                  <ul className="space-y-2">
                                    {ensureArray(result.analysis?.aspetti_mancanti).map((item, i) => (
                                      <li key={i} className="flex items-start gap-2 text-sm text-slate-600 bg-white px-3 py-2 rounded-lg border border-red-200/50">
                                        <div className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5"></div>
                                        {item}
                                      </li>
                                    ))}
                                    {ensureArray(result.analysis?.aspetti_mancanti).length === 0 && (
                                      <li className="text-sm text-slate-400 italic">Nessun aspetto mancante rilevato</li>
                                    )}
                                  </ul>
                                </div>

                                <div className="bg-red-50/50 p-5 rounded-2xl border border-red-100">
                                  <h4 className="text-sm font-bold text-red-800 mb-3 flex items-center gap-2">
                                    <AlertCircle size={16} className="text-red-500" />
                                    Gap Identificati
                                  </h4>
                                  <ul className="space-y-2">
                                    {ensureArray(result.analysis?.gap).map((item, i) => (
                                      <li key={i} className="flex items-start gap-2 text-sm text-red-700">
                                        <div className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5"></div>
                                        {item}
                                      </li>
                                    ))}
                                    {ensureArray(result.analysis?.gap).length === 0 && (
                                      <li className="text-sm text-slate-400 italic">Nessun gap rilevato</li>
                                    )}
                                  </ul>
                                </div>

                                <div>
                                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Azioni Richieste</h4>
                                  <ul className="space-y-2">
                                    {ensureArray(result.analysis?.azioni_richieste).map((item, i) => (
                                      <li key={i} className="flex items-start gap-2 text-sm text-slate-700 bg-white px-3 py-2 rounded-lg border-l-4 border-brand-500 shadow-sm">
                                        {item}
                                      </li>
                                    ))}
                                    {ensureArray(result.analysis?.azioni_richieste).length === 0 && (
                                      <li className="text-sm text-slate-400 italic">Nessuna azione richiesta</li>
                                    )}
                                  </ul>
                                </div>
                              </div>

                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-white border-t border-slate-200 px-6 py-4 flex items-center justify-between">
            <div className="text-sm text-slate-500">
              Pagina <span className="font-bold text-slate-800">{currentPage}</span> di <span className="font-bold text-slate-800">{totalPages}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1}
                className="px-4 py-2 rounded-xl border border-slate-200 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Precedente
              </button>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages}
                className="px-4 py-2 rounded-xl bg-slate-900 text-white text-sm font-bold hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg shadow-slate-200"
              >
                Successiva
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ResultsTable;