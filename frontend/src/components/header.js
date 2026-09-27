import React, { useState, useEffect } from 'react';
import ResultsTable from './ResultsTable';
import XlsxViewer from './XlsxViewer';
import Logo from '../assets/logo.png';

const Header = () => {
    const [existingResults, setExistingResults] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [showRequirementsModal, setShowRequirementsModal] = useState(false);
    const [showExplorer, setShowExplorer] = useState(false);
    const [showXlsxViewer, setShowXlsxViewer] = useState(false);
    const [fullResults, setFullResults] = useState([]);
    const [filteredResults, setFilteredResults] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage] = useState(50);

    // New state for requirements
    const [requirements, setRequirements] = useState([]);
    const [requirementsLoading, setRequirementsLoading] = useState(false);
    const [requirementsSearchTerm, setRequirementsSearchTerm] = useState('');
    const [filteredRequirements, setFilteredRequirements] = useState([]);
    const [requirementsCurrentPage, setRequirementsCurrentPage] = useState(1);
    const [requirementsPerPage] = useState(12);
    useEffect(() => {
        console.log('requirementsPerPage:', requirementsPerPage);
    }, [requirementsPerPage]);

    // New state for requirement file selection
    const [showRequirementSelection, setShowRequirementSelection] = useState(false);
    const [availableRequirementFiles, setAvailableRequirementFiles] = useState([]);
    const [selectedRequirementFile, setSelectedRequirementFile] = useState('');
    const [requirementsExplicitlyRequested, setRequirementsExplicitlyRequested] = useState(false);

    // New state for internal documents exploration
    const [showInternalDocsModal, setShowInternalDocsModal] = useState(false);
    const [internalDocuments, setInternalDocuments] = useState([]);
    const [internalDocsLoading, setInternalDocsLoading] = useState(false);

    // New state for mapping file selection
    const [showMappingSelection, setShowMappingSelection] = useState(false);
    const [availableMappings, setAvailableMappings] = useState([]);
    const [selectedMapping, setSelectedMapping] = useState('');
    const [mappingSelectionMode, setMappingSelectionMode] = useState('json'); // 'json' or 'excel'

    // Check for existing results on component mount
    useEffect(() => {
        checkExistingResults();
    }, []);

    // Filter results when search term changes
    useEffect(() => {
        if (searchTerm) {
            const filtered = fullResults.filter(item =>
                Object.values(item).some(value =>
                    value && value.toString().toLowerCase().includes(searchTerm.toLowerCase())
                )
            );
            setFilteredResults(filtered);
        } else {
            setFilteredResults(fullResults);
        }
        setCurrentPage(1);
    }, [searchTerm, fullResults]);

    // Filter requirements when search term changes
    useEffect(() => {
        if (requirementsSearchTerm) {
            const filtered = requirements.filter(req =>
                req.requisito.toLowerCase().includes(requirementsSearchTerm.toLowerCase()) ||
                req.domanda_audit.toLowerCase().includes(requirementsSearchTerm.toLowerCase()) ||
                req.file_sorgente.toLowerCase().includes(requirementsSearchTerm.toLowerCase())
            );
            setFilteredRequirements(filtered);
        } else {
            setFilteredRequirements(requirements);
        }
        setRequirementsCurrentPage(1);
    }, [requirementsSearchTerm, requirements]);

    const checkExistingResults = async () => {
        try {
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/check-existing-results`);
            const data = await response.json();
            if (data.exists) {
                setExistingResults(data);
            }
        } catch (error) {
            console.error('Error checking existing results:', error);
        }
    };

    const fetchRequirements = async (requirementFilePath = null) => {
        setRequirementsLoading(true);
        try {
            let url = `${process.env.REACT_APP_API_URL}/api/get-requirements-list`;
            if (requirementFilePath) {
                url += `?file=${encodeURIComponent(requirementFilePath)}`;
            }

            const response = await fetch(url);
            const data = await response.json();
            if (data.success) {
                setRequirements(data.requirements);
                setFilteredRequirements(data.requirements);
            } else {
                console.error('Error fetching requirements:', data.error);
            }
        } catch (error) {
            console.error('Error fetching requirements:', error);
        } finally {
            setRequirementsLoading(false);
        }
    };

    const fetchAvailableRequirementFiles = async () => {
        try {
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-requirements`);
            const data = await response.json();
            setAvailableRequirementFiles(data);
        } catch (error) {
            console.error('Error fetching available requirement files:', error);
        }
    };

    const handleShowRequirements = async () => {
        setRequirementsExplicitlyRequested(true);
        await fetchAvailableRequirementFiles();
        // We need to check the files after they're fetched, so we'll handle this in useEffect
    };

    // Use effect to handle the requirement files after they're fetched (only when explicitly requested)
    useEffect(() => {
        // Only trigger modal if files were explicitly requested (not on initial load)
        if (requirementsExplicitlyRequested) {
            if (availableRequirementFiles.length === 1 && showRequirementSelection === false && showRequirementsModal === false) {
                // If only one file available, select it automatically
                setSelectedRequirementFile(availableRequirementFiles[0].path);
                fetchRequirements(availableRequirementFiles[0].path);
                setShowRequirementsModal(true);
            } else if (availableRequirementFiles.length > 1) {
                // Show selection modal for multiple files
                setShowRequirementSelection(true);
            } else if (availableRequirementFiles.length === 0) {
                // Show selection modal with "no files" message
                setShowRequirementSelection(true);
            }
        }
    }, [availableRequirementFiles, requirementsExplicitlyRequested]);

    const handleRequirementFileSelected = async () => {
        if (selectedRequirementFile) {
            setShowRequirementSelection(false);
            await fetchRequirements(selectedRequirementFile);
            setShowRequirementsModal(true);
        }
    };

    const handleDownloadRequirements = () => {
        window.open(`${process.env.REACT_APP_API_URL}/api/download-requirements-list`, '_blank');
    };

    const fetchInternalDocuments = async () => {
        setInternalDocsLoading(true);
        try {
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/get-internal-docs-list`);
            const data = await response.json();
            if (data.success) {
                setInternalDocuments(data.documents);
            } else {
                console.error('Error fetching internal documents:', data.error);
                setInternalDocuments([]);
            }
        } catch (error) {
            console.error('Error fetching internal documents:', error);
            setInternalDocuments([]);
        } finally {
            setInternalDocsLoading(false);
        }
    };

    const handleShowInternalDocs = async () => {
        await fetchInternalDocuments();
        setShowInternalDocsModal(true);
    };

    const handleDeleteInternalDoc = async (docId) => {
        if (window.confirm('Sei sicuro di voler eliminare questo documento? Questa azione non può essere annullata.')) {
            try {
                const response = await fetch(`${process.env.REACT_APP_API_URL}/api/delete-internal-doc/${docId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                if (data.success) {
                    // Refresh the list
                    await fetchInternalDocuments();
                    alert('Documento eliminato con successo');
                } else {
                    alert('Errore durante l\'eliminazione: ' + data.error);
                }
            } catch (error) {
                console.error('Error deleting document:', error);
                alert('Errore durante l\'eliminazione del documento');
            }
        }
    };

    const loadFullResults = async () => {
        try {
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/get-full-results`);
            const data = await response.json();
            setFullResults(data);
            setFilteredResults(data);
        } catch (error) {
            console.error('Error loading full results:', error);
        }
    };

    const handleMappingSelected = async () => {
        if (!selectedMapping) return;

        setShowMappingSelection(false);

        if (mappingSelectionMode === 'json') {
            // Load results for explorer
            try {
                const response = await fetch(`${process.env.REACT_APP_API_URL}/api/get-mapping-results?file=${encodeURIComponent(selectedMapping)}`);
                const data = await response.json();
                setFullResults(data);
                setFilteredResults(data);
                setShowExplorer(true);
            } catch (error) {
                console.error('Error loading mapping results:', error);
                alert('Errore nel caricamento dei risultati');
            }
        } else if (mappingSelectionMode === 'excel') {
            // Set the selected Excel file for XlsxViewer
            setShowXlsxViewer(true);
        }
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setShowRequirementsModal(false);
        setShowRequirementSelection(false);
        setRequirementsSearchTerm('');
        setRequirementsCurrentPage(1);
        setSelectedRequirementFile('');
        setRequirementsExplicitlyRequested(false);
        setShowInternalDocsModal(false);
        setShowMappingSelection(false);
        setSelectedMapping('');
        setMappingSelectionMode('json');
    };

    const fetchAvailableMappings = async () => {
        try {
            const response = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-mappings`);
            const data = await response.json();
            setAvailableMappings(data);
        } catch (error) {
            console.error('Error fetching available mappings:', error);
        }
    };

    const handleShowExplorer = async () => {
        await fetchAvailableMappings();
        setMappingSelectionMode('json');
        setShowMappingSelection(true);
    };

    const handleCloseExplorer = () => {
        setShowExplorer(false);
        setSearchTerm('');
        setCurrentPage(1);
    };

    const handleShowXlsxViewer = async () => {
        await fetchAvailableMappings();
        setMappingSelectionMode('excel');
        setShowMappingSelection(true);
    };

    const handleCloseXlsxViewer = () => {
        setShowXlsxViewer(false);
    };

    // Pagination
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = filteredResults.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(filteredResults.length / itemsPerPage);

    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    return (
        <>
            <nav className="navbar-main">
                <div className="navbar-overlay">
                    <img src={Logo} alt="Logo" className="logo" />
                    <h1 className="app-title">AI Compliance<p className='subtitle'>a feature of Lutech GRC</p></h1>
                </div>

                <div className="nav-menu-items">
                    <button className="nav-menu-button" onClick={handleShowRequirements}>Requisiti Estratti</button>
                    <button className="nav-menu-button" onClick={handleShowInternalDocs}>Documenti Estratti</button>
                    <button className="nav-menu-button" onClick={handleShowExplorer}>Esplora Risultati</button>
                    <button className="nav-menu-button" onClick={handleShowXlsxViewer}>Scarica Risultati</button>

                </div>
            </nav>

            {/* Modal for Requirement File Selection */}
            {showRequirementSelection && (
                <div className="requirements-modal-overlay">
                    <div className="requirements-modal" style={{ maxWidth: '600px' }}>
                        <div className="requirements-modal-header">
                            <button
                                onClick={handleCloseModal}
                                className="requirements-modal-close"
                            >
                                🏠︎
                            </button>

                            <h2 className="requirements-modal-title">
                                Seleziona Estrazione Requisiti
                            </h2>
                            <p className="requirements-modal-subtitle">
                                Scegli quale estrazione di requisiti visualizzare
                            </p>
                        </div>

                        <div className="requirements-modal-content" style={{ padding: '20px' }}>
                            {availableRequirementFiles.length === 0 ? (
                                <div className="requirements-empty-state">
                                    <h3 className="requirements-empty-title">📄 Nessuna estrazione trovata</h3>
                                    <p className="requirements-empty-description">
                                        Non sono state trovate estrazioni di requisiti.
                                        Elabora prima un documento nella sezione "Estrazione Requisiti".
                                    </p>
                                </div>
                            ) : (
                                <div className="requirement-file-selection">
                                    <div className="file-selection-list">
                                        {availableRequirementFiles.map((file, index) => (
                                            <div
                                                key={index}
                                                className={`requirement-file-option ${selectedRequirementFile === file.path ? 'selected' : ''}`}
                                                onClick={() => setSelectedRequirementFile(file.path)}
                                            >
                                                <div className="requirement-file-info">
                                                    <div className="requirement-file-name">
                                                        <strong>{file.name}</strong>
                                                    </div>
                                                    <div className="requirement-file-details">
                                                        <span className="requirement-file-location">{file.location}</span>
                                                        {file.metadata?.total_requirements && (
                                                            <span className="requirement-count">
                                                                {file.metadata.total_requirements} requisiti
                                                            </span>
                                                        )}
                                                        {file.metadata?.processed_date && (
                                                            <span className="requirement-date">
                                                                {new Date(file.metadata.processed_date).toLocaleDateString('it-IT')}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="requirement-file-radio">
                                                    <input
                                                        type="radio"
                                                        name="requirement-file"
                                                        checked={selectedRequirementFile === file.path}
                                                        onChange={() => setSelectedRequirementFile(file.path)}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    <div className="requirement-selection-actions">
                                        <button
                                            className="requirement-cancel-btn"
                                            onClick={handleCloseModal}
                                        >
                                            Annulla
                                        </button>
                                        <button
                                            className="requirement-select-btn"
                                            onClick={handleRequirementFileSelected}
                                            disabled={!selectedRequirementFile}
                                        >
                                            Visualizza Requisiti
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Modal for Requirements */}
            {showRequirementsModal && (
                <div className="requirements-modal-overlay">
                    <div className="requirements-modal">
                        {/* Header */}
                        <div className="requirements-modal-header">
                            <button
                                onClick={handleCloseModal}
                                className="requirements-modal-close"
                            >
                                🏠︎
                            </button>

                            <h2 className="requirements-modal-title">
                                Lista Requisiti Estratti
                            </h2>
                            <p className="requirements-modal-subtitle">
                                {requirementsLoading ? 'Caricamento...' : `${filteredRequirements.length} requisiti trovati`}
                            </p>
                        </div>

                        {/* Controls */}
                        <div className="requirements-modal-controls">
                            <div className="requirements-controls-container">
                                <div className="requirements-search-group">
                                    <input
                                        type="text"
                                        placeholder="Cerca nei requisiti..."
                                        value={requirementsSearchTerm}
                                        onChange={(e) => setRequirementsSearchTerm(e.target.value)}
                                        className="requirements-search-input"
                                    />
                                    <span className="requirements-counter">
                                        {filteredRequirements.length} / {requirements.length} requisiti
                                    </span>
                                </div>

                                <button
                                    onClick={handleDownloadRequirements}
                                    disabled={requirementsLoading || requirements.length === 0}
                                    className="requirements-download-btn"
                                    title="Scarica Lista Requisiti"

                                >
                                    Scarica Lista
                                </button>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="requirements-modal-content">
                            {requirementsLoading ? (
                                <div className="requirements-loading">
                                    <div className="requirements-loading-spinner"></div>
                                    <p className="requirements-loading-text">Caricamento requisiti...</p>
                                </div>
                            ) : filteredRequirements.length === 0 ? (
                                <div className="requirements-empty-state">
                                    <h3 className="requirements-empty-title">
                                        {requirements.length === 0 ? '📄 Nessun requisito trovato' : '🔍 Nessun risultato'}
                                    </h3>
                                    <p className="requirements-empty-description">
                                        {requirements.length === 0
                                            ? 'Non sono stati trovati requisiti nel sistema. Assicurati di aver elaborato i documenti.'
                                            : 'Prova con termini di ricerca diversi.'
                                        }
                                    </p>
                                </div>
                            ) : (
                                <div className="requirements-list">
                                    {(() => {
                                        const indexOfLastReq = requirementsCurrentPage * requirementsPerPage;
                                        const indexOfFirstReq = indexOfLastReq - requirementsPerPage;
                                        const currentRequirements = filteredRequirements.slice(indexOfFirstReq, indexOfLastReq);
                                        const totalReqPages = Math.ceil(filteredRequirements.length / requirementsPerPage);

                                        return (
                                            <>
                                                <div className="requirements-grid">
                                                    {currentRequirements.map((req, index) => (
                                                        <div key={indexOfFirstReq + index} className="requirement-card">
                                                            <div className="requirement-header">
                                                                <span className="requirement-id">#{req.numero || indexOfFirstReq + index + 1}</span>
                                                                {req.file_sorgente && (
                                                                    <div className="requirement-source-info">
                                                                        <div>{req.file_sorgente}</div>
                                                                        {req.chunk_sorgente && <div>Chunk: {req.chunk_sorgente}</div>}
                                                                    </div>
                                                                )}
                                                            </div>

                                                            {req.requisito && (
                                                                <div className="requirement-section">
                                                                    <h4 className="requirement-section-title">
                                                                        Requisito
                                                                    </h4>
                                                                    <p className="requirement-text">{req.requisito}</p>
                                                                </div>
                                                            )}

                                                            {req.domanda_audit && (
                                                                <div className="requirement-section">
                                                                    <h4 className="requirement-section-title">
                                                                        Domanda Audit
                                                                    </h4>
                                                                    <p className="requirement-audit-answer">
                                                                        {req.domanda_audit}
                                                                    </p>
                                                                </div>
                                                            )}

                                                            {/* If it's just a simple string requirement */}
                                                            {typeof req === 'string' && (
                                                                <p className="requirement-text">{req}</p>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>

                                                {totalReqPages > 1 && (
                                                    <div className="requirements-pagination">
                                                        <button
                                                            onClick={() => setRequirementsCurrentPage(requirementsCurrentPage - 1)}
                                                            disabled={requirementsCurrentPage === 1}
                                                            className="requirements-page-btn"
                                                        >
                                                            Precedente
                                                        </button>

                                                        <span className="requirements-page-info">
                                                            Pagina {requirementsCurrentPage} di {totalReqPages}
                                                        </span>

                                                        <button
                                                            onClick={() => setRequirementsCurrentPage(requirementsCurrentPage + 1)}
                                                            disabled={requirementsCurrentPage === totalReqPages}
                                                            className="requirements-page-btn"
                                                        >
                                                            Successiva
                                                        </button>
                                                    </div>
                                                )}
                                            </>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Explorer Modal */}
            {showExplorer && (
                <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <div style={{ backgroundColor: 'white', padding: '20px', borderRadius: '0px', width: '95%', height: '90%', overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
                        <button onClick={handleCloseExplorer} style={{ position: 'absolute', top: '10px', right: '15px', backgroundColor: 'transparent', border: 'none', fontSize: '24px', cursor: 'pointer', zIndex: 10 }}>×</button>

                        <div style={{ marginBottom: '20px', paddingRight: '40px' }}>
                            <h2>Esplora Risultati Completi</h2>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '15px' }}>
                                <input
                                    type="text"
                                    placeholder="Cerca nei risultati..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    style={{ padding: '8px 12px', border: '1px solid #ddd', borderRadius: '4px', width: '300px' }}
                                />
                                <span style={{ color: '#666' }}>
                                    Mostrando {filteredResults.length} di {fullResults.length} risultati
                                </span>
                            </div>
                        </div>

                        <div style={{ flex: 1, overflow: 'auto', marginBottom: '15px' }}>
                            <ResultsTable results={currentItems} />
                        </div>

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px', borderTop: '1px solid #eee', paddingTop: '15px' }}>
                                <button
                                    onClick={() => paginate(currentPage - 1)}
                                    disabled={currentPage === 1}
                                    style={{ padding: '5px 10px', border: '1px solid #ddd', backgroundColor: currentPage === 1 ? '#f5f5f5' : 'white', cursor: currentPage === 1 ? 'not-allowed' : 'pointer' }}
                                >
                                    Precedente
                                </button>

                                <span style={{ margin: '0 10px' }}>
                                    Pagina {currentPage} di {totalPages}
                                </span>

                                <button
                                    onClick={() => paginate(currentPage + 1)}
                                    disabled={currentPage === totalPages}
                                    style={{ padding: '5px 10px', border: '1px solid #ddd', backgroundColor: currentPage === totalPages ? '#f5f5f5' : 'white', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer' }}
                                >
                                    Successiva
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Internal Documents Modal */}
            {showInternalDocsModal && (
                <div className="requirements-modal-overlay">
                    <div className="requirements-modal" style={{ maxWidth: '900px', maxHeight: '80vh' }}>
                        <div className="requirements-modal-header">
                            <button
                                onClick={handleCloseModal}
                                className="requirements-modal-close"
                            >
                                ✕
                            </button>

                            <h2 className="requirements-modal-title">
                                Documenti Interni Processati
                            </h2>
                            <p className="requirements-modal-subtitle">
                                Esplora, modifica ed elimina i documenti interni già processati
                            </p>
                        </div>

                        <div className="requirements-modal-content" style={{ padding: '20px', overflow: 'auto' }}>
                            {internalDocsLoading ? (
                                <div style={{ textAlign: 'center', padding: '40px' }}>
                                    <p>Caricamento documenti...</p>
                                </div>
                            ) : internalDocuments.length === 0 ? (
                                <div className="requirements-empty-state">
                                    <h3 className="requirements-empty-title">📁 Nessun documento trovato</h3>
                                    <p className="requirements-empty-description">
                                        Non sono stati trovati documenti interni processati.
                                        Carica prima i documenti nella sezione "Documentazione da Analizzare".
                                    </p>
                                </div>
                            ) : (
                                <div className="internal-docs-list">
                                    <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                        <h4 style={{ margin: '0 0 10px 0', color: '#495057' }}>
                                            Statistiche
                                        </h4>
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
                                            <div style={{ textAlign: 'center' }}>
                                                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#007bff' }}>
                                                    {internalDocuments.length}
                                                </div>
                                                <div style={{ fontSize: '14px', color: '#6c757d' }}>
                                                    Documenti Totali
                                                </div>
                                            </div>
                                            <div style={{ textAlign: 'center' }}>
                                                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#28a745' }}>
                                                    {internalDocuments.reduce((sum, doc) => sum + (doc.chunk_count || 0), 0)}
                                                </div>
                                                <div style={{ fontSize: '14px', color: '#6c757d' }}>
                                                    Chunks Totali
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="internal-docs-grid" style={{ display: 'grid', gap: '15px' }}>
                                        {internalDocuments.map((doc, index) => (
                                            <div
                                                key={doc.id}
                                                className="internal-doc-card"
                                                style={{
                                                    border: '1px solid #dee2e6',
                                                    borderRadius: '8px',
                                                    padding: '20px',
                                                    backgroundColor: doc.exists ? '#fff' : '#f8f9fa',
                                                    position: 'relative'
                                                }}
                                            >
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
                                                    <div style={{ flex: 1 }}>
                                                        <h4 style={{ margin: '0 0 8px 0', fontSize: '18px', color: '#343a40' }}>
                                                            📄 {doc.display_name}
                                                        </h4>
                                                        <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#6c757d' }}>
                                                            <strong>File originale:</strong> {doc.original_name}
                                                        </p>
                                                        <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#6c757d' }}>
                                                            <strong>Data elaborazione:</strong> {new Date(doc.processed_date).toLocaleDateString('it-IT', {
                                                                year: 'numeric',
                                                                month: 'long',
                                                                day: 'numeric',
                                                                hour: '2-digit',
                                                                minute: '2-digit'
                                                            })}
                                                        </p>
                                                        {doc.exists && (
                                                            <>
                                                                <p style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#28a745' }}>
                                                                    <strong>Chunks estratti:</strong> {doc.chunk_count || 0}
                                                                </p>
                                                                <p style={{ margin: '0', fontSize: '14px', color: '#6c757d' }}>
                                                                    <strong>Dimensione file:</strong> {((doc.file_size || 0) / 1024).toFixed(2)} KB
                                                                </p>
                                                            </>
                                                        )}
                                                        {!doc.exists && (
                                                            <p style={{ margin: '0', fontSize: '14px', color: '#dc3545' }}>
                                                                ⚠️ File chunks non trovato
                                                            </p>
                                                        )}
                                                    </div>

                                                    <div style={{ display: 'flex', gap: '8px', marginLeft: '15px' }}>
                                                        {doc.exists && (
                                                            <button
                                                                style={{
                                                                    padding: '6px 12px',
                                                                    fontSize: '12px',
                                                                    border: '1px solid #007bff',
                                                                    backgroundColor: '#007bff',
                                                                    color: 'white',
                                                                    borderRadius: '4px',
                                                                    cursor: 'pointer'
                                                                }}
                                                                onClick={() => {
                                                                    // TODO: Implement view/edit functionality
                                                                    alert('DA IMPLEMENTARE: Funzionalità di visualizzazione/modifica del documento interno'); //TODO
                                                                }}
                                                            >
                                                                Visualizza
                                                            </button>
                                                        )}
                                                        <button
                                                            style={{
                                                                padding: '6px 12px',
                                                                fontSize: '12px',
                                                                border: '1px solid #dc3545',
                                                                backgroundColor: '#dc3545',
                                                                color: 'white',
                                                                borderRadius: '4px',
                                                                cursor: 'pointer'
                                                            }}
                                                            onClick={() => handleDeleteInternalDoc(doc.id)}
                                                        >
                                                            Elimina
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Mapping Selection Modal */}
            {showMappingSelection && (
                <div className="requirements-modal-overlay">
                    <div className="requirements-modal" style={{ maxWidth: '600px' }}>
                        <div className="requirements-modal-header">
                            <button
                                onClick={handleCloseModal}
                                className="requirements-modal-close"
                            >
                                🏠︎
                            </button>

                            <h2 className="requirements-modal-title">
                                {mappingSelectionMode === 'json' ? 'Seleziona Risultati da Esplorare' : 'Seleziona Excel da Visualizzare'}
                            </h2>
                            <p className="requirements-modal-subtitle">
                                {mappingSelectionMode === 'json'
                                    ? 'Scegli quale mapping di allineamento esplorare'
                                    : 'Scegli quale file Excel visualizzare'
                                }
                            </p>
                        </div>

                        <div className="requirements-modal-content" style={{ padding: '20px' }}>
                            {availableMappings.length === 0 ? (
                                <div className="requirements-empty-state">
                                    <h3 className="requirements-empty-title">📊 Nessun mapping trovato</h3>
                                    <p className="requirements-empty-description">
                                        Non sono stati trovati risultati di allineamento.
                                        Completa prima un allineamento nella sezione "Allineamento Documentale".
                                    </p>
                                </div>
                            ) : (
                                <div className="requirement-file-selection">
                                    <div className="file-selection-list">
                                        {availableMappings
                                            .filter(mapping => mappingSelectionMode === 'json' ? mapping.has_json : mapping.has_excel)
                                            .map((mapping, index) => (
                                                <div
                                                    key={index}
                                                    className={`requirement-file-option ${selectedMapping === (mappingSelectionMode === 'json' ? mapping.json_path : mapping.excel_path) ? 'selected' : ''}`}
                                                    onClick={() => setSelectedMapping(mappingSelectionMode === 'json' ? mapping.json_path : mapping.excel_path)}
                                                >
                                                    <div className="requirement-file-info">
                                                        <div className="requirement-file-name">
                                                            <strong>{mapping.name}</strong>
                                                            {mappingSelectionMode === 'excel' && !mapping.has_excel &&
                                                                <span style={{ color: '#dc3545', fontSize: '12px', marginLeft: '10px' }}>
                                                                    (Excel non disponibile)
                                                                </span>
                                                            }
                                                        </div>
                                                        <div className="requirement-file-details">
                                                            <span className="requirement-file-location">{mapping.location}</span>
                                                            {mapping.metadata?.processing_date && (
                                                                <span className="requirement-date">
                                                                    {new Date(mapping.metadata.processing_date).toLocaleDateString('it-IT')}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <div className="requirement-file-radio">
                                                        <input
                                                            type="radio"
                                                            name="mapping-file"
                                                            checked={selectedMapping === (mappingSelectionMode === 'json' ? mapping.json_path : mapping.excel_path)}
                                                            onChange={() => setSelectedMapping(mappingSelectionMode === 'json' ? mapping.json_path : mapping.excel_path)}
                                                            disabled={mappingSelectionMode === 'excel' && !mapping.has_excel}
                                                        />
                                                    </div>
                                                </div>
                                            ))}
                                    </div>

                                    <div className="requirement-selection-actions">
                                        <button
                                            className="requirement-cancel-btn"
                                            onClick={handleCloseModal}
                                        >
                                            Annulla
                                        </button>
                                        <button
                                            className="requirement-select-btn"
                                            onClick={handleMappingSelected}
                                            disabled={!selectedMapping}
                                        >
                                            {mappingSelectionMode === 'json' ? 'Esplora Risultati' : 'Scarica Risultati'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Excel Viewer */}
            <XlsxViewer
                isOpen={showXlsxViewer}
                onClose={handleCloseXlsxViewer}
                selectedExcelFile={mappingSelectionMode === 'excel' ? selectedMapping : null}
            />
        </>
    );
};

export default Header;