from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self) -> None:
        self.root = settings.storage_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def abs_path(self, relative_path: str) -> str:
        return str((self.root / relative_path).resolve())

    def save_bytes(self, relative_path: str, data: bytes) -> str:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return relative_path

    def copy_file(self, source_path: str, relative_path: str) -> str:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        return relative_path

    def public_url(self, relative_path: str) -> str:
        return f"{settings.backend_url.rstrip('/')}/storage/{relative_path.lstrip('/')}"


local_storage = LocalStorage()

