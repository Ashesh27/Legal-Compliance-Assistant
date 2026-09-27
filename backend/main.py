from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
from pathlib import Path
from werkzeug.utils import secure_filename
import threading
import time
import tempfile
import shutil
from services.document_service import process_path
from scripts.chunking_improved import ImprovedDocumentChunker
from scripts.chunking_dynamic import DynamicMacroSectionChunker
from services.mapping_service import ImprovedRequirementsMapper
from services.requirements_service import process_chunks_file, save_requirements_to_file
from services.redundancy_service import RedundancyEliminator
from scripts.annex_merger import AnnexMergerEnhanced as AnnexMerger
from config import settings as config
import os

app = Flask(__name__)
CORS(app)

# Inizializza directory
config.init_directories()

# Importa costanti di configurazione
UPLOAD_FOLDER = config.UPLOAD_FOLDER
OUTPUT_FOLDER = config.OUTPUT_FOLDER
CHUNKS_FOLDER = config.CHUNKS_FOLDER
REQUIREMENTS_FOLDER = config.REQUIREMENTS_FOLDER
INTERNAL_DOCS_FOLDER = config.INTERNAL_DOCS_FOLDER
MAPPINGS_FOLDER = config.MAPPINGS_FOLDER

# Register blueprints
from routes import requirements_bp, internal_docs_bp, mapping_bp
app.register_blueprint(requirements_bp)
app.register_blueprint(internal_docs_bp)
app.register_blueprint(mapping_bp)

# Global variables to track processing status for each module
processing_status = {
    'requirements': {'status': 'idle', 'step': '', 'progress': 0, 'message': ''},
    'internal_docs': {'status': 'idle', 'step': '', 'progress': 0, 'message': ''},
    'mapping': {'status': 'idle', 'step': '', 'progress': 0, 'message': ''}
}

@app.route('/api/status/<module>')
def get_status(module):
    if module in processing_status:
        return jsonify(processing_status[module])
    return jsonify({'error': 'Invalid module'}), 400

@app.route('/api/status/all')
def get_all_status():
    return jsonify(processing_status)

def update_status(module, status, step, progress, message):
    global processing_status
    if module in processing_status:
        processing_status[module].update({
            'status': status,
            'step': step,
            'progress': progress,
            'message': message
        })

# MODULE A: REQUIREMENTS EXTRACTION
def process_requirements_async(req_path, extraction_name='Unnamed Requirements'):
    try:
        update_status('requirements', 'processing', 'Processing requirements PDF...', 10, 'Analyzing requirements document')
        
        print("🔄 Step 1: Processing requirements PDF with Dynamic Chunking...")
        
        # NUOVO: Chunking dinamico basato su LLM per macrosezioni
        chunker = DynamicMacroSectionChunker(pages_per_batch=3)
        
        # Output directory per dynamic chunks
        dynamic_output_dir = os.path.dirname(req_path)
        
        # Processa il documento e crea i chunk dinamici
        chunker.process_document(req_path, output_dir=dynamic_output_dir)
        
        update_status('requirements', 'processing', 'Extracting requirements...', 50, 'Extracting requirements from PDF')
        
        # Generate requirements file - usa il file dinamico
        base_name = os.path.splitext(os.path.basename(req_path))[0]
        req_chunks_file = os.path.join(dynamic_output_dir, f"{base_name}_dynamic_chunks.txt")
        requirements_list = process_chunks_file(req_chunks_file)
        
        # Create named folder structure
        safe_name = secure_filename(extraction_name)
        extraction_folder = os.path.join(REQUIREMENTS_FOLDER, safe_name)
        os.makedirs(extraction_folder, exist_ok=True)
        
        # Save RAW requirements first (Exactly as before)
        raw_req_output_file = os.path.join(extraction_folder, 'requirements_raw.txt')
        save_requirements_to_file(requirements_list, raw_req_output_file)
        
        # --- REDUNDANCY ELIMINATION START ---
        update_status('requirements', 'processing', 'Eliminating redundancies...', 70, 'Optimizing requirements list')
        print("🔄 Step 2: Eliminating redundancies...")
        
        try:
            eliminator = RedundancyEliminator()
            requirements_list = eliminator.process(requirements_list)
        except Exception as e:
            print(f"⚠️ Redundancy elimination failed, proceeding with original list: {e}")
        # --- REDUNDANCY ELIMINATION END ---
        
        # Save FINAL (optimized) requirements
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
        
        update_status('requirements', 'completed', 'Requirements extraction completed!', 100, f'Extracted {len(requirements_list)} requirements as "{extraction_name}"')
        
    except Exception as e:
        print(f"Requirements extraction error: {str(e)}")
        update_status('requirements', 'error', 'Error occurred', 0, str(e))

