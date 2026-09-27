import React, { useState, useEffect } from 'react';
import * as XLSX from 'xlsx';
import LivelloSorter from './LivelloSorter';

const XlsxViewer = ({ isOpen, onClose, selectedExcelFile }) => {
    const [excelData, setExcelData] = useState([]);
    const [excelHeaders, setExcelHeaders] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [filteredData, setFilteredData] = useState([]);
    const [livelloColumnIndex, setLivelloColumnIndex] = useState(-1);
    const [originalData, setOriginalData] = useState([]); // Store original order
    const [displayData, setDisplayData] = useState([]); // Data after sorting

    // Filter data when search term changes
    useEffect(() => {
        if (searchTerm) {
            const filtered = displayData.filter(row =>
                row.some(cell =>
                    cell && cell.toString().toLowerCase().includes(searchTerm.toLowerCase())
                )
            );
            setFilteredData(filtered);
        } else {
            setFilteredData(displayData);
        }
    }, [searchTerm, displayData]);

    // Load Excel data when component opens
    useEffect(() => {
        if (isOpen) {
            loadExcelData();
        }
    }, [isOpen]);

    const loadExcelData = async () => {
        setLoading(true);
        setError(null);

        try {
            let url = `${process.env.REACT_APP_API_URL}/api/download-mapping-excel`;
            if (selectedExcelFile) {
                url += `?file=${encodeURIComponent(selectedExcelFile)}`;
            } else {
                // Fallback to legacy endpoint
                url = `${process.env.REACT_APP_API_URL}/api/download-excel`;
            }

            const response = await fetch(url);

            if (!response.ok) {
                throw new Error('Excel file not found or error downloading');
            }

            const arrayBuffer = await response.arrayBuffer();
            const workbook = XLSX.read(arrayBuffer, { type: 'array' });
            const sheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[sheetName];
            const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

            if (jsonData.length > 0) {
                const headers = jsonData[0];
                const dataRows = jsonData.slice(1);

                setExcelHeaders(headers);
                setExcelData(dataRows);
                setOriginalData(dataRows); // Store original order
                setDisplayData(dataRows); // Initialize display data
                setFilteredData(dataRows);

                // Find LIVELLO column index
                const livelloIndex = headers.findIndex(header =>
                    header && header.toString().toLowerCase().includes('livello')
                );
                setLivelloColumnIndex(livelloIndex);
            } else {
                setError('Excel file is empty');
            }
        } catch (error) {
            console.error('Error loading Excel file:', error);
            setError(error.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDataChange = (newData) => {
        setDisplayData(newData);
    };

    const downloadExcel = () => {
        let url = `${process.env.REACT_APP_API_URL}/api/download-mapping-excel`;
        if (selectedExcelFile) {
            url += `?file=${encodeURIComponent(selectedExcelFile)}`;
        } else {
            // Fallback to legacy endpoint
            url = `${process.env.REACT_APP_API_URL}/api/download-excel`;
        }
        window.open(url, '_blank');
    };

    const getLivelloColor = (value) => {
        if (!value) return 'transparent';

        const val = value.toString().toLowerCase();

        if (val.includes('1') || val.includes('assente')) {
            return '#F44336'; // red
        } else if (val.includes('2') || val.includes('bassa')) {
            return '#ff8307ff'; // orange
        } else if (val.includes('3') || val.includes('media')) {
            return '#f6ff00ff'; // yellow
        } else if (val.includes('4') || val.includes('elevata')) {
            return '#a9f91fff'; // light green
        } else if (val.includes('5') || val.includes('completa')) {
            return '#028b00ff'; // green
        }

        return 'transparent';
    };

    const formatMappingContent = (content) => {
        if (!content) return '';

        const contentStr = content.toString();

        // Split by numbered items (1., 2., 3., etc.)
        const items = contentStr.split(/(?=\d+\.\s+File:)/).filter(item => item.trim());

        return items.map((item, index) => {
            // Extract file, section, and score using regex
            const fileMatch = item.match(/File:\s*([^\n]+)/);
            const sectionMatch = item.match(/Sezione:\s*([^\n]+)/);
            const scoreMatch = item.match(/Score:\s*([\d.]+)/);

            if (fileMatch && sectionMatch && scoreMatch) {
                const fileName = fileMatch[1].trim();
                const section = sectionMatch[1].trim();
                const score = parseFloat(scoreMatch[1]);

                // Get file type indicator
                const fileType = fileName.includes('MRS-') ? 'MRS' :
                    fileName.includes('POL-') ? 'POL' :
                        fileName.includes('PRO-') ? 'PRO' : 'DOC';

                return {
                    number: index + 1,
                    fileName,
                    fileType,
                    section,
                    score,
                    original: item.trim()
                };
            }
            return null;
        }).filter(Boolean);
    };

    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
        }}>
            <div style={{
                backgroundColor: 'white',
                padding: '15px',
                borderRadius: '0px',
                width: '98%',
                height: '95%',
                overflow: 'hidden',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column'
            }}>
                <button
                    onClick={onClose}
                    style={{
                        position: 'absolute',
                        top: '10px',
                        right: '15px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        fontSize: '24px',
                        cursor: 'pointer',
                        zIndex: 10
                    }}
                >
                    ×
                </button>

                {/* Compact Header with all controls */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '10px',
                    paddingRight: '40px',
                    flexWrap: 'wrap',
                    gap: '10px'
                }}>
                    <h2 style={{
                        color: 'var(--primary-color)',
                        margin: '0',
                        fontSize: '20px'
                    }}>
                        Visualizzatore Excel - Risultati Mapping
                    </h2>

                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        flexWrap: 'wrap'
                    }}>
                        {!loading && !error && excelData.length > 0 && (
                            <input
                                type="text"
                                placeholder="Cerca nell'Excel..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                style={{
                                    padding: '8px 12px',
                                    border: '1px solid #ddd',
                                    borderRadius: '4px',
                                    width: '160px',
                                    height: '36px',
                                    fontSize: '13px',
                                    boxSizing: 'border-box'
                                }}
                            />
                        )}

                        {/* Inline Livello Sorter - matching size and style */}
                        {!loading && !error && excelData.length > 0 && livelloColumnIndex !== -1 && (
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '5px',
                                padding: '8px 12px',
                                border: '1px solid #ddd',
                                borderRadius: '4px',
                                width: '160px',
                                height: '36px',
                                fontSize: '13px',
                                boxSizing: 'border-box',
                                backgroundColor: '#ffffff'
                            }}>
                                <span style={{
                                    fontSize: '13px',
                                    fontWeight: 'bold',
                                    color: '#333',
                                    whiteSpace: 'nowrap'
                                }}>
                                    Livello:
                                </span>
                                <LivelloSorter
                                    data={displayData}
                                    onDataChange={handleDataChange}
                                    livelloColumnIndex={livelloColumnIndex}
                                    originalData={originalData}
                                />
                            </div>
                        )}

                        <button
                            onClick={downloadExcel}
                            style={{
                                backgroundColor: 'var(--primary-color)',
                                color: 'white',
                                padding: '8px 12px',
                                border: 'none',
                                borderRadius: '0px',
                                cursor: 'pointer',
                                fontWeight: 'bold',
                                fontSize: '12px'
                            }}
                        >
                            Download Excel
                        </button>

                        <button
                            onClick={loadExcelData}
                            disabled={loading}
                            style={{
                                backgroundColor: loading ? '#ccc' : 'var(--secondary-color)',
                                color: 'white',
                                padding: '8px 12px',
                                border: 'none',
                                borderRadius: '0px',
                                cursor: loading ? 'not-allowed' : 'pointer',
                                fontSize: '12px'
                            }}
                        >
                            {loading ? 'Aggiornamento' : 'Aggiorna Excel'}
                        </button>
                    </div>
                </div>

                {/* Data count info */}
                {!loading && !error && excelData.length > 0 && (
                    <div style={{
                        marginBottom: '5px',
                        fontSize: '11px',
                        color: '#666',
                        textAlign: 'center',
                        padding: '3px',
                        backgroundColor: '#f8f9fa'
                    }}>
                        Mostrando {filteredData.length} di {excelData.length} requisiti totali
                    </div>
                )}


                <div style={{ flex: 1, overflow: 'auto' }}>
                    {loading && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            height: '100%',
                            flexDirection: 'column',
                            gap: '15px'
                        }}>
                            <div className="spinner"></div>
                            <p>Caricamento Excel in corso...</p>
                        </div>
                    )}

                    {error && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            height: '100%',
                            flexDirection: 'column'
                        }}>
                            <div style={{
                                textAlign: 'center',
                                color: 'var(--primary-color)',
                                padding: '20px',
                                backgroundColor: 'var(--background-light)',
                                borderRadius: '4px',
                                maxWidth: '500px'
                            }}>
                                <h3>Errore nel caricamento</h3>
                                <p>{error}</p>
                                <button
                                    onClick={loadExcelData}
                                    style={{
                                        backgroundColor: 'var(--primary-color)',
                                        color: 'white',
                                        padding: '10px 20px',
                                        border: 'none',
                                        borderRadius: '0px',
                                        cursor: 'pointer',
                                        marginTop: '10px'
                                    }}
                                >
                                    Riprova
                                </button>
                            </div>
                        </div>
                    )}

                    {!loading && !error && excelData.length === 0 && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            height: '100%',
                            flexDirection: 'column'
                        }}>
                            <div style={{
                                textAlign: 'center',
                                color: '#666',
                                padding: '20px',
                                backgroundColor: 'var(--background-light)',
                                borderRadius: '4px',
                                maxWidth: '500px'
                            }}>
                                <h3>Nessun dato Excel disponibile</h3>
                                <p>Non è stato trovato alcun file Excel da visualizzare.</p>
                            </div>
                        </div>
                    )}

                    {!loading && !error && filteredData.length > 0 && (
                        <div style={{ height: '100%', overflow: 'auto' }}>
                            <style>
                                {`
                                .excel-header:hover {
                                    transform: scale(1.05);
                                    transition: transform 0.2s ease;
                                    z-index: 10;
                                    position: relative;
                                }
                                .excel-header {
                                    transition: transform 0.2s ease;
                                }
                                `}
                            </style>
                            <table style={{
                                border: '2px solid #ddd',
                                width: '100%',
                                borderCollapse: 'collapse',
                                fontSize: '12px',
                                tableLayout: 'auto'
                            }}>
                                <thead style={{ position: 'sticky', top: 0, backgroundColor: 'white', zIndex: 5 }}>
                                    <tr>
                                        {excelHeaders.map((header, index) => (
                                            <th key={index} className="excel-header" style={{
                                                border: '2px solid #ddd',
                                                padding: '12px 8px',
                                                backgroundColor: '#f8f9fa',
                                                textAlign: 'left',
                                                fontWeight: 'bold',
                                                fontSize: '13px',
                                                verticalAlign: 'top',
                                                wordWrap: 'break-word',
                                                minWidth: '120px',
                                                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                                                cursor: 'pointer'
                                            }}>
                                                {header}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredData.map((row, rowIndex) => (
                                        <tr key={rowIndex} style={{
                                            backgroundColor: rowIndex % 2 === 0 ? '#ffffff' : '#f8f9fa',
                                            borderBottom: '1px solid #eee'
                                        }}>
                                            {row.map((cell, cellIndex) => {
                                                const cellContent = cell ? cell.toString() : '';
                                                const isLivelloColumn = cellIndex === livelloColumnIndex;
                                                const livelloColor = isLivelloColumn ? getLivelloColor(cellContent) : 'transparent';

                                                const isMappingColumn = excelHeaders[cellIndex] &&
                                                    excelHeaders[cellIndex].toString().toLowerCase().includes('mapping');

                                                return (
                                                    <td key={cellIndex} style={{
                                                        border: '1px solid #ddd',
                                                        padding: '8px 6px',
                                                        verticalAlign: 'top',
                                                        fontSize: '11px',
                                                        lineHeight: '1.4',
                                                        backgroundColor: isLivelloColumn ? livelloColor : 'transparent',
                                                        color: isLivelloColumn && livelloColor !== 'transparent' ? 'white' : 'inherit',
                                                        fontWeight: isLivelloColumn ? 'bold' : 'normal',
                                                        minWidth: isMappingColumn ? '270px' : '80px',
                                                        maxWidth: isMappingColumn ? '340px' : '170px'
                                                    }}>
                                                        {isMappingColumn ? (
                                                            <div style={{
                                                                wordWrap: 'break-word',
                                                                wordBreak: 'break-word',
                                                                whiteSpace: 'normal'
                                                            }}>
                                                                {formatMappingContent(cellContent).map((item, idx) => (
                                                                    <div key={idx} style={{
                                                                        marginBottom: '8px',
                                                                        paddingBottom: '6px'
                                                                    }}>
                                                                        <div style={{
                                                                            display: 'flex',
                                                                            alignItems: 'center',
                                                                            marginBottom: '2px',
                                                                            gap: '8px'
                                                                        }}>
                                                                            <span style={{
                                                                                fontSize: '8px',
                                                                                fontWeight: 'bold',
                                                                                color: '#333'
                                                                            }}>
                                                                                {item.fileType}
                                                                            </span>
                                                                            <span style={{
                                                                                fontSize: '8px',
                                                                                fontWeight: 'bold',
                                                                                color: '#666'
                                                                            }}>
                                                                                {(item.score * 100).toFixed(1)}%
                                                                            </span>
                                                                        </div>
                                                                        <div style={{
                                                                            fontWeight: 'bold',
                                                                            color: '#000',
                                                                            marginBottom: '2px',
                                                                            fontSize: '10px'
                                                                        }}>
                                                                            {item.fileName.replace('_chunks.txt', '')}
                                                                        </div>
                                                                        <div style={{
                                                                            color: '#555',
                                                                            fontSize: '9px',
                                                                            fontWeight: 'normal'
                                                                        }}>
                                                                            {item.section}
                                                                        </div>
                                                                    </div>
                                                                ))}
                                                                {formatMappingContent(cellContent).length === 0 && (
                                                                    <div style={{
                                                                        wordWrap: 'break-word',
                                                                        wordBreak: 'break-word',
                                                                        whiteSpace: 'pre-wrap',
                                                                        fontSize: '10px',
                                                                        color: '#666'
                                                                    }}>
                                                                        {cellContent}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <div style={{
                                                                wordWrap: 'break-word',
                                                                wordBreak: 'break-word',
                                                                whiteSpace: 'pre-wrap',
                                                                maxWidth: '170px'
                                                            }}>
                                                                {/* Remove square brackets from GAP column values */}
                                                                {excelHeaders[cellIndex] &&
                                                                    excelHeaders[cellIndex].toString().toLowerCase().includes('gap') ?
                                                                    cellContent.replace(/^\[|\]$/g, '').replace() :
                                                                    cellContent}
                                                            </div>
                                                        )}
                                                    </td>
                                                );
                                            })}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {!loading && !error && excelData.length > 0 && filteredData.length === 0 && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            height: '100%',
                            flexDirection: 'column'
                        }}>
                            <div style={{
                                textAlign: 'center',
                                color: '#666',
                                padding: '20px',
                                backgroundColor: '#f8f9fa',
                                borderRadius: '4px',
                                maxWidth: '500px'
                            }}>
                                <h3>Nessun risultato trovato</h3>
                                <p>La ricerca per "{searchTerm}" non ha prodotto risultati.</p>
                                <button
                                    onClick={() => setSearchTerm('')}
                                    style={{
                                        backgroundColor: 'var(--primary-color)',
                                        color: 'white',
                                        padding: '8px 16px',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        marginTop: '10px'
                                    }}
                                >
                                    Pulisci ricerca
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default XlsxViewer;