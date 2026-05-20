from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.local import local_storage


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def main() -> None:
    root = Path(local_storage.root)
    targets = [
        root / "previews" / "protocol_v2",
        root / "protocols",
    ]
    removed: list[str] = []
    for target in targets:
        if target.exists():
            _remove_path(target)
            removed.append(str(target))

    for path in root.rglob("*protocol*.png"):
        if "photos" in path.parts:
            continue
        if path.exists():
            path.unlink()
            removed.append(str(path))

    print("Removed protocol cache:")
    for path in removed:
        print(path)


if __name__ == "__main__":
    main()
