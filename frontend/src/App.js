import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, ArrowRight, CheckCircle2, AlertCircle, PlayCircle, BookOpen, Eye, Download, Trash2, CheckSquare, Square, Upload, FileText, Loader2, Settings, History } from 'lucide-react';
import FileUpload from './components/FileUpload';
import ProcessingStatus from './components/ProcessingStatus';
import ResultsTable from './components/ResultsTable';
import RequirementsViewer from './components/RequirementsViewer';
import AnalysisHistory from './components/AnalysisHistory';
import ConfirmationModal from './components/ConfirmationModal';

function App() {
  const [requirementsFiles, setRequirementsFiles] = useState([]);
  const [internalDocsFiles, setInternalDocsFiles] = useState([]);

  const [processingStatus, setProcessingStatus] = useState({
    requirements: { status: 'idle', step: '', progress: 0, message: '' },
    internal_docs: { status: 'idle', step: '', progress: 0, message: '' },
    mapping: { status: 'idle', step: '', progress: 0, message: '' }
  });

  const [availableData, setAvailableData] = useState({
    requirements: false,
    internal_docs: false,
    mapping_results: false
  });

  const [processedRequirements, setProcessedRequirements] = useState([]);
  const [processedInternalDocs, setProcessedInternalDocs] = useState([]);
  const [selectedRequirement, setSelectedRequirement] = useState(null);
  const [selectedChunks, setSelectedChunks] = useState(new Set());
  const [viewingRequirements, setViewingRequirements] = useState(null);
  const [results, setResults] = useState([]);
  const [excelPath, setExcelPath] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [requirementsSearch, setRequirementsSearch] = useState('');
  const [internalDocsSearch, setInternalDocsSearch] = useState('');

  const [error, setError] = useState(null);
  const [isWorkflowActive, setIsWorkflowActive] = useState(false);
  const [isAnnexMode, setIsAnnexMode] = useState(false);
  const resultsRef = useRef(null);

  // Check for existing processed data on load
  useEffect(() => {
    checkAvailableData();
    fetchProcessedRequirements();
    fetchProcessedInternalDocs();
  }, []);

  // Poll status
  useEffect(() => {
    const interval = setInterval(() => {
      ['requirements', 'mapping'].forEach(module => {
        if (processingStatus[module].status === 'processing') {
          fetch(`${process.env.REACT_APP_API_URL}/api/status/${module}`)
            .then(res => res.json())
            .then(data => {
              setProcessingStatus(prev => ({
                ...prev,
                [module]: data
              }));

              if (data.status === 'completed') {
                checkAvailableData();
                if (module === 'mapping') {
                  fetchResults();
                  setIsWorkflowActive(false);
                }
                if (module === 'requirements') {
                  fetchProcessedRequirements();
                }
              } else if (data.status === 'error') {
                setError(`Errore in ${module}: ${data.message}`);
                if (module === 'mapping') setIsWorkflowActive(false);
              }
            })
            .catch(err => console.error(`Error fetching ${module} status:`, err));
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [processingStatus]);

  const checkAvailableData = async () => {
    try {
      const [reqRes, docsRes, mapRes] = await Promise.all([
        fetch(`${process.env.REACT_APP_API_URL}/api/check-requirements`),
        fetch(`${process.env.REACT_APP_API_URL}/api/check-internal-docs`),
        fetch(`${process.env.REACT_APP_API_URL}/api/check-existing-results`)
      ]);

      const reqData = await reqRes.json();
      const docsData = await docsRes.json();
      const mapData = await mapRes.json();

      setAvailableData({
        requirements: reqData.exists,
        internal_docs: docsData.exists,
        mapping_results: mapData.exists
      });
    } catch (error) {
      console.error('Error checking available data:', error);
    }
  };

  const fetchResults = async () => {
    try {
      console.log("Fetching results from /api/results...");
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/results`);
      console.log("Results response status:", res.status);
      if (res.ok) {
        const data = await res.json();
        console.log("Results data received:", data);
        if (Array.isArray(data)) {
          setResults(data);
        } else {
          setResults(data.results || []);
          if (data.excel_path) {
            setExcelPath(data.excel_path);
          }
        }
      } else {
        console.error("Failed to fetch results, status:", res.status);
      }
    } catch (error) {
      console.error("Error fetching results:", error);
    }
  };

  const fetchProcessedRequirements = async () => {
    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-requirements`);
      if (res.ok) {
        const data = await res.json();
        setProcessedRequirements(data);
      }
    } catch (error) {
      console.error("Error fetching processed requirements:", error);
    }
  };

  const fetchProcessedInternalDocs = async () => {
    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-chunks`);
      if (res.ok) {
        const data = await res.json();
        setProcessedInternalDocs(data);
      }
    } catch (error) {
      console.error("Error fetching processed internal docs:", error);
    }
  };

  const handleUpload = (files, type) => {
    if (type === 'requirements') {
      setRequirementsFiles(prev => [...prev, ...files]);
    } else {
      setInternalDocsFiles(prev => [...prev, ...files]);
    }
    setError(null);
  };

  const handleRemove = (index, type) => {
    if (type === 'requirements') {
      setRequirementsFiles(prev => prev.filter((_, i) => i !== index));
    } else {
      setInternalDocsFiles(prev => prev.filter((_, i) => i !== index));
    }
  };

  const processModule = async (module, formData) => {
    try {
      let endpoint;
      switch (module) {
        case 'requirements': endpoint = 'process-requirements'; break;
        case 'internal_docs': endpoint = 'process-internal-docs'; break;
        case 'mapping': endpoint = 'process-mapping'; break;
        default: throw new Error('Invalid module');
      }

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/${endpoint}`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        setProcessingStatus(prev => ({
          ...prev,
          [module]: { status: 'processing', step: 'Avvio...', progress: 0, message: data.message }
        }));
        return true;
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error(`Error processing ${module}:`, error);
      setError(error.message);
      setProcessingStatus(prev => ({
        ...prev,
        [module]: { status: 'error', step: 'Error', progress: 0, message: error.message }
      }));
      return false;
    }
  };

  const runRequirementsExtraction = async () => {
    if (requirementsFiles.length === 0) {
      setError("Carica almeno un documento dei requisiti (Normativa).");
      return;
    }

    for (const file of requirementsFiles) {
      const formData = new FormData();
      formData.append('requirements_pdf', file);
      formData.append('extraction_name', file.name.replace('.pdf', ''));

      const success = await processModule('requirements', formData);
      if (!success) break;

      await new Promise(resolve => {
        const checkInterval = setInterval(async () => {
          const res = await fetch(`${process.env.REACT_APP_API_URL}/api/status/requirements`);
          const status = await res.json();
          if (status.status === 'completed' || status.status === 'error') {
            clearInterval(checkInterval);
            resolve();
          }
        }, 1000);
      });
    }

    setRequirementsFiles([]);
    fetchProcessedRequirements();
  };

  const runInternalDocsProcessing = async () => {
    if (internalDocsFiles.length === 0) {
      setError("Carica almeno un documento aziendale.");
      return;
    }

    setIsWorkflowActive(true);

    for (const [index, file] of internalDocsFiles.entries()) {
      console.log(`Starting processing for file ${index + 1}/${internalDocsFiles.length}: ${file.name}`);

      setProcessingStatus(prev => ({
        ...prev,
        internal_docs: { status: 'processing', step: 'Avvio...', progress: 0, message: `Preparazione ${file.name}...` }
      }));

      const formData = new FormData();
      formData.append('internal_docs', file);

      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/process-internal-docs`, {
          method: 'POST',
          body: formData
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || 'Upload failed');
        }
      } catch (error) {
        console.error(`Failed to start processing for file ${file.name}:`, error);
        setError(`Errore caricamento ${file.name}: ${error.message}`);
        setIsWorkflowActive(false);
        return;
      }

      await new Promise((resolve, reject) => {
        const checkInterval = setInterval(async () => {
          try {
            const res = await fetch(`${process.env.REACT_APP_API_URL}/api/status/internal_docs`);
            const status = await res.json();

            setProcessingStatus(prev => ({
              ...prev,
              internal_docs: status
            }));

            if (status.status === 'completed') {
              clearInterval(checkInterval);
              resolve();
            } else if (status.status === 'error') {
              clearInterval(checkInterval);
              reject(new Error(status.message || 'Error processing internal docs'));
            }
          } catch (err) {
            console.error("Error checking status:", err);
          }
        }, 1000);
      });

      await new Promise(r => setTimeout(r, 1000));
    }

    setInternalDocsFiles([]);
    fetchProcessedInternalDocs();
    setIsWorkflowActive(false);
    setProcessingStatus(prev => ({
      ...prev,
      internal_docs: { status: 'idle', step: '', progress: 0, message: '' }
    }));
  };

  const runFullAnalysis = async () => {
    if (!selectedRequirement) {
      setError("Seleziona una normativa dalla lista 'Normative Disponibili' per l'analisi gap.");
      return;
    }

    if (selectedChunks.size === 0) {
      setError("Seleziona almeno un documento aziendale elaborato per l'analisi.");
      return;
    }

    setIsWorkflowActive(true);

    let chunkFiles = Array.from(selectedChunks);

    if (chunkFiles.length === 0) {
      console.error("No chunk files found!");
      setError("Nessun documento elaborato selezionato per l'analisi.");
      setIsWorkflowActive(false);
      return;
    }

    try {
      console.log("Sending mapping request with:", {
        requirements_file: selectedRequirement,
        chunk_files: chunkFiles
      });

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/process-mapping`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          requirements_file: selectedRequirement.path,
          mapping_name: `Gap Analysis - ${selectedRequirement.name}`,
          chunk_files: chunkFiles
        })
      });

      const data = await response.json();

      if (response.ok) {
        setProcessingStatus(prev => ({
          ...prev,
          mapping: { status: 'processing', step: 'Avvio...', progress: 0, message: data.message }
        }));
        setViewingRequirements(null);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error(`Error processing mapping:`, error);
      setError(error.message);
      setProcessingStatus(prev => ({
        ...prev,
        mapping: { status: 'error', step: 'Error', progress: 0, message: error.message }
      }));
      setIsWorkflowActive(false);
    }
  };

  const handleSelectRequirement = (req) => {
    if (selectedRequirement?.path === req.path) {
      setSelectedRequirement(null);
    } else {
      setSelectedRequirement(req);
    }
  };

  const [deleteModal, setDeleteModal] = useState({ isOpen: false, type: null, item: null });

  const handleDeleteRequirement = (req) => {
    setDeleteModal({
      isOpen: true,
      type: 'requirement',
      item: req,
      title: 'Elimina Normativa',
      message: 'Sei sicuro di voler eliminare la normativa'
    });
  };

  const handleDeleteChunk = (chunk) => {
    setDeleteModal({
      isOpen: true,
      type: 'chunk',
      item: chunk,
      title: 'Elimina Documento',
      message: 'Sei sicuro di voler eliminare il documento'
    });
  };

  const executeDelete = async () => {
    const { type, item } = deleteModal;
    if (!type || !item) return;

    try {
      let endpoint = '';
      let body = {};

      if (type === 'requirement') {
        endpoint = 'delete-requirement';
        body = { folder_name: item.folder_name };
      } else {
        endpoint = 'delete-chunk';
        body = { filename: item.filename };
      }

      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (res.ok) {
        if (type === 'requirement') {
          fetchProcessedRequirements();
          if (selectedRequirement?.path === item.path) setSelectedRequirement(null);
        } else {
          fetchProcessedInternalDocs();
          const newSelected = new Set(selectedChunks);
          newSelected.delete(item.path);
          setSelectedChunks(newSelected);
        }
      } else {
        const data = await res.json();
        setError(data.error || "Errore durante l'eliminazione.");
      }
    } catch (err) {
      console.error("Error deleting item:", err);
      setError("Impossibile eliminare l'elemento.");
    }

    setDeleteModal({ isOpen: false, type: null, item: null });
  };

  const toggleChunkSelection = (path) => {
    const newSelected = new Set(selectedChunks);
    if (newSelected.has(path)) {
      newSelected.delete(path);
    } else {
      newSelected.add(path);
    }
    setSelectedChunks(newSelected);
  };

  const handleViewRequirements = async (reqFile) => {
    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/get-requirements-list?file=${encodeURIComponent(reqFile.path)}`);
      if (res.ok) {
        const data = await res.json();
        setViewingRequirements({
          title: reqFile.name,
          requirements: data.requirements,
          path: reqFile.path
        });
        setResults([]);
        setTimeout(() => {
          resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      }
    } catch (err) {
      console.error("Error loading requirements:", err);
      setError("Impossibile caricare i requisiti.");
    }
  };

  const handleDownloadRequirements = (reqFile) => {
    window.location.href = `${process.env.REACT_APP_API_URL}/api/download-requirements-list?file=${encodeURIComponent(reqFile.path)}`;
  };

  const handleSelectAnalysis = async (mapping) => {
    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/get-mapping-results?file=${encodeURIComponent(mapping.json_path)}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
        setViewingRequirements(null);
        setExcelPath(mapping.excel_path);
        setShowHistory(false);
      }
    } catch (error) {
      console.error("Error loading analysis:", error);
    }
  };

  const isAnalyzing = Object.values(processingStatus).some(s => s.status === 'processing') || isWorkflowActive;

  let activeStatus = Object.values(processingStatus).find(s => s.status === 'processing');

  if (isWorkflowActive && !activeStatus) {
    if (processingStatus.internal_docs.status === 'completed') {
      activeStatus = { ...processingStatus.internal_docs, message: 'Preparazione prossimo documento...' };
    } else if (processingStatus.internal_docs.status === 'idle' && internalDocsFiles.length > 0) {
      activeStatus = { status: 'processing', message: 'Inizializzazione analisi...', progress: 0 };
    }
  }

  const runAnnexProcessing = async () => {
    if (requirementsFiles.length === 0 || internalDocsFiles.length === 0) {
      setError("Carica sia il documento principale che almeno un documento addizionale.");
      return;
    }

    setIsWorkflowActive(true);
    setError(null);

    try {
      setProcessingStatus(prev => ({ ...prev, mapping: { status: 'processing', message: 'Caricamento e rielaborazione...' } }));

      const fdMerge = new FormData();
      fdMerge.append('main_doc_file', requirementsFiles[0]);
      internalDocsFiles.forEach(f => fdMerge.append('annex_doc_files', f));

      const res = await fetch(`${process.env.REACT_APP_API_URL}/api/process-annex-merge`, {
        method: 'POST',
        body: fdMerge
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Errore durante l'avvio del processo.");
      }

      const jobId = data.job_id;

      const interval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${process.env.REACT_APP_API_URL}/api/check-annex-status/${jobId}`);
          const status = await statusRes.json();

          if (status.status === 'completed') {
            clearInterval(interval);
            setIsWorkflowActive(false);
            setProcessingStatus(prev => ({ ...prev, mapping: { status: 'completed', message: 'Rielaborazione completata!' } }));
            window.location.href = `${process.env.REACT_APP_API_URL}/api/download-annex-result/${jobId}`;
          } else if (status.status === 'error') {
            clearInterval(interval);
            setIsWorkflowActive(false);
            setError(status.error);
            setProcessingStatus(prev => ({ ...prev, mapping: { status: 'error', message: status.error } }));
          }
        } catch (e) {
          console.error(e);
          clearInterval(interval);
          setIsWorkflowActive(false);
          setError("Errore durante il monitoraggio.");
        }
      }, 2000);

    } catch (e) {
      console.error(e);
      setError("Errore durante la procedura.");
      setIsWorkflowActive(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 font-sans relative overflow-x-hidden selection:bg-brand-200 selection:text-brand-900">

      {/* Background Ambience */}
      <div className="fixed top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-brand-200/30 rounded-full mix-blend-multiply filter blur-[100px] animate-blob"></div>
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-indigo-200/30 rounded-full mix-blend-multiply filter blur-[100px] animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-[-10%] left-[20%] w-[50%] h-[50%] bg-purple-200/30 rounded-full mix-blend-multiply filter blur-[100px] animate-blob animation-delay-4000"></div>
      </div>

      {/* Navbar */}
      <nav className="sticky top-0 z-40 w-full bg-white/70 backdrop-blur-md border-b border-white/20 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl shadow-lg shadow-brand-500/20">
              <img src="/logo.png" alt="Logo" className="w-10 h-10 object-contain" />
            </div>
            <span className="text-2xl font-bold text-slate-800 tracking-tight">Compl<span className="text-brand-600">ia</span>nce</span>
          </div>
          <div className="hidden md:flex items-center gap-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Enterprise Edition</span>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Hero Header */}
        <div className="text-center max-w-3xl mx-auto mb-16 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white border border-slate-200 shadow-sm mb-6">
            <Sparkles size={14} className="text-brand-500" />
            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">AI Gap Analysis V2.0</span>
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 mb-6 leading-tight tracking-tight">
            Conformità Aziendale, <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-600 via-indigo-600 to-purple-600">Elevata dall'Intelligenza.</span>
          </h1>
          <p className="text-lg text-slate-500 leading-relaxed max-w-2xl mx-auto">
            Carica policy aziendali e normative. La nostra IA segmenta i documenti, identifica i gap critici e genera piani d'azione professionali.
          </p>
        </div>

        {/* Workflow Area */}
        <div className="relative z-10 mb-12">
          <div className="grid md:grid-cols-2 gap-8 relative items-start">
            {/* Connector Arrow */}
            <div className="hidden md:flex absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 items-center justify-center w-12 h-12 bg-white rounded-full border border-slate-200 shadow-sm">
              <ArrowRight className="text-slate-300" />
            </div>

            {/* Upload Zone 1: Requirements (Normative) */}
            <div className="glass-card p-8 rounded-3xl transition-transform hover:-translate-y-1 duration-300">
              <div key={isAnnexMode ? 'annex-req' : 'std-req'} className="animate-fade-in">
                <FileUpload
                  title={isAnnexMode ? "Documento principale" : "1. Nuove Normative"}
                  description={isAnnexMode ? "Carica il documento principale a cui riferire gli annex." : "Carica i PDF delle normative (es. ISO, Regolamento)."}
                  files={requirementsFiles}
                  onUpload={(f) => handleUpload(f, 'requirements')}
                  onRemove={(i) => handleRemove(i, 'requirements')}
                  theme="emerald"
                  accept=".pdf"
                />

                {/* Processed Requirements List */}
                {!isAnnexMode && (
                  <div className="mt-6 border-t border-slate-100 pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Normative Disponibili</h5>
                      <input
                        type="text"
                        placeholder="Cerca..."
                        value={requirementsSearch}
                        onChange={(e) => setRequirementsSearch(e.target.value)}
                        className="text-xs border border-slate-200 rounded-md px-2 py-1 w-24 focus:outline-none focus:border-emerald-400 transition-colors"
                      />
                    </div>
                    <div className="space-y-2 max-h-[150px] overflow-y-auto pr-1 custom-scrollbar">

                      {/* Special Slot for Uploading TXT */}
                      <div className="relative group border-2 border-dashed border-slate-200 rounded-lg p-2 hover:border-emerald-400 hover:bg-emerald-50 transition-all cursor-pointer flex items-center justify-center gap-2 text-slate-400 hover:text-emerald-600">
                        <input
                          type="file"
                          accept=".txt"
                          className="absolute inset-0 opacity-0 cursor-pointer"
                          onChange={(e) => {
                            if (e.target.files?.[0]) {
                              const file = e.target.files[0];
                              const formData = new FormData();
                              formData.append('requirements_pdf', file);
                              formData.append('extraction_name', file.name.replace('.txt', ''));
                              processModule('requirements', formData).then(() => fetchProcessedRequirements());
                            }
                          }}
                        />
                        <span className="text-xs font-bold uppercase tracking-wider">+ Carica TXT Pronto</span>
                      </div>

                      {processedRequirements
                        .filter(req => req.name.toLowerCase().includes(requirementsSearch.toLowerCase()))
                        .map((req, idx) => {
                          const isSelected = selectedRequirement?.path === req.path;
                          return (
                            <div key={idx} className={`flex items-center justify-between p-2 rounded-lg border text-sm group transition-colors ${isSelected ? 'bg-emerald-50 border-emerald-500 ring-1 ring-emerald-500' : 'bg-white border-slate-200 hover:border-emerald-300'}`}>
                              <div className="flex items-center gap-2 overflow-hidden cursor-pointer flex-1" onClick={() => handleSelectRequirement(req)}>
                                {isSelected ? (
                                  <CheckSquare size={16} className="text-emerald-600 flex-shrink-0" />
                                ) : (
                                  <Square size={16} className="text-slate-300 group-hover:text-emerald-400 flex-shrink-0" />
                                )}
                                <span className={`truncate font-medium ${isSelected ? 'text-emerald-900' : 'text-slate-700'}`} title={req.name}>{req.name}</span>
                              </div>
                              <div className="flex gap-1 items-center">
                                <button
                                  onClick={() => handleViewRequirements(req)}
                                  className="p-1 text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded"
                                  title="Visualizza"
                                >
                                  <Eye size={14} />
                                </button>
                                <button
                                  onClick={() => handleDownloadRequirements(req)}
                                  className="p-1 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded"
                                  title="Scarica"
                                >
                                  <Download size={14} />
                                </button>
                                <div className="w-px h-3 bg-slate-200 mx-1"></div>
                                <button
                                  onClick={() => handleDeleteRequirement(req)}
                                  className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded"
                                  title="Elimina"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Upload Zone 2: Internal Docs (Aziendali) */}
            <div className="glass-card p-8 rounded-3xl transition-transform hover:-translate-y-1 duration-300">
              <div key={isAnnexMode ? 'annex-docs' : 'std-docs'} className="animate-fade-in">
                <FileUpload
                  title={isAnnexMode ? "Documenti addizionali" : "2. Documenti Aziendali"}
                  description={isAnnexMode ? "Carica annex, FAQ o allegati extra." : "Policy interne, manuali operativi, procedure."}
                  files={internalDocsFiles}
                  onUpload={(f) => handleUpload(f, 'internal_docs')}
                  onRemove={(i) => handleRemove(i, 'internal_docs')}
                  theme="indigo"
                  accept=".pdf,.doc,.docx,.txt"
                />

                {/* Processed Internal Docs List */}
                {!isAnnexMode && (
                  <div className="mt-6 border-t border-slate-100 pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Documenti Elaborati</h5>
                      <input
                        type="text"
                        placeholder="Cerca..."
                        value={internalDocsSearch}
                        onChange={(e) => setInternalDocsSearch(e.target.value)}
                        className="text-xs border border-slate-200 rounded-md px-2 py-1 w-24 focus:outline-none focus:border-indigo-400 transition-colors"
                      />
                    </div>
                    <div className="space-y-2 max-h-[150px] overflow-y-auto pr-1 custom-scrollbar">
                      {processedInternalDocs.length === 0 && (
                        <p className="text-xs text-slate-400 italic">Nessun documento elaborato.</p>
                      )}
                      {processedInternalDocs
                        .filter(chunk => chunk.name.toLowerCase().includes(internalDocsSearch.toLowerCase()))
                        .map((chunk, idx) => {
                          const isSelected = selectedChunks.has(chunk.path);
                          return (
                            <div key={idx} className={`flex items-center justify-between p-2 rounded-lg border text-sm group transition-colors ${isSelected ? 'bg-indigo-50 border-indigo-500 ring-1 ring-indigo-500' : 'bg-white border-slate-200 hover:border-indigo-300'}`}>
                              <div className="flex items-center gap-2 overflow-hidden cursor-pointer flex-1" onClick={() => toggleChunkSelection(chunk.path)}>
                                {isSelected ? (
                                  <CheckSquare size={16} className="text-indigo-600 flex-shrink-0" />
                                ) : (
                                  <Square size={16} className="text-slate-300 group-hover:text-indigo-400 flex-shrink-0" />
                                )}
                                <span className={`truncate font-medium ${isSelected ? 'text-indigo-900' : 'text-slate-700'}`} title={chunk.name}>{chunk.name}</span>
                              </div>
                              <button
                                onClick={() => handleDeleteChunk(chunk)}
                                className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded"
                                title="Elimina"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="mt-12 flex flex-col items-center justify-center">
            {error && (
              <div className="mb-6 flex items-center gap-2 text-red-600 bg-red-50 px-4 py-2 rounded-lg border border-red-100 animate-slide-up">
                <AlertCircle size={18} />
                <span className="text-sm font-medium">{error}</span>
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-4">
              {isAnnexMode ? (
                <button
                  onClick={runAnnexProcessing}
                  disabled={requirementsFiles.length === 0 || internalDocsFiles.length === 0}
                  className={`group relative px-8 py-4 rounded-2xl font-bold text-lg shadow-xl transition-all duration-300 ${requirementsFiles.length === 0 || internalDocsFiles.length === 0 ? 'bg-slate-800 text-slate-500 cursor-not-allowed opacity-50' : 'bg-indigo-600 text-white hover:bg-indigo-500 hover:shadow-indigo-500/20 hover:scale-105'}`}
                >
                  <span className="relative z-10 flex items-center gap-3">
                    <Sparkles size={20} className="text-indigo-200" />
                    Rielabora
                  </span>
                </button>
              ) : (
                <>
                  <button
                    onClick={runRequirementsExtraction}
                    disabled={isAnalyzing || requirementsFiles.length === 0}
                    className={`group relative px-6 py-4 rounded-2xl font-bold text-base shadow-lg transition-all duration-300 border-2 ${isAnalyzing || requirementsFiles.length === 0 ? 'border-slate-100 bg-slate-50 text-slate-300 cursor-not-allowed' : 'border-emerald-100 bg-white text-emerald-600 hover:border-emerald-200 hover:bg-emerald-50'}`}
                  >
                    <span className="relative z-10 flex items-center gap-2">
                      <BookOpen size={20} />
                      Estrai Requisiti ({requirementsFiles.length})
                    </span>
                  </button>

                  <button
                    onClick={runInternalDocsProcessing}
                    disabled={isAnalyzing || internalDocsFiles.length === 0}
                    className={`group relative px-6 py-4 rounded-2xl font-bold text-base shadow-lg transition-all duration-300 border-2 ${isAnalyzing || internalDocsFiles.length === 0 ? 'border-slate-100 bg-slate-50 text-slate-300 cursor-not-allowed' : 'border-indigo-100 bg-white text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50'}`}
                  >
                    <span className="relative z-10 flex items-center gap-2">
                      <Settings size={20} />
                      Elabora Documenti ({internalDocsFiles.length})
                    </span>
                  </button>

                  <button
                    onClick={runFullAnalysis}
                    disabled={isAnalyzing || selectedChunks.size === 0 || !selectedRequirement}
                    className={`group relative px-8 py-4 rounded-2xl font-bold text-lg shadow-xl transition-all duration-300 ${isAnalyzing || selectedChunks.size === 0 || !selectedRequirement ? 'bg-slate-800 text-slate-500 cursor-not-allowed opacity-50' : 'bg-slate-900 text-white hover:bg-slate-800 hover:shadow-brand-500/20 hover:scale-105'}`}
                  >
                    <span className="relative z-10 flex items-center gap-3">
                      {isAnalyzing ? 'Analisi in corso...' : 'Avvia Analisi Gap'}
                      {!isAnalyzing && <PlayCircle size={20} className="text-brand-400" />}
                    </span>
                  </button>
                </>
              )}
            </div>

            <div className="mt-4 flex flex-col sm:flex-row gap-4 items-center">
              <button
                onClick={() => setShowHistory(true)}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-full text-slate-600 font-bold hover:bg-slate-50 hover:text-brand-600 transition-all shadow-sm"
              >
                <History size={18} />
                Analisi Effettuate
              </button>

              <button
                onClick={() => setIsAnnexMode(!isAnnexMode)}
                className={`flex items-center gap-2 px-4 py-2 rounded-full font-bold transition-all shadow-sm border ${isAnnexMode ? 'bg-indigo-100 text-indigo-700 border-indigo-200' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}
              >
                <FileText size={18} />
                {isAnnexMode ? "Modalità Annex Attiva" : "Hai un annex o faq?"}
              </button>
            </div>

            <p className="mt-4 text-sm text-slate-400 font-medium flex items-center gap-1.5">
              <CheckCircle2 size={14} className="text-emerald-500" />
              Secure Processing via Google Gemini
            </p>
          </div>
        </div>

        {/* Progress Overlay */}
        {(isAnalyzing || isWorkflowActive) && activeStatus && (
          <ProcessingStatus
            status={activeStatus.status}
            message={activeStatus.message}
            progress={activeStatus.progress}
          />
        )}

        {/* Viewing Requirements */}
        {viewingRequirements && !results.length && (
          <div ref={resultsRef}>
            <RequirementsViewer
              requirements={viewingRequirements.requirements}
              title={viewingRequirements.title}
              onDownload={() => window.location.href = `${process.env.REACT_APP_API_URL}/api/download-requirements-list?file=${encodeURIComponent(viewingRequirements.path)}`}
            />
          </div>
        )}

        {/* Results Section */}
        {results.length > 0 && (
          <div className="relative">
            <ResultsTable results={results} excelPath={excelPath} />
          </div>
        )}

        {showHistory && (
          <AnalysisHistory
            onSelectAnalysis={handleSelectAnalysis}
            onClose={() => setShowHistory(false)}
          />
        )}

        <ConfirmationModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ ...deleteModal, isOpen: false })}
          onConfirm={executeDelete}
          title={deleteModal.title}
          message={deleteModal.message}
          itemName={deleteModal.item?.name}
        />

      </main>

      {/* Footer */}
      {/* <footer className="py-10 border-t border-slate-200 bg-white/40">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-slate-400 text-sm font-medium">
            &copy; 2025 Lutech Platform. All rights reserved. Powered by Gemini Enterprise
          </p>
        </div>
      </footer> */}

    </div>
  );
}

export default App;