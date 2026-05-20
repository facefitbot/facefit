from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.local import local_storage


def _remove_children(path: Path) -> int:
    if not path.exists():
        return 0
    removed = 0
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def main() -> None:
    targets = [
        Path(local_storage.abs_path("previews/protocol_v4")),
        Path(local_storage.abs_path("protocols/v4")),
    ]
    total = 0
    for target in targets:
        removed = _remove_children(target)
        total += removed
        print(f"cleaned {target}: {removed}")
    print(f"removed_entries={total}")


if __name__ == "__main__":
    main()
