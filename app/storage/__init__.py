"""Storage backends for PuerHumidity."""

from app.storage.base import StorageBase
from app.storage.local_storage import LocalStorage
from app.storage.table_storage import TableStorage

__all__ = ["StorageBase", "LocalStorage", "TableStorage"]