@app.route('/api/process-requirements', methods=['POST'])
def process_requirements():
    if processing_status['requirements']['status'] == 'processing':
        return jsonify({'error': 'Requirements processing already in progress'}), 400
    
    try:
        requirements_file = request.files.get('requirements_pdf')
        extraction_name = request.form.get('extraction_name', 'Unnamed Requirements')
        
        if not requirements_file:
            return jsonify({'error': 'Requirements file missing'}), 400
        
        update_status('requirements', 'processing', 'Uploading file...', 5, 'Saving uploaded file')
        
        req_filename = secure_filename(requirements_file.filename)
        req_path = os.path.join(UPLOAD_FOLDER, f"req_{req_filename}")
        requirements_file.save(req_path)
        
        # Check if it's a TXT file (pre-extracted)
        if req_filename.lower().endswith('.txt'):
            # Direct save logic for TXT
            try:
                safe_name = secure_filename(extraction_name)
                extraction_folder = os.path.join(REQUIREMENTS_FOLDER, safe_name)
                os.makedirs(extraction_folder, exist_ok=True)
                
                # Copy to requirements.txt
                req_output_file = os.path.join(extraction_folder, 'requirements.txt')
                shutil.copy2(req_path, req_output_file)
                
                # Create simple metadata
                metadata = {
                    'extraction_name': extraction_name,
                    'original_file': req_filename,
                    'processed_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'total_requirements': 0, # Unknown without parsing
                    'requirements_file': req_output_file,
                    'extraction_folder': extraction_folder,
                    'type': 'pre_extracted_txt'
                }
                
                with open(os.path.join(extraction_folder, 'metadata.json'), 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                update_status('requirements', 'completed', 'Requirements loaded!', 100, f'Loaded pre-extracted requirements "{extraction_name}"')
                return jsonify({'status': 'completed', 'message': f'Requirements loaded for "{extraction_name}"'})
                
            except Exception as e:
                update_status('requirements', 'error', 'Error loading TXT', 0, str(e))
                return jsonify({'error': str(e)}), 500
        else:
            # Normal PDF processing
            thread = threading.Thread(target=process_requirements_async, args=(req_path, extraction_name))
            thread.start()
            return jsonify({'status': 'started', 'message': f'Requirements processing started for "{extraction_name}"'})
        
    except Exception as e:
        update_status('requirements', 'error', 'Error occurred', 0, str(e))
        return jsonify({'error': str(e)}), 500

# MODULE B: INTERNAL DOCUMENTS PROCESSING
# Logic moved to routes/internal_docs.py to avoid duplication

# CHECK AVAILABILITY OF PROCESSED DATA
@app.route('/api/check-requirements')
def check_requirements():
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

@app.route('/api/check-internal-docs')
def check_internal_docs():
    metadata_file = os.path.join(INTERNAL_DOCS_FOLDER, 'metadata.json')
    
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return jsonify({
            'exists': True,
            'metadata': metadata
        })
    return jsonify({'exists': False})

@app.route('/api/check-existing-results')
def check_existing_results():
    # Check mappings folder for any results
    mappings_available = []
    if os.path.exists(MAPPINGS_FOLDER):
        for folder_name in os.listdir(MAPPINGS_FOLDER):
            folder_path = os.path.join(MAPPINGS_FOLDER, folder_name)
            if os.path.isdir(folder_path):
                json_path = os.path.join(folder_path, 'mapping_results.json')
                excel_path = os.path.join(folder_path, 'mapping_results.xlsx')
                if os.path.exists(json_path):
                    mappings_available.append({
                        'name': folder_name,
                        'json_path': json_path,
                        'excel_path': excel_path,
                        'excel_available': os.path.exists(excel_path)
                    })
    
    # Also check legacy paths for backward compatibility
    legacy_json = os.path.join(OUTPUT_FOLDER, 'mapping_results.json')
    legacy_excel = os.path.join(OUTPUT_FOLDER, 'mapping_results.xlsx')
    if os.path.exists(legacy_json):
        mappings_available.append({
            'name': 'Legacy Results (root)',
            'json_path': legacy_json,
            'excel_path': legacy_excel,
            'excel_available': os.path.exists(legacy_excel)
        })
    
    if mappings_available:
        # Return the first available mapping for compatibility
        first_mapping = mappings_available[0]
        with open(first_mapping['json_path'], 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({
            'exists': True,
            'preview': data[:10],
            'total_count': len(data),
            'excel_available': first_mapping['excel_available'],
            'mappings_available': mappings_available
        })
    return jsonify({'exists': False})

# EXISTING ENDPOINTS (kept for compatibility)
@app.route('/api/download-excel')
def download_excel():
    excel_path = os.path.join(OUTPUT_FOLDER, 'mapping_results.xlsx')
    if os.path.exists(excel_path):
        return send_file(excel_path, as_attachment=True, download_name='compliance_analysis.xlsx')
    return jsonify({'error': 'Excel file not found'}), 404

@app.route('/api/get-results-preview')
def get_results_preview():
    json_path = os.path.join(OUTPUT_FOLDER, 'mapping_results.json')
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data[:10])
    return jsonify([])

@app.route('/api/get-full-results')
def get_full_results():
    json_path = os.path.join(OUTPUT_FOLDER, 'mapping_results.json')
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify([])

# NEW ENDPOINT FOR FETCHING REQUIREMENTS
@app.route('/api/get-requirements-list')
def get_requirements_list():
    """Get parsed requirements list from requirements.txt"""
    try:
        # Check if a specific file is requested
        file_path = request.args.get('file')
        
        if file_path and os.path.exists(file_path):
            req_file_path = file_path
        else:
            # Default to the main requirements file
            req_file_path = os.path.join(OUTPUT_FOLDER, 'requirements.txt')
        
        if not os.path.exists(req_file_path):
            return jsonify({'error': 'Requirements file not found'}), 404
            
        with open(req_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract total count from header
        import re
        total_match = re.search(r'Totale requisiti: (\d+)', content)
        total_count = int(total_match.group(1)) if total_match else 0
        
        # Parse requirements by splitting chunks (more robust than regex)
        blocks = content.split("=" * 80)
        requirements = []
        
        for block in blocks:
            block = block.strip()
            if not block or "REQUISITO" not in block:
                continue
                
            entries = {}
            lines = block.split('\n')
            current_key = None
            
            for line in lines:
                line = line.strip()
                if not line: 
                    continue
                    
                if line.startswith("REQUISITO") and not line.startswith("REQUISITO:"):
                     # It's the header "REQUISITO 1"
                     try:
                         entries['numero'] = int(line.replace("REQUISITO", "").strip())
                     except:
                         pass
                elif line.startswith("File sorgente:"):
                    entries['file_sorgente'] = line.replace("File sorgente:", "").strip()
                elif line.startswith("Chunk sorgente:"):
                    entries['chunk_sorgente'] = line.replace("Chunk sorgente:", "").strip()
                elif line.startswith("REQUISITO:"):
                    entries['requisito'] = line.replace("REQUISITO:", "").strip()
                    current_key = 'requisito'
                elif line.startswith("DOMANDA AUDIT:"):
                    entries['domanda_audit'] = line.replace("DOMANDA AUDIT:", "").strip()
                    current_key = 'domanda_audit'
                elif line.startswith("REFERENZE:"):
                    entries['referenze'] = line.replace("REFERENZE:", "").strip()
                    current_key = 'referenze'
                elif line.startswith("-") or line.startswith("="):
                    continue
                else:
                    # Append continuation lines to the last key
                    if current_key and current_key in entries:
                        entries[current_key] += " " + line
            
            if 'numero' in entries and 'requisito' in entries:
                requirements.append({
                    'numero': entries.get('numero', 0),
                    'file_sorgente': entries.get('file_sorgente', 'N/A'),
                    'chunk_sorgente': entries.get('chunk_sorgente', 'N/A'),
                    'requisito': entries.get('requisito', ''),
                    'domanda_audit': entries.get('domanda_audit', ''),
                    'referenze': entries.get('referenze', '')
                })
        
        return jsonify({
            'success': True,
            'total_count': total_count,
            'requirements': requirements,
            'file_path': req_file_path
        })
        
    except Exception as e:
        print(f"Error fetching requirements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-requirements-list')
def download_requirements_list():
    """Download a clean formatted requirements list"""
    try:
        # Check if a specific file is requested
        file_path = request.args.get('file')
        
        if file_path and os.path.exists(file_path):
            req_file_path = file_path
        else:
            # Default to the main requirements file
            req_file_path = os.path.join(OUTPUT_FOLDER, 'requirements.txt')
        
        if not os.path.exists(req_file_path):
            return jsonify({'error': 'Requirements file not found'}), 404
            
        with open(req_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse and format requirements for download
        import re
        total_match = re.search(r'Totale requisiti: (\d+)', content)
        total_count = int(total_match.group(1)) if total_match else 0
        
        # Parse requirements by splitting chunks (more robust than regex)
        blocks = content.split("=" * 80)
        
        # Create clean formatted output
        formatted_content = f"LISTA REQUISITI ESTRATTI\n"
        formatted_content += f"Totale: {total_count} requisiti\n"
        formatted_content += f"Data estrazione: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        formatted_content += "=" * 80 + "\n\n"
        
        for block in blocks:
            block = block.strip()
            if not block or "REQUISITO" not in block:
                continue
                
            entries = {}
            lines = block.split('\n')
            current_key = None
            
            for line in lines:
                line = line.strip()
                if not line: continue
                    
                if line.startswith("REQUISITO") and not line.startswith("REQUISITO:"):
                     try:
                         entries['numero'] = int(line.replace("REQUISITO", "").strip())
                     except: pass
                elif line.startswith("File sorgente:"):
                    entries['file_sorgente'] = line.replace("File sorgente:", "").strip()
                elif line.startswith("REQUISITO:"):
                    entries['requisito'] = line.replace("REQUISITO:", "").strip()
                    current_key = 'requisito'
                elif line.startswith("DOMANDA AUDIT:"):
                    entries['domanda_audit'] = line.replace("DOMANDA AUDIT:", "").strip()
                    current_key = 'domanda_audit'
                elif line.startswith("REFERENZE:"):
                    # Optional field
                    pass 
                elif line.startswith("-") or line.startswith("="):
                    continue
                else:
                    if current_key and current_key in entries:
                        entries[current_key] += " " + line

            if 'numero' in entries and 'requisito' in entries:
                req_num = entries.get('numero')
                source_file = entries.get('file_sorgente', 'N/A')
                requirement_text = entries.get('requisito', '')
                audit_question = entries.get('domanda_audit', '')
                
                formatted_content += f"REQUISITO {req_num}\n"
                formatted_content += f"Fonte: {source_file}\n"
                formatted_content += f"Testo: {requirement_text}\n"
                formatted_content += f"Domanda Audit: {audit_question}\n"
                formatted_content += "-" * 60 + "\n\n"
        
        # Create temporary file for download
        temp_file = os.path.join(OUTPUT_FOLDER, 'requisiti_lista.txt')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        
        return send_file(temp_file, as_attachment=True, download_name='requisiti_lista.txt', mimetype='text/plain')
        
    except Exception as e:
        print(f"Error creating requirements download: {str(e)}")
        return jsonify({'error': str(e)}), 500

# NEW ENDPOINTS FOR SELECTING FILES
@app.route('/api/get-available-requirements')
def get_available_requirements():
    """Get list of available requirements files"""
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
                        
                        # Use the extraction_name from metadata, fallback to folder name
                        display_name = metadata.get('extraction_name', folder_name)
                        
                        requirements_files.append({
                            'path': req_file,
                            'name': f'{display_name}',
                            'folder_name': folder_name,
                            'location': f'requirements/{folder_name}/',
                            'metadata': metadata
                        })
        
        # Check main requirements folder for legacy requirements.txt
        legacy_req_file = os.path.join(REQUIREMENTS_FOLDER, 'requirements.txt')
        if os.path.exists(legacy_req_file):
            metadata_file = os.path.join(REQUIREMENTS_FOLDER, 'metadata.json')
            metadata = {}
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            
            requirements_files.append({
                'path': legacy_req_file,
                'name': 'Legacy Requirements (root folder)',
                'folder_name': 'root',
                'location': 'requirements/',
                'metadata': metadata
            })
        
        # Check output folder for other requirements files
        output_req_file = os.path.join(OUTPUT_FOLDER, 'requirements.txt')
        if os.path.exists(output_req_file):
            requirements_files.append({
                'path': output_req_file,
                'name': 'requirements.txt (from Output folder)',
                'folder_name': 'output',
                'location': 'output/',
                'metadata': {}
            })
        
        return jsonify(requirements_files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-requirement', methods=['POST'])
def delete_requirement():
    """Delete a requirement extraction by folder name"""
    try:
        data = request.get_json()
        folder_name = data.get('folder_name')
        
        if not folder_name:
            return jsonify({'error': 'Folder name required'}), 400
            
        # Handle different locations
        if folder_name == 'root':
            # Legacy root - maybe just delete the file? Or clear it?
            # For safety, let's just delete the file
            req_file = os.path.join(REQUIREMENTS_FOLDER, 'requirements.txt')
            if os.path.exists(req_file):
                os.remove(req_file)
            return jsonify({'success': True, 'message': 'Legacy requirements deleted'})
            
        elif folder_name == 'output':
            # Output folder
            req_file = os.path.join(OUTPUT_FOLDER, 'requirements.txt')
            if os.path.exists(req_file):
                os.remove(req_file)
            return jsonify({'success': True, 'message': 'Output requirements deleted'})
            
        else:
            # Named extraction folder
            folder_path = os.path.join(REQUIREMENTS_FOLDER, folder_name)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                return jsonify({'success': True, 'message': f'Requirement "{folder_name}" deleted'})
            else:
                return jsonify({'error': 'Requirement folder not found'}), 404
                
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-available-chunks')
def get_available_chunks():
    """Get list of available chunk files"""
    try:
        chunk_files = []
        
        # Check chunks folder for JSON files (legacy)
        if os.path.exists(CHUNKS_FOLDER):
            for file in os.listdir(CHUNKS_FOLDER):
                if file.endswith('_chunks_chunks.json'):
                    file_path = os.path.join(CHUNKS_FOLDER, file)
                    
                    # Try to get file info
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        chunk_count = len(data) if isinstance(data, list) else len(data.get('chunks', []))
                        file_size = os.path.getsize(file_path)
                        
                        chunk_files.append({
                            'path': file_path,
                            'name': f'{file.replace("_chunks_chunks.json", "")} (legacy)',
                            'filename': file,
                            'chunk_count': chunk_count,
                            'size': file_size,
                            'location': 'chunks/',
                            'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                        })
                    except Exception as e:
                        # If can't read the file, still add it but with limited info
                        chunk_files.append({
                            'path': file_path,
                            'name': f'{file.replace("_chunks_chunks.json", "")} (legacy)',
                            'filename': file,
                            'chunk_count': 'Unknown',
                            'size': os.path.getsize(file_path),
                            'location': 'chunks/',
                            'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path))),
                            'error': str(e)
                        })
        
        # Check internal_docs folder for JSON files (using original document names)
        if os.path.exists(INTERNAL_DOCS_FOLDER):
            for file in os.listdir(INTERNAL_DOCS_FOLDER):
                if file.endswith('.json') and file != 'metadata.json' and os.path.isfile(os.path.join(INTERNAL_DOCS_FOLDER, file)):
                    file_path = os.path.join(INTERNAL_DOCS_FOLDER, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        chunk_count = len(data) if isinstance(data, list) else len(data.get('chunks', []))
                        
                        chunk_files.append({
                            'path': file_path,
                            'name': file.replace('.json', ''),
                            'filename': file,
                            'chunk_count': chunk_count,
                            'size': os.path.getsize(file_path),
                            'location': 'internal_docs/',
                            'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path)))
                        })
                    except Exception as e:
                        chunk_files.append({
                            'path': file_path,
                            'name': file.replace('.json', ''),
                            'filename': file,
                            'chunk_count': 'Unknown',
                            'size': os.path.getsize(file_path),
                            'location': 'internal_docs/',
                            'modified': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(file_path))),
                            'error': str(e)
                        })
        
        return jsonify(chunk_files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# MODULE C: DOCUMENT ALIGNMENT (MAPPING) WITH FILE SELECTION
def process_mapping_async(selected_requirements_file, selected_chunk_files, mapping_name='Unnamed Mapping'):
    try:
        update_status('mapping', 'processing', 'Starting document alignment...', 10, 'Preparing mapping analysis')
        
        # Validate selected files
        if not os.path.exists(selected_requirements_file):
            raise Exception(f"Selected requirements file not found: {selected_requirements_file}")
        
        for chunk_file in selected_chunk_files:
            if not os.path.exists(chunk_file):
                raise Exception(f"Selected chunk file not found: {chunk_file}")
        
        update_status('mapping', 'processing', 'Loading selected files...', 20, f'Using {len(selected_chunk_files)} chunk files')
        
        # Create named folder structure for mapping results
        safe_name = secure_filename(mapping_name)
        mapping_folder = os.path.join(OUTPUT_FOLDER, 'mappings', safe_name)
        os.makedirs(mapping_folder, exist_ok=True)
        
        # Create a temporary directory with selected chunks for mapping
        with tempfile.TemporaryDirectory() as temp_chunks_dir:
            # Copy selected chunk files to temp directory
            for chunk_file in selected_chunk_files:
                filename = os.path.basename(chunk_file)
                shutil.copy2(chunk_file, os.path.join(temp_chunks_dir, filename))
            
            update_status('mapping', 'processing', 'Analyzing requirements mapping...', 50, 'Mapping requirements to selected documents')
            
            # Perform mapping with selected files
            mapper = ImprovedRequirementsMapper()
            results = mapper.process_enhanced_mapping(
                requirements_file=selected_requirements_file,
                chunks_dir=temp_chunks_dir,
                output_dir=mapping_folder  # Save to named folder
            )
            
            # Also copy results to main OUTPUT_FOLDER for backward compatibility
            mapping_json = os.path.join(mapping_folder, 'mapping_results.json')
            mapping_excel = os.path.join(mapping_folder, 'mapping_results.xlsx')
            
            if os.path.exists(mapping_json):
                shutil.copy2(mapping_json, os.path.join(OUTPUT_FOLDER, 'mapping_results.json'))
            if os.path.exists(mapping_excel):
                shutil.copy2(mapping_excel, os.path.join(OUTPUT_FOLDER, 'mapping_results.xlsx'))
            
            # Add metadata about selected files
            mapping_metadata = {
                'mapping_name': mapping_name,
                'selected_requirements_file': selected_requirements_file,
                'selected_chunk_files': selected_chunk_files,
                'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_chunk_files': len(selected_chunk_files),
                'mapping_folder': mapping_folder
            }
            
            with open(os.path.join(mapping_folder, 'mapping_metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(mapping_metadata, f, indent=2, ensure_ascii=False)
            
            # Also save to main OUTPUT_FOLDER for backward compatibility
            with open(os.path.join(OUTPUT_FOLDER, 'mapping_metadata.json'), 'w', encoding='utf-8') as f:
                json.dump(mapping_metadata, f, indent=2, ensure_ascii=False)
        
        update_status('mapping', 'completed', 'Document alignment completed!', 100, f'Mapping analysis completed successfully as "{mapping_name}"')
        
    except Exception as e:
        print(f"Mapping error: {str(e)}")
        update_status('mapping', 'error', 'Error occurred', 0, str(e))

# MODULE D: ANNEX/FAQ MERGER
@app.route('/api/process-annex-merge', methods=['POST'])
def process_annex_merge():
    # 1. Handle File Uploads Directly
    main_doc_file = request.files.get('main_doc_file')
    annex_doc_files = request.files.getlist('annex_doc_files')
    
    if not main_doc_file or not annex_doc_files:
        return jsonify({'error': 'Missing main document or annex documents'}), 400

    # Save Main Doc
    original_main_filename = main_doc_file.filename
    main_filename = secure_filename(original_main_filename)
    main_doc_path = os.path.join(UPLOAD_FOLDER, f"annex_main_{int(time.time())}_{main_filename}")
    main_doc_file.save(main_doc_path)
    
    # Derive output name from original (without extension)
    base_name = os.path.splitext(original_main_filename)[0]
    output_name = f"{base_name}_merged"
    
    # Save Annex Docs
    clean_annex_paths = []
    for i, f in enumerate(annex_doc_files):
        fname = secure_filename(f.filename)
        fpath = os.path.join(UPLOAD_FOLDER, f"annex_extra_{int(time.time())}_{i}_{fname}")
        f.save(fpath)
        clean_annex_paths.append(fpath)
            
    job_name = f"Merged_{int(time.time())}"
    output_dir = os.path.join(OUTPUT_FOLDER, 'annex_merged')
    
    def run_async_job():
        try:
            merger = AnnexMerger()
            result = merger.process_files(
                main_doc_path=main_doc_path,
                annex_paths=clean_annex_paths,
                output_dir=output_dir,
                job_name=output_name,
                generate_pdf=False  # Skip PDF, only MD
            )
            # New AnnexMergerEnhanced returns a dict
            md_path = result.get('markdown_path') if isinstance(result, dict) else result
            # Store result path with original name for download
            processing_status['annex_job_' + job_name] = {
                'status': 'completed', 
                'md_path': md_path,
                'download_name': f"{output_name}.md"
            }
        except Exception as e:
            print(f"Annex Job Failed: {e}")
            processing_status['annex_job_' + job_name] = {'status': 'error', 'error': str(e)}

    # Start Async
    thread = threading.Thread(target=run_async_job)
    thread.start()
    
    return jsonify({
        'status': 'started', 
        'job_id': job_name,
        'message': 'Annex merging started. Poll status or wait.'
    })

@app.route('/api/check-annex-status/<job_id>')
def check_annex_status(job_id):
    key = 'annex_job_' + job_id
    if key in processing_status:
        return jsonify(processing_status[key])
    return jsonify({'status': 'processing'}) # Assume processing if not found/completed yet? Or specific logic.

@app.route('/api/download-annex-result/<job_id>')
def download_annex_result(job_id):
    key = 'annex_job_' + job_id
    if key in processing_status and processing_status[key]['status'] == 'completed':
        job_data = processing_status[key]
        md_path = job_data.get('md_path')
        download_name = job_data.get('download_name', f"{job_id}.md")
        
        if not md_path:
            return jsonify({'error': 'Markdown path not found'}), 404
            
        abs_path = os.path.abspath(md_path)
        print(f"📥 Servicing MD download: {abs_path}")
        
        if not os.path.exists(abs_path):
            print(f"❌ File not found at: {abs_path}")
            return jsonify({'error': 'File not found on server'}), 404
            
        return send_file(
            abs_path, 
            as_attachment=True,
            mimetype='text/markdown',
            download_name=download_name
        )
    return jsonify({'error': 'File not ready'}), 404

@app.route('/api/get-internal-docs-list')
def get_internal_docs_list():
    """Get list of processed internal documents with metadata"""
    try:
        metadata_file = os.path.join(INTERNAL_DOCS_FOLDER, 'metadata.json')
        
        if not os.path.exists(metadata_file):
            return jsonify({'success': False, 'error': 'No processed internal documents found'})
        
        # Load metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Get document details
        internal_docs = []
        processed_docs = metadata.get('processed_docs', [])
        
        if processed_docs:
            # New format with processed_docs
            for doc in processed_docs:
                doc_info = {
                    'id': len(internal_docs),  # Use index as ID
                    'original_name': doc.get('original_name', ''),
                    'display_name': doc.get('clean_name', ''),
                    'chunks_file': doc.get('chunks_file', ''),
                    'processed_date': metadata.get('processed_date', ''),
                    'chunk_count': doc.get('chunks_count', 0),
                    'exists': os.path.exists(doc.get('chunks_file', '')) if doc.get('chunks_file') else False
                }
                
                # Get file size if file exists
                if doc_info['exists']:
                    try:
                        doc_info['file_size'] = os.path.getsize(doc_info['chunks_file'])
                    except Exception:
                        doc_info['file_size'] = 0
                
                internal_docs.append(doc_info)
        else:
            # Legacy format - try to reconstruct from original_files
            for i, original_file in enumerate(metadata.get('original_files', [])):
                # Extract document name from original filename
                doc_name = original_file.replace('internal_', '').replace('.pdf', '')
                # Remove the duplicate number at the start if present
                if doc_name.startswith(f'{i}_'):
                    doc_name = doc_name[2:]  # Remove "X_" where X is the index
                
                # Try different possible chunk file locations
                possible_files = [
                    os.path.join(INTERNAL_DOCS_FOLDER, f'{doc_name}_chunks.json'),
                    os.path.join(INTERNAL_DOCS_FOLDER, f'internal_{i}_{doc_name}_chunks_chunks.json')
                ]
                
                chunks_file = None
                for possible_file in possible_files:
                    if os.path.exists(possible_file):
                        chunks_file = possible_file
                        break
                
                doc_info = {
                    'id': i,
                    'original_name': original_file,
                    'display_name': doc_name,
                    'chunks_file': chunks_file or possible_files[0],
                    'processed_date': metadata.get('processed_date', ''),
                    'exists': chunks_file is not None
                }
                
                # Get chunk count and file size if file exists
                if doc_info['exists']:
                    try:
                        with open(chunks_file, 'r', encoding='utf-8') as cf:
                            chunks_data = json.load(cf)
                            if isinstance(chunks_data, list):
                                doc_info['chunk_count'] = len(chunks_data)
                            else:
                                doc_info['chunk_count'] = len(chunks_data.get('chunks', []))
                        doc_info['file_size'] = os.path.getsize(chunks_file)
                    except Exception as e:
                        print(f"Error reading chunks file {chunks_file}: {e}")
                        doc_info['chunk_count'] = 0
                        doc_info['file_size'] = 0
                else:
                    doc_info['chunk_count'] = 0
                    doc_info['file_size'] = 0
                
                internal_docs.append(doc_info)
        
        return jsonify({
            'success': True,
            'documents': internal_docs,
            'total_documents': len(internal_docs),
            'processed_date': metadata.get('processed_date', ''),
            'metadata': metadata
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete-internal-doc/<int:doc_id>', methods=['DELETE'])
def delete_internal_doc(doc_id):
    """Delete a specific internal document and its chunks"""
    try:
        metadata_file = os.path.join(INTERNAL_DOCS_FOLDER, 'metadata.json')
        
        if not os.path.exists(metadata_file):
            return jsonify({'success': False, 'error': 'No metadata file found'})
        
        # Load metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        if doc_id >= len(metadata.get('original_files', [])):
            return jsonify({'success': False, 'error': 'Document not found'})
        
        original_file = metadata['original_files'][doc_id]
        # Extract document name from original filename
        doc_name = original_file.replace('internal_', '').replace('.pdf', '')
        # Remove the duplicate number at the start if present
        if doc_name.startswith(f'{doc_id}_'):
            doc_name = doc_name[2:]  # Remove "X_" where X is the index
        
        # Files to delete
        chunks_file = os.path.join(INTERNAL_DOCS_FOLDER, f'internal_{doc_id}_{doc_name}_chunks_chunks.json')
        chunks_txt_file = os.path.join(INTERNAL_DOCS_FOLDER, f'internal_{doc_id}_{doc_name}_chunks_chunks.txt')
        uploaded_pdf = os.path.join(UPLOAD_FOLDER, original_file)
        uploaded_txt = os.path.join(UPLOAD_FOLDER, original_file.replace('.pdf', '_chunks.txt'))
        
        # Delete files
        files_deleted = []
        for file_path in [chunks_file, chunks_txt_file, uploaded_pdf, uploaded_txt]:
            if os.path.exists(file_path):
                os.remove(file_path)
                files_deleted.append(os.path.basename(file_path))
        
        # Update metadata
        metadata['original_files'].pop(doc_id)
        metadata['total_documents'] = len(metadata['original_files'])
        metadata['total_chunks'] = metadata['total_chunks'] - 1 if metadata['total_chunks'] > 0 else 0
        
        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True, 
            'message': f'Document {original_file} deleted successfully',
            'files_deleted': files_deleted
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/process-mapping', methods=['POST'])
def process_mapping():
    if processing_status['mapping']['status'] == 'processing':
        return jsonify({'Stato': 'Mappatura in corso'}), 400
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        selected_requirements_file = data.get('requirements_file')
        selected_chunk_files = data.get('chunk_files', [])
        mapping_name = data.get('mapping_name', 'Unnamed Mapping')
        
        if not selected_requirements_file:
            return jsonify({'error': 'Requirements file must be selected'}), 400
        
        if not selected_chunk_files:
            return jsonify({'error': 'At least one chunk file must be selected'}), 400
        
        thread = threading.Thread(target=process_mapping_async, args=(selected_requirements_file, selected_chunk_files, mapping_name))
        thread.start()
        
        return jsonify({'status': 'started', 'message': f'Document alignment started for "{mapping_name}" with selected files'})
        
    except Exception as e:
        update_status('mapping', 'error', 'Error occurred', 0, str(e))
        return jsonify({'error': str(e)}), 500

# NEW ENDPOINTS FOR MAPPINGS SELECTION
@app.route('/api/get-available-mappings')
def get_available_mappings():
    """Get list of available mapping results"""
    try:
        mappings = []
        
        # Check mappings folder
        if os.path.exists(MAPPINGS_FOLDER):
            for folder_name in os.listdir(MAPPINGS_FOLDER):
                folder_path = os.path.join(MAPPINGS_FOLDER, folder_name)
                if os.path.isdir(folder_path):
                    json_path = os.path.join(folder_path, 'mapping_results.json')
                    excel_path = os.path.join(folder_path, 'mapping_results.xlsx')
                    metadata_path = os.path.join(folder_path, 'mapping_metadata.json')
                    
                    metadata = {}
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    
                    if os.path.exists(json_path):
                        mappings.append({
                            'name': metadata.get('mapping_name', folder_name),
                            'folder_name': folder_name,
                            'json_path': json_path,
                            'excel_path': excel_path,
                            'has_json': True,
                            'has_excel': os.path.exists(excel_path),
                            'location': f'mappings/{folder_name}/',
                            'metadata': metadata
                        })
        
        # Check legacy paths
        legacy_json = os.path.join(OUTPUT_FOLDER, 'mapping_results.json')
        legacy_excel = os.path.join(OUTPUT_FOLDER, 'mapping_results.xlsx')
        if os.path.exists(legacy_json):
            mappings.append({
                'name': 'Legacy Results (root folder)',
                'folder_name': 'legacy',
                'json_path': legacy_json,
                'excel_path': legacy_excel,
                'has_json': True,
                'has_excel': os.path.exists(legacy_excel),
                'location': 'output/',
                'metadata': {}
            })
        
        return jsonify(mappings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-mapping-results')
def get_mapping_results():
    """Get mapping results with file selection"""
    try:
        file_path = request.args.get('file')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-mapping-excel')
def download_mapping_excel():
    """Download Excel with file selection"""
    try:
        file_path = request.args.get('file')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Excel file not found'}), 404
        
        # Extract filename for download
        filename = os.path.basename(file_path)
        if not filename:
            filename = 'compliance_analysis.xlsx'
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
     app.run(debug=True, host='0.0.0.0', port=5020)