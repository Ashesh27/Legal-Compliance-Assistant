import React, { useState } from 'react';

const LivelloSorter = ({ 
    data, 
    onDataChange, 
    livelloColumnIndex, 
    originalData
}) => {
    const [sortState, setSortState] = useState('original'); // 'original', 'asc', 'desc'

    // Function to extract numeric value from livello cell
    const extractLivelloValue = (cell) => {
        if (!cell) return 0;
        
        const cellStr = cell.toString().toLowerCase();
        
        // Check for numeric values first
        if (cellStr.includes('1') || cellStr.includes('assente')) return 1;
        if (cellStr.includes('2') || cellStr.includes('bassa')) return 2;
        if (cellStr.includes('3') || cellStr.includes('media')) return 3;
        if (cellStr.includes('4') || cellStr.includes('elevata')) return 4;
        if (cellStr.includes('5') || cellStr.includes('completa')) return 5;
        
        // Try to extract pure number
        const numMatch = cellStr.match(/(\d+)/);
        if (numMatch) {
            const num = parseInt(numMatch[1]);
            return num >= 1 && num <= 5 ? num : 0;
        }
        
        return 0; // Default for unrecognized values
    };

    const handleSort = (direction) => {
        if (livelloColumnIndex === -1) {
            alert('Colonna LIVELLO non trovata nei dati');
            return;
        }

        let sortedData;
        
        if (direction === 'original') {
            sortedData = [...originalData];
            setSortState('original');
        } else {
            sortedData = [...data].sort((a, b) => {
                const aValue = extractLivelloValue(a[livelloColumnIndex]);
                const bValue = extractLivelloValue(b[livelloColumnIndex]);
                
                if (direction === 'asc') {
                    return aValue - bValue;
                } else {
                    return bValue - aValue;
                }
            });
            setSortState(direction);
        }
        
        onDataChange(sortedData);
    };

    const getSortButtonStyle = (buttonType) => ({
        padding: '3px 6px',
        margin: '0 1px',
        border: '1px solid #ddd',
        borderRadius: '3px',
        backgroundColor: sortState === buttonType ? 'var(--primary-color)' : '#ffffff',
        color: sortState === buttonType ? 'white' : '#333',
        cursor: 'pointer',
        fontSize: '10px',
        fontWeight: sortState === buttonType ? 'bold' : 'normal',
        transition: 'all 0.2s ease'
    });

    const getArrowStyle = (isActive) => ({
        fontSize: '10px',
        fontWeight: 'bold',
        color: isActive ? 'white' : '#666'
    });

    if (livelloColumnIndex === -1) {
        return null; // Don't render if LIVELLO column is not found
    }

    return (
        <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
            <button
                onClick={() => handleSort('asc')}
                style={getSortButtonStyle('asc')}
                title="Ordina crescente (1→5)"
            >
                <span style={getArrowStyle(sortState === 'asc')}>↑</span>
            </button>
            
            <button
                onClick={() => handleSort('desc')}
                style={getSortButtonStyle('desc')}
                title="Ordina decrescente (5→1)"
            >
                <span style={getArrowStyle(sortState === 'desc')}>↓</span>
            </button>
            
            <button
                onClick={() => handleSort('original')}
                style={getSortButtonStyle('original')}
                title="Ripristina ordine originale"
            >
                <span style={getArrowStyle(sortState === 'original')}>⟲</span>
            </button>
        </div>
    );
};

export default LivelloSorter;