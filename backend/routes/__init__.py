"""
Routes package for the application.
"""

from flask import Blueprint

# Create blueprints
requirements_bp = Blueprint('requirements', __name__, url_prefix='/api')
internal_docs_bp = Blueprint('internal_docs', __name__, url_prefix='/api')
mapping_bp = Blueprint('mapping', __name__, url_prefix='/api')

# Import routes to register them with blueprints
from . import requirements, internal_docs, mapping

__all__ = [
    'requirements_bp',
    'internal_docs_bp',
    'mapping_bp'
]