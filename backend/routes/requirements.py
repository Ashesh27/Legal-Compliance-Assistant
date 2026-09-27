"""
Gestione estrazione dei requisiti
"""

from flask import request, jsonify, send_file
from . import requirements_bp
from werkzeug.utils import secure_filename
import threading
import os
import json
import time

from config.settings import UPLOAD_FOLDER, REQUIREMENTS_FOLDER
from services.document_service import process_path
from scripts.chunking_dynamic import DynamicMacroSectionChunker
from services.requirements_service import process_chunks_file, save_requirements_to_file
from services.redundancy_service import RedundancyEliminator

# Global processing status
processing_status = {'status': 'idle', 'step': '', 'progress': 0, 'message': ''}

def update_status(status, step, progress, message):
    global processing_status
    processing_status.update({
        'status': status,
        'step': step,
        'progress': progress,
        'message': message
    })

def process_requirements_async(req_path, extraction_name='Unnamed Requirements'):
    """Process requirements asynchronously."""
    try:
        update_status('processing', 'Processing requirements PDF...', 10, 'Analyzing requirements document')
        
        print("🔄 Step 1: Processing requirements PDF with Dynamic Chunking...")
        
        # NUOVO: Chunking dinamico basato su LLM per macrosezioni
        chunker = DynamicMacroSectionChunker(pages_per_batch=3)
        
        # Output directory per dynamic chunks
        dynamic_output_dir = os.path.dirname(req_path)
        
        # Processa il documento e crea i chunk dinamici
        chunker.process_document(req_path, output_dir=dynamic_output_dir)

        update_status('processing', 'Extracting requirements...', 50, 'Extracting requirements from PDF')
        
        # Generate requirements file - usa il file dinamico
        base_name = os.path.splitext(os.path.basename(req_path))[0]
        req_chunks_file = os.path.join(dynamic_output_dir, f"{base_name}_dynamic_chunks.txt")
        requirements_list = process_chunks_file(req_chunks_file)
        
        # Create named folder structure
        safe_name = secure_filename(extraction_name)
        extraction_folder = os.path.join(REQUIREMENTS_FOLDER, safe_name)
        os.makedirs(extraction_folder, exist_ok=True)
        
        # Save RAW requirements first
        raw_req_output_file = os.path.join(extraction_folder, 'requirements_raw.txt')
        save_requirements_to_file(requirements_list, raw_req_output_file)
        
        # --- REDUNDANCY ELIMINATION START ---
        update_status('processing', 'Eliminating redundancies...', 70, 'Optimizing requirements list')
        print("🔄 Step 2: Eliminating redundancies...")
        
        try:
            eliminator = RedundancyEliminator()
            requirements_list = eliminator.process(requirements_list)
        except Exception as e:
            print(f"⚠️ Redundancy elimination failed, proceeding with original list: {e}")
        # --- REDUNDANCY ELIMINATION END ---
        
        # Save to named requirements folder
        req_output_file = os.path.join(extraction_folder, 'requirements.txt')
        save_requirements_to_file(requirements_list, req_output_file)
        
        # Also save metadata
        metadata = {
            'extraction_name': extraction_name,
            'original_file': os.path.basename(req_path),
            'processed_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_requirements': len(requirements_list),
            'requirements_file': req_output_file,
            'raw_requirements_file': raw_req_output_file,
            'extraction_folder': extraction_folder
        }
        
        with open(os.path.join(extraction_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        update_status('completed', 'Requirements extraction completed!', 100, f'Extracted {len(requirements_list)} requirements as "{extraction_name}"')
        
    except Exception as e:
        print(f"Requirements extraction error: {str(e)}")
        update_status('error', 'Error occurred', 0, str(e))

@requirements_bp.route('/process-requirements', methods=['POST'])
def process_requirements():
    """Process requirements PDF endpoint."""
    if processing_status['status'] == 'processing':
        return jsonify({'error': 'Requirements processing already in progress'}), 400
    
    try:
        requirements_pdf = request.files.get('requirements_pdf')
        extraction_name = request.form.get('extraction_name', 'Unnamed Requirements')
        
        if not requirements_pdf:
            return jsonify({'error': 'Requirements PDF missing'}), 400
        
        update_status('processing', 'Uploading file...', 5, 'Saving uploaded file')
        
        req_filename = secure_filename(requirements_pdf.filename)
        req_path = os.path.join(UPLOAD_FOLDER, f"req_{req_filename}")
        requirements_pdf.save(req_path)
        
        thread = threading.Thread(target=process_requirements_async, args=(req_path, extraction_name))
        thread.start()
        
        return jsonify({'status': 'started', 'message': f'Requirements processing started for "{extraction_name}"'})
        
    except Exception as e:
        update_status('error', 'Error occurred', 0, str(e))
        return jsonify({'error': str(e)}), 500

@requirements_bp.route('/status/requirements')
def get_status():
    """Get processing status."""
    return jsonify(processing_status)

@requirements_bp.route('/check-requirements')
def check_requirements():
    """Check if requirements exist."""
    req_file = os.path.join(REQUIREMENTS_FOLDER, 'requirements.txt')
    metadata_file = os.path.join(REQUIREMENTS_FOLDER, 'metadata.json')
    
    if os.path.exists(req_file):
        metadata = {}
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        
        return jsonify({
            'exists': True,
            'metadata': metadata
        })
    return jsonify({'exists': False})

@requirements_bp.route('/get-available-requirements')
def get_available_requirements():
    """Get list of available requirements files."""
    try:
        requirements_files = []
        
        # Check requirements folder for named extractions
        if os.path.exists(REQUIREMENTS_FOLDER):
            for folder_name in os.listdir(REQUIREMENTS_FOLDER):
                folder_path = os.path.join(REQUIREMENTS_FOLDER, folder_name)
                if os.path.isdir(folder_path):
                    req_file = os.path.join(folder_path, 'requirements.txt')
                    metadata_file = os.path.join(folder_path, 'metadata.json')
                    
                    if os.path.exists(req_file):
                        metadata = {}
                        if os.path.exists(metadata_file):
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                        
                        display_name = metadata.get('extraction_name', folder_name)
                        
                        requirements_files.append({
                            'path': req_file,
                            'name': f'{display_name}',
                            'folder_name': folder_name,
                            'location': f'requirements/{folder_name}/',
                            'metadata': metadata
                        })
        
        return jsonify(requirements_files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500