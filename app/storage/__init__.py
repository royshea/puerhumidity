"""Storage backends for PuerHumidity."""

from app.storage.base import StorageBase
from app.storage.local_storage import LocalStorage
from app.storage.table_storage import TableStorage

__all__ = ["StorageBase", "LocalStorage", "TableStorage", "get_storage", "init_storage"]

# Global storage instance - initialized by app factory
_storage: StorageBase | None = None


def get_storage() -> StorageBase:
    """Get the configured storage instance.

    Returns:
        The storage backend configured for this app.

    Raises:
        RuntimeError: If called before init_storage().
    """
    if _storage is None:
        raise RuntimeError("Storage not initialized. Call init_storage() first.")
    return _storage


def init_storage(storage: StorageBase) -> None:
    """Initialize the global storage instance.

    Args:
        storage: The storage backend to use.
    """
    global _storage
    _storage = storage
