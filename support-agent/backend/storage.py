"""Object storage for tickets and knowledge.

Azure Blob Storage is the system of record in Azure. ``LocalStore`` mirrors the
same container/blob model in a folder so the app and its tests run offline.
"""

import hashlib
import os
import re
import threading
from pathlib import Path
from typing import Protocol

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


class NotFoundError(Exception):
    """The requested blob does not exist."""


class ConflictError(Exception):
    """The blob changed (or already exists) since the caller last read it."""


class Store(Protocol):
    def list_names(self, container: str) -> list[str]: ...

    def read(self, container: str, name: str) -> tuple[str, str]: ...

    def write(
        self, container: str, name: str, text: str, *,
        etag: str | None = None, create_only: bool = False,
    ) -> str: ...


def _check_name(value: str) -> str:
    if not NAME_PATTERN.fullmatch(value):
        raise ValueError(f"Unsafe container or blob name: {value!r}")
    return value


class LocalStore:
    """Folder-backed store for local development and tests (single process)."""

    _lock = threading.Lock()

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, container: str, name: str | None = None) -> Path:
        folder = self.root / _check_name(container)
        return folder if name is None else folder / _check_name(name)

    @staticmethod
    def _etag(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def list_names(self, container: str) -> list[str]:
        folder = self._path(container)
        if not folder.is_dir():
            return []
        return sorted(item.name for item in folder.iterdir()
                      if item.is_file() and not item.name.startswith("."))

    def read(self, container: str, name: str) -> tuple[str, str]:
        path = self._path(container, name)
        try:
            data = path.read_bytes()
        except FileNotFoundError as error:
            raise NotFoundError(name) from error
        return data.decode("utf-8"), self._etag(data)

    def write(self, container, name, text, *, etag=None, create_only=False):
        path = self._path(container, name)
        data = text.encode("utf-8")
        with self._lock:
            if create_only and path.exists():
                raise ConflictError(name)
            if etag is not None:
                try:
                    current = self._etag(path.read_bytes())
                except FileNotFoundError as error:
                    raise ConflictError(name) from error
                if current != etag:
                    raise ConflictError(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_bytes(data)
            os.replace(temporary, path)
        return self._etag(data)


class BlobStore:
    """Azure Blob Storage using Microsoft Entra ID (managed identity in App Service)."""

    def __init__(self, service_client):
        self.service = service_client

    @classmethod
    def from_settings(cls, account_url: str = "", connection_string: str = "") -> "BlobStore":
        from azure.storage.blob import BlobServiceClient

        if connection_string:
            return cls(BlobServiceClient.from_connection_string(connection_string))
        from azure.identity import DefaultAzureCredential

        return cls(BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential()))

    def _blob(self, container: str, name: str):
        return self.service.get_blob_client(_check_name(container), _check_name(name))

    def list_names(self, container: str) -> list[str]:
        client = self.service.get_container_client(_check_name(container))
        return sorted(blob.name for blob in client.list_blobs())

    def read(self, container: str, name: str) -> tuple[str, str]:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            downloader = self._blob(container, name).download_blob()
        except ResourceNotFoundError as error:
            raise NotFoundError(name) from error
        return downloader.readall().decode("utf-8"), downloader.properties.etag

    def write(self, container, name, text, *, etag=None, create_only=False):
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
        from azure.storage.blob import ContentSettings

        content_type = "text/markdown" if name.endswith(".md") else "application/json"
        options = {"content_settings": ContentSettings(content_type=content_type)}
        if create_only:
            options["overwrite"] = False
        else:
            options["overwrite"] = True
            if etag is not None:
                options.update(etag=etag, match_condition=MatchConditions.IfNotModified)
        try:
            result = self._blob(container, name).upload_blob(text.encode("utf-8"), **options)
        except (ResourceExistsError, ResourceModifiedError) as error:
            raise ConflictError(name) from error
        return result["etag"]


def store_from_environment() -> Store:
    """Choose Azure Blob Storage when configured, otherwise a local folder."""
    account_url = os.getenv("STORAGE_ACCOUNT_URL", "").strip()
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if account_url or connection_string:
        if account_url and not re.fullmatch(r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net/?", account_url):
            raise ValueError("STORAGE_ACCOUNT_URL must look like https://<account>.blob.core.windows.net")
        return BlobStore.from_settings(account_url, connection_string)
    default_dir = Path(__file__).resolve().parent / ".data"
    return LocalStore(os.getenv("DATA_DIR", str(default_dir)))
