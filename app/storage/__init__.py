"""Storage backends for PuerHumidity."""

from app.storage.base import StorageBase
from app.storage.local_storage import LocalStorage

__all__ = ["StorageBase", "LocalStorage"]
