"""xpx: restricted-XML / XPath-1.0-subset extraction backend."""

from .errors import QueryError, Reject
from .service import run, run_json_text, validate_input

__all__ = ['Reject', 'QueryError', 'run', 'run_json_text', 'validate_input']
