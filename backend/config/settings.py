"""
File di configurazione centralizzato per l'applicazione.
Carica tutte le variabili d'ambiente e fornisce costanti di configurazione.
"""

import os
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
LLM_MAPPING_MODEL = os.getenv('LLM_MAPPING_MODEL', 'deepseek-r1:14b')
LLM_EXTRACTION_MODEL = os.getenv('LLM_EXTRACTION_MODEL', 'deepseek-r1:32b')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')

# LLM Parameters
LLM_MAPPING_TEMPERATURE = float(os.getenv('LLM_MAPPING_TEMPERATURE', '0.1'))
LLM_EXTRACTION_TEMPERATURE = float(os.getenv('LLM_EXTRACTION_TEMPERATURE', '0.0001'))
LLM_NUM_PREDICT = int(os.getenv('LLM_NUM_PREDICT', '4096'))
LLM_NUM_CTX = int(os.getenv('LLM_NUM_CTX', '8192'))
LLM_TOP_P = float(os.getenv('LLM_TOP_P', '0.95'))

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Percorsi applicazione
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', './uploads')
OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', './output')
CHUNKS_FOLDER = os.getenv('CHUNKS_FOLDER', './output/chunks')
REQUIREMENTS_FOLDER = os.getenv('REQUIREMENTS_FOLDER', './output/requirements')
INTERNAL_DOCS_FOLDER = os.getenv('INTERNAL_DOCS_FOLDER', './output/internal_docs')
MAPPINGS_FOLDER = os.getenv('MAPPINGS_FOLDER', './output/mappings')

# Crea le directory se non esistono
def init_directories():
    """Crea tutte le directory necessarie per l'applicazione"""
    directories = [
        UPLOAD_FOLDER,
        OUTPUT_FOLDER,
        CHUNKS_FOLDER,
        REQUIREMENTS_FOLDER,
        INTERNAL_DOCS_FOLDER,
        MAPPINGS_FOLDER
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)