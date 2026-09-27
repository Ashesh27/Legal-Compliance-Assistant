import React from 'react';
import { AlertTriangle } from 'lucide-react';

const ConfirmationModal = ({ isOpen, onClose, onConfirm, title, message, itemName }) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-scale-in">
                <div className="p-6 text-center">
                    <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <AlertTriangle className="text-red-600" size={24} />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
                    <p className="text-slate-500 mb-6">
                        {message} <span className="font-semibold text-slate-700">"{itemName}"</span>?
                        <br />
                        Questa azione non può essere annullata.
                    </p>

                    <div className="flex gap-3 justify-center">
                        <button
                            onClick={onClose}
                            className="px-5 py-2.5 rounded-xl font-medium text-slate-600 hover:bg-slate-100 transition-colors"
                        >
                            Annulla
                        </button>
                        <button
                            onClick={() => {
                                onConfirm();
                                onClose();
                            }}
                            className="px-5 py-2.5 rounded-xl font-medium text-white bg-red-600 hover:bg-red-700 shadow-lg shadow-red-500/30 transition-all hover:scale-105"
                        >
                            Elimina
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ConfirmationModal;
