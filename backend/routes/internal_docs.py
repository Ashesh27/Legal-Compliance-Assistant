"""
Gestione degli endpoints e rotte per i documenti interni
"""

from flask import request, jsonify
from . import internal_docs_bp
from werkzeug.utils import secure_filename
import threading
import os
import json
import time
import shutil

from config.settings import UPLOAD_FOLDER, INTERNAL_DOCS_FOLDER
from services.document_service import process_path
from scripts.chunking_improved import ImprovedDocumentChunker

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

def process_internal_docs_async(internal_paths):
    """Process internal documents asynchronously."""
    try:
        update_status('processing', 'Processing internal documents...', 10, 'Starting document analysis')
        
        # Process each document
        for i, path in enumerate(internal_paths):
            update_status('processing', f'Processing document {i+1}/{len(internal_paths)}...', 
                         10 + (i * 40 // len(internal_paths)), f'Processing {os.path.basename(path)}')
            process_path(
                path=path,
                min_chars=10,
                max_tokens=400
            )
        
        update_status('processing', 'Improving document chunks...', 60, 'Optimizing document chunks')
        
        # Improved chunking - save with original names in internal_docs folder
        chunker = ImprovedDocumentChunker(
            chunk_size=800,
            overlap=200,
            min_chunk_size=100
        )
        
        chunk_files = [p.replace('.pdf', '_chunks.txt') for p in internal_paths]
        
        # Process each document individually to maintain original names
        processed_docs = []
        for i, (chunk_file, internal_path) in enumerate(zip(chunk_files, internal_paths)):
            # Extract original filename without the internal_X_ prefix
            original_filename = os.path.basename(internal_path)
            if original_filename.startswith('internal_'):
                parts = original_filename.split('_', 2)
                if len(parts) > 2:
                    original_filename = parts[2]
            
            clean_name = original_filename.replace('.pdf', '')
            
            # Process single document
            chunks_dict = chunker.process_multiple_documents([chunk_file], INTERNAL_DOCS_FOLDER)
            
            chunk_file_name = os.path.basename(chunk_file)
            chunks = chunks_dict.get(chunk_file_name, [])
            
            # Rename output files to use original names
            # Chunker adds _chunks.json to the stem. The input file was ..._chunks.txt
            # So the output is ..._chunks_chunks.json
            old_json_path = os.path.join(INTERNAL_DOCS_FOLDER, f'{os.path.basename(chunk_file).replace(".txt", "")}_chunks.json')
            old_txt_path = os.path.join(INTERNAL_DOCS_FOLDER, f'{os.path.basename(chunk_file).replace(".txt", "")}_chunks.txt')
            
            new_json_path = os.path.join(INTERNAL_DOCS_FOLDER, f'{clean_name}_chunks.json')
            new_txt_path = os.path.join(INTERNAL_DOCS_FOLDER, f'{clean_name}_chunks.txt')
            
            # Rename files if they exist and names are different
            if os.path.exists(old_json_path) and old_json_path != new_json_path:
                shutil.move(old_json_path, new_json_path)
                
                # Update source_file in the JSON content
                try:
                    with open(new_json_path, 'r', encoding='utf-8') as f:
                        chunks_data = json.load(f)
                    
                    updated = False
                    for chunk in chunks_data:
                        if 'source_file' in chunk:
                            chunk['source_file'] = original_filename
                            updated = True
                    
                    if updated:
                        with open(new_json_path, 'w', encoding='utf-8') as f:
                            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"Error updating source_file in JSON: {e}")

            if os.path.exists(old_txt_path) and old_txt_path != new_txt_path:
                shutil.move(old_txt_path, new_txt_path)
            
            processed_docs.append({
                'original_name': original_filename,
                'clean_name': clean_name,
                'chunks_file': new_json_path,
                'chunks_count': len(chunks)
            })
        
        # Save metadata
        metadata = {
            'original_files': [doc['original_name'] for doc in processed_docs],
            'processed_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_documents': len(internal_paths),
            'chunks_folder': INTERNAL_DOCS_FOLDER,
            'total_chunks': sum(doc['chunks_count'] for doc in processed_docs),
            'processed_docs': processed_docs
        }
        
        with open(os.path.join(INTERNAL_DOCS_FOLDER, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        update_status('completed', 'Internal documents processing completed!', 100, 
                     f'Processed {len(internal_paths)} documents')
        
    except Exception as e:
        print(f"Internal docs processing error: {str(e)}")
        update_status('error', 'Error occurred', 0, str(e))

@internal_docs_bp.route('/process-internal-docs', methods=['POST'])
def process_internal_docs():
    """Process internal documents endpoint."""
    if processing_status['status'] == 'processing':
        return jsonify({'error': 'Internal docs processing already in progress'}), 400
    
    try:
        internal_docs = request.files.getlist('internal_docs')
        
        if not internal_docs:
            return jsonify({'error': 'Internal documents missing'}), 400
        
        # Set status synchronously to avoid race condition
        update_status('processing', 'Initializing processing...', 0, 'Starting...')
        
        internal_paths = []
        for i, doc in enumerate(internal_docs):
            filename = secure_filename(doc.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"internal_{i}_{filename}")
            doc.save(filepath)
            internal_paths.append(filepath)
        
        thread = threading.Thread(target=process_internal_docs_async, args=(internal_paths,))
        thread.start()
        
        return jsonify({'status': 'started', 'message': 'Internal documents processing started'})
        
    except Exception as e:
        update_status('error', 'Error occurred', 0, str(e))
        return jsonify({'error': str(e)}), 500

@internal_docs_bp.route('/status/internal_docs')
def get_status():
    """Get processing status."""
    return jsonify(processing_status)

@internal_docs_bp.route('/check-internal-docs')
def check_internal_docs():
    """Check if internal docs exist."""
    metadata_file = os.path.join(INTERNAL_DOCS_FOLDER, 'metadata.json')
    
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return jsonify({
            'exists': True,
            'metadata': metadata
        })
    return jsonify({'exists': False})

@internal_docs_bp.route('/get-available-chunks')
def get_available_chunks():
    """Get list of available chunk files."""
    try:
        chunk_files = []
        
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

@internal_docs_bp.route('/delete-chunk', methods=['POST'])
def delete_chunk():
    """Delete a processed chunk file."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'error': 'Filename required'}), 400
            
        json_path = os.path.join(INTERNAL_DOCS_FOLDER, filename)
        txt_path = os.path.join(INTERNAL_DOCS_FOLDER, filename.replace('.json', '.txt'))
        
        deleted = False
        if os.path.exists(json_path):
            os.remove(json_path)
            deleted = True
            
        if os.path.exists(txt_path):
            os.remove(txt_path)
            
        if deleted:
            return jsonify({'message': 'File deleted successfully'})
        else:
            return jsonify({'error': 'File not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500