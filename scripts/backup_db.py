#!/usr/bin/env python3
"""Private local backup of master_pricebook.db (not for GitHub)."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    db = root / "master_pricebook.db"
    backup_dir = Path(
        os.environ.get(
            "FAF_PRICEBOOK_BACKUP_DIR",
            Path.home() / "Documents" / "FAF-pricebook-backups",
        )
    )
    if not db.is_file():
        print(f"No database at {db}")
        return 1

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"master_pricebook-{stamp}.db"

    # Consistent snapshot via SQLite backup API
    src = sqlite3.connect(str(db))
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    # Prune to newest 20
    backups = sorted(
        backup_dir.glob("master_pricebook-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[20:]:
        old.unlink(missing_ok=True)

    size_mb = dest.stat().st_size / (1024 * 1024)
    print(f"Backed up → {dest} ({size_mb:.1f} MB)")
    print(f"Backups in {backup_dir}: {min(len(backups), 20)} kept (max 20)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
