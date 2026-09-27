import React, { useState, useEffect } from 'react';
import ProcessingStatus from './ProcessingStatus';

const ModuleDetail = ({
  title,
  description,
  module,
  status,
  hasData,
  onProcess,
  inputType,
  inputLabel,
  inputName,
  requiresData,
  availableData
}) => {
  const [files, setFiles] = useState(null);
  const [extractionName, setExtractionName] = useState('');
  const [mappingName, setMappingName] = useState('');
  const [availableRequirements, setAvailableRequirements] = useState([]);
  const [availableChunks, setAvailableChunks] = useState([]);
  const [selectedRequirements, setSelectedRequirements] = useState('');
  const [selectedChunks, setSelectedChunks] = useState([]);
  const [previousMappingStatus, setPreviousMappingStatus] = useState('idle');

  // Load available files for mapping module
  useEffect(() => {
    if (module === 'mapping') {
      loadAvailableFiles();
    }
  }, [module]);

  // Monitor mapping status changes and show popup when completed
  useEffect(() => {
    if (module === 'mapping' && previousMappingStatus === 'processing' && status.status === 'completed') {
      alert('✅ Allineamento Documentale Completato!\n\n' + status.message);
    }
    if (module === 'mapping') {
      setPreviousMappingStatus(status.status);
    }
  }, [status.status, module, previousMappingStatus, status.message]);

  const loadAvailableFiles = async () => {
    try {
      // Load available requirements files
      const reqResponse = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-requirements`);
      const reqData = await reqResponse.json();
      setAvailableRequirements(reqData);

      // Load available chunk files
      const chunkResponse = await fetch(`${process.env.REACT_APP_API_URL}/api/get-available-chunks`);
      const chunkData = await chunkResponse.json();
      setAvailableChunks(chunkData);
    } catch (error) {
      console.error('Error loading available files:', error);
    }
  };

  const handleFileChange = (e) => {
    setFiles(e.target.files);
  };

  const handleRequirementsChange = (e) => {
    setSelectedRequirements(e.target.value);
  };

  const handleChunkChange = (e, chunkPath) => {
    if (e.target.checked) {
      setSelectedChunks([...selectedChunks, chunkPath]);
    } else {
      setSelectedChunks(selectedChunks.filter(path => path !== chunkPath));
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (module === 'mapping') {
      // For mapping module, send selected files with mapping name
      const mappingData = {
        requirements_file: selectedRequirements,
        chunk_files: selectedChunks,
        mapping_name: mappingName.trim() || 'Unnamed Mapping'
      };

      fetch(`${process.env.REACT_APP_API_URL}/api/process-mapping`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(mappingData)
      })
        .then(res => res.json())
        .then(data => {
          if (data.status === 'started') {
            onProcess(module, null); // Trigger status update
            setMappingName(''); // Reset name field
            setSelectedChunks([]); // Reset selected chunks
            setSelectedRequirements(''); // Reset selected requirements
          } else {
            throw new Error(data.error || 'Unknown error');
          }
        })
        .catch(error => {
          console.error('Error starting mapping:', error);
          alert('❌ Errore durante l\'avvio dell\'allineamento: ' + error.message);
        });
    } else {
      // For other modules, use form data with names
      const formData = new FormData();

      if (inputType === 'single' && files && files[0]) {
        formData.append(inputName, files[0]);
        // Add extraction name for requirements module
        if (module === 'requirements') {
          formData.append('extraction_name', extractionName.trim() || 'Unnamed Requirements');
        }
      } else if (inputType === 'multiple' && files) {
        for (let file of files) {
          formData.append(inputName, file);
        }
      }

      onProcess(module, formData);
      setFiles(null);
      setExtractionName('');
      e.target.reset();
    }
  };

  const canProcess = () => {
    if (module === 'mapping') {
      return selectedRequirements && selectedChunks.length > 0;
    }
    if (inputType === 'none') {
      return requiresData ? requiresData.every(req => availableData[req]) : true;
    }
    return files && files.length > 0;
  };

  const getStatusColor = () => {
    if (status.status === 'processing') return '#e5f321ff';
    if (status.status === 'completed') return '#4CAF50';
    if (status.status === 'error') return '#f44336';
    return 'black';
  };

  return (
    <div className="module-detail">
      <div className="detail-header">
        <p>{description}</p>
        {hasData && (
          <div className="data-status">
            <span className="data-badge">Dati disponibili</span>
          </div>
        )}
      </div>

      {status.status === 'processing' && (
        <ProcessingStatus
          status={status.status}
          step={status.step}
          progress={status.progress}
          message={status.message}
        />
      )}

      {status.status !== 'processing' && (
        <form onSubmit={handleSubmit} className="module-form">
          {inputType === 'single' && (
            <>
              <div className="name-input-group">
                <label htmlFor={`${module}-name`}>
                  {module === 'requirements' ? 'Nome Estrazione Requisiti:' : 'Nome:'}
                </label>
                <input
                  id={`${module}-name`}
                  type="text"
                  placeholder={module === 'requirements' ? 'Es: Requisiti ISO 9001' : 'Nome personalizzato'}
                  value={extractionName}
                  onChange={(e) => setExtractionName(e.target.value)}
                />
                <small className="field-hint">
                  Inserisci un nome per identificare facilmente questa estrazione
                </small>
              </div>

              <div className="file-input-group">
                <label htmlFor={`${module}-file`}>{inputLabel}</label>
                <input
                  id={`${module}-file`}
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  required
                />
              </div>
            </>
          )}

          {inputType === 'multiple' && (
            <div className="file-input-group">
              <label htmlFor={`${module}-files`}>{inputLabel}</label>
              <input
                id={`${module}-files`}
                type="file"
                accept=".pdf"
                multiple
                onChange={handleFileChange}
                required
              />
            </div>
          )}

          {module === 'mapping' && (
            <div className="mapping-file-selection">
              {/* Mapping Name Input */}
              <div className="name-input-group">
                <label htmlFor="mapping-name">Nome Allineamento Documentale:</label>
                <input
                  id="mapping-name"
                  type="text"
                  placeholder="Es: Allineamento ISO 9001 - Procedure Qualità"
                  value={mappingName}
                  onChange={(e) => setMappingName(e.target.value)}
                />
                <small className="field-hint">
                  Inserisci un nome per identificare facilmente questo allineamento documentale
                </small>
              </div>

              {/* Requirements Selection */}
              <div className="file-selection-group">
                <label>Selezione un file requisiti:</label>
                <select
                  value={selectedRequirements}
                  onChange={handleRequirementsChange}
                  required
                >
                  <option value="">Scegli un file requisiti...</option>
                  {availableRequirements.map((req, index) => (
                    <option key={index} value={req.path}>
                      {req.name} ({req.metadata?.total_requirements || 'Unknown'} requirements)
                    </option>
                  ))}
                </select>
              </div>

              {/* Chunks Selection */}
              <div className="file-selection-group">
                <label>Seleziona i documenti interni (seleziona uno o più):</label>
                <div className="chunks-selection">
                  {(() => {
                    // Remove duplicates based on normalized name
                    const normalizedMap = new Map();

                    availableChunks.forEach(chunk => {
                      // Skip chunking_summary files
                      if (chunk.name === 'chunking_summary' || chunk.chunk_count === 0) {
                        return;
                      }

                      // Normalize name: remove internal_{number}_ prefix and (legacy) suffix
                      let normalizedName = chunk.name
                        .replace(/^internal_\d+_/, '')
                        .replace(/\s*\(legacy\)\s*$/, '')
                        .replace(/_chunks_chunks$/, '')
                        .trim();

                      // If we already have this document, keep the most recent one
                      if (normalizedMap.has(normalizedName)) {
                        const existing = normalizedMap.get(normalizedName);
                        // Prefer internal_docs over chunks (legacy)
                        if (chunk.location === 'internal_docs/' && existing.location === 'chunks/') {
                          normalizedMap.set(normalizedName, chunk);
                        } else if (chunk.modified > existing.modified) {
                          normalizedMap.set(normalizedName, chunk);
                        }
                      } else {
                        normalizedMap.set(normalizedName, chunk);
                      }
                    });

                    // Sort by normalized name
                    const uniqueChunks = Array.from(normalizedMap.values()).sort((a, b) => {
                      const nameA = a.name
                        .replace(/^internal_\d+_/, '')
                        .replace(/\s*\(legacy\)\s*$/, '')
                        .toLowerCase();
                      const nameB = b.name
                        .replace(/^internal_\d+_/, '')
                        .replace(/\s*\(legacy\)\s*$/, '')
                        .toLowerCase();
                      return nameA.localeCompare(nameB);
                    });

                    return uniqueChunks.map((chunk, index) => {
                      // Display name without internal_ prefix and _chunks_chunks suffix
                      const displayName = chunk.name
                        .replace(/^internal_\d+_/, '')
                        .replace(/_chunks_chunks$/, '')
                        .replace(/\s*\(legacy\)\s*$/, '');

                      return (
                        <div key={index} className="chunk-item">
                          <input
                            type="checkbox"
                            id={`chunk-${index}`}
                            onChange={(e) => handleChunkChange(e, chunk.path)}
                            checked={selectedChunks.includes(chunk.path)}
                          />
                          <label htmlFor={`chunk-${index}`}>
                            <strong>{displayName}</strong>
                            <span className="chunk-info">
                              {chunk.modified} •
                              {chunk.chunk_count} chunks • {(chunk.size / 1024).toFixed(1)}KB
                              {chunk.location && ` • ${chunk.location}`}
                            </span>
                          </label>
                        </div>
                      );
                    });
                  })()}
                </div>
              </div>

              {selectedChunks.length > 0 && (
                <div className="selection-summary">
                  Selected: {selectedChunks.length} chunk files
                </div>
              )}
            </div>
          )}

          {inputType === 'none' && requiresData && module !== 'mapping' && (
            <div className="requirements-check">
              <h4>Required Data:</h4>
              <ul>
                {requiresData.map(req => (
                  <li key={req} className={availableData[req] ? 'available' : 'missing'}>
                    {req.replace('_', ' ').toUpperCase()}: {availableData[req] ? '[OK]' : '[MISSING]'}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="submit"
            className="process-button"
            disabled={!canProcess() || status.status === 'processing'}
            style={{ backgroundColor: getStatusColor() }}
          >
            {status.status === 'processing' ? (
              module === 'mapping' ? 'Allineamento in corso...' : 'Processing...'
            ) : (
              module === 'mapping' ? 'Avvia Assessment' :
                inputType === 'none' ? 'Start Analysis' : 'Process Files'
            )}
          </button>

          {status.status === 'error' && (
            <div className="error-message">
              {status.message}
            </div>
          )}

          {status.status === 'completed' && (
            <div className="success-message">
              [SUCCESS] {status.message}
            </div>
          )}
        </form>
      )}
    </div>
  );
};

export default ModuleDetail;