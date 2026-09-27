import React from 'react';

const ModuleCard = ({ 
  title, 
  description,
  hasData,
  onClick
}) => {
  return (
    <div className="module-card">
      <div className="card-content">
        <h3>{title}</h3>
        <p>{description}</p>
        {hasData && (
          <div className="data-status">
            <span className="data-badge">Dati disponibili</span>
          </div>
        )}
      </div>
      <div className="card-action">
        <button onClick={onClick} className="open-module-btn">
          Apri
        </button>
      </div>
    </div>
  );
};

export default ModuleCard;