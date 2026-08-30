"""External app connectors: catalog, encrypted credential store, live verification."""

from .registry import CATALOG, ConnectorSpec, get_spec, missing_required, spec_to_dict
from .store import ConnectorStore
from .verify import verify

__all__ = [
    "CATALOG",
    "ConnectorSpec",
    "ConnectorStore",
    "get_spec",
    "missing_required",
    "spec_to_dict",
    "verify",
]
