import React, { useRef, useState } from 'react';
import { Upload, FileText, X } from 'lucide-react';

const FileUpload = ({
  title,
  description,
  files = [],
  onUpload,
  onRemove,
  accept = ".pdf",
  theme = 'indigo'
}) => {
  const fileInputRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(Array.from(e.target.files));
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUpload(Array.from(e.dataTransfer.files));
    }
  };

  const isIndigo = theme === 'indigo';
  const themeColor = isIndigo ? 'text-brand-600' : 'text-accent-600';
  const bgColor = isIndigo ? 'bg-brand-50' : 'bg-accent-50';

  const activeClass = isDragging
    ? (isIndigo ? 'border-brand-400 bg-brand-50/80' : 'border-emerald-400 bg-emerald-50/80')
    : 'border-slate-200 hover:border-brand-300 hover:bg-white/60';

  return (
    <div className="w-full flex flex-col">
      <div className="mb-4">
        <h4 className="font-bold text-slate-800 text-lg">{title}</h4>
        <p className="text-sm text-slate-500">{description}</p>
      </div>

      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          relative flex-1 min-h-[220px] border-2 border-dashed rounded-2xl 
          flex flex-col items-center justify-center cursor-pointer 
          transition-all duration-300 group backdrop-blur-sm
          ${activeClass}
        `}
      >
        <input
          type="file"
          multiple
          ref={fileInputRef}
          className="hidden"
          accept={accept}
          onChange={handleFileChange}
        />

        <div className={`
          w-16 h-16 rounded-2xl mb-4 flex items-center justify-center shadow-lg transform transition-transform group-hover:scale-110 duration-300
          ${isIndigo ? 'bg-gradient-to-br from-brand-500 to-indigo-600 text-white' : 'bg-gradient-to-br from-emerald-400 to-emerald-600 text-white'}
        `}>
          <Upload size={32} strokeWidth={2} />
        </div>
        <span className="font-bold text-slate-700 text-base">Carica documenti PDF</span>
        <span className="text-xs text-slate-400 mt-1">Trascina o clicca per esplorare</span>
      </div>

      {/* File List */}
      <div className="mt-4 space-y-2">
        {files.length > 0 ? (
          <div className="max-h-[180px] overflow-y-auto pr-2 custom-scrollbar space-y-2">
            {files.map((file, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-white/80 backdrop-blur border border-slate-100 rounded-xl shadow-sm hover:shadow-md transition-all duration-200 group animate-fade-in">
                <div className="flex items-center gap-3 overflow-hidden">
                  <div className={`p-2 rounded-lg ${bgColor} ${themeColor}`}>
                    <FileText size={18} />
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="text-sm font-semibold text-slate-700 truncate">{file.name}</span>
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider font-medium">
                      {(file.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onRemove(idx); }}
                  className="text-slate-300 hover:text-red-500 hover:bg-red-50 p-1.5 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                >
                  <X size={16} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-[60px] flex items-center justify-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <span className="text-xs text-slate-400 italic">Nessun file caricato</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default FileUpload;