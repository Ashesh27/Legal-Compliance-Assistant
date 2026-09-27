"""
Modulo per la gestione delle rotte del mapping.
Gestisce endpoints per il document alignment e mapping.
"""

from flask import request, jsonify, send_file
from . import mapping_bp
from werkzeug.utils import secure_filename
import threading
import os
import json
import time
import tempfile
import shutil

from config.settings import OUTPUT_FOLDER, MAPPINGS_FOLDER
from services.mapping_service import ImprovedRequirementsMapper

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

def process_mapping_async(selected_requirements_file, selected_chunk_files, mapping_name):
    """Process mapping asynchronously."""
    try:
        update_status('processing', 'Initializing mapping...', 10, 'Preparing files')
        
        # Ensure output directories exist
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        os.makedirs(MAPPINGS_FOLDER, exist_ok=True)
        
        update_status('processing', 'Loading selected files...', 20, f'Using {len(selected_chunk_files)} chunk files')
        
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
            
            update_status('processing', 'Analyzing requirements mapping...', 50, 'Mapping requirements to selected documents')
            
            # Perform mapping with selected files
            mapper = ImprovedRequirementsMapper()
            results = mapper.process_enhanced_mapping(
                requirements_file=selected_requirements_file,
                chunks_dir=temp_chunks_dir,
                output_dir=mapping_folder
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
        
        update_status('completed', 'Document alignment completed!', 100, f'Mapping analysis completed successfully as "{mapping_name}"')
        
    except Exception as e:
        print(f"Mapping error: {str(e)}")
        update_status('error', 'Error occurred', 0, str(e))

@mapping_bp.route('/process-mapping', methods=['POST'])
def process_mapping():
    """Process mapping endpoint."""
    if processing_status['status'] == 'processing':
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
        update_status('error', 'Error occurred', 0, str(e))
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/status/mapping')
def get_status():
    """Get processing status."""
    return jsonify(processing_status)

@mapping_bp.route('/get-available-mappings')
def get_available_mappings():
    """Get list of available mapping results."""
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

@mapping_bp.route('/get-mapping-results')
def get_mapping_results():
    """Get mapping results with file selection."""
    try:
        file_path = request.args.get('file')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/download-mapping-excel')
def download_mapping_excel():
    """Download Excel with file selection."""
    try:
        file_path = request.args.get('file')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Excel file not found'}), 404
        
        filename = os.path.basename(file_path)
        if not filename:
            filename = 'compliance_analysis.xlsx'
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/check-existing-results')
def check_existing_results():
    """Check for existing mapping results."""
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

@mapping_bp.route('/results')
def get_latest_results():
    """Get the most recent mapping results."""
    try:
        # Find most recent mapping folder
        if not os.path.exists(MAPPINGS_FOLDER):
            return jsonify([]), 200
            
        folders = [os.path.join(MAPPINGS_FOLDER, d) for d in os.listdir(MAPPINGS_FOLDER) 
                  if os.path.isdir(os.path.join(MAPPINGS_FOLDER, d))]
        
        if not folders:
            return jsonify([]), 200
            
        # Sort by modification time (newest first)
        latest_folder = max(folders, key=os.path.getmtime)
        
        json_path = os.path.join(latest_folder, 'mapping_results.json')
        excel_path = os.path.join(latest_folder, 'mapping_results.xlsx')
        
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            return jsonify({
                'results': results,
                'excel_path': excel_path if os.path.exists(excel_path) else None,
                'mapping_name': os.path.basename(latest_folder)
            })
            
        return jsonify([]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500