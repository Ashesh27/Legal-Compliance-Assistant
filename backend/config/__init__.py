"""" Qui tutto ciò che deve andare a prendersi"""
from .settings import *
from .prompts_config import *

__all__ = [
    'LLM_PROVIDER',
    'LLM_MAPPING_MODEL',
    'LLM_EXTRACTION_MODEL',
    'EMBEDDING_MODEL',
    'LLM_MAPPING_TEMPERATURE',
    'LLM_EXTRACTION_TEMPERATURE',
    'LLM_NUM_PREDICT',
    'LLM_NUM_CTX',
    'LLM_TOP_P',
    'GEMINI_API_KEY',
    'OPENAI_API_KEY',
    'UPLOAD_FOLDER',
    'OUTPUT_FOLDER',
    'CHUNKS_FOLDER',
    'REQUIREMENTS_FOLDER',
    'INTERNAL_DOCS_FOLDER',
    'MAPPINGS_FOLDER',
    'init_directories',
    'EXTRACTION_SYSTEM_PROMPT',
    'EXTRACTION_USER_PROMPT_TEMPLATE',
    'MAPPING_SYSTEM_PROMPT',
    'MAPPING_USER_PROMPT_TEMPLATE',
    'get_extraction_user_prompt',
    'get_mapping_user_prompt',
    'get_custom_prompt'
]