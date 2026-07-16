"""Batch import supplier Excel/PDF files from a folder."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from backend.config import DEFAULT_MULTIPLIER
from backend.import_service import ImportService
from backend.repository import PriceBookRepository


EXCEL_EXT = {".xlsx", ".xls", ".xlsm"}
PDF_EXT = {".pdf"}
SKIP_NAME_BITS = ("~$", ".ds_store")


@dataclass
class BatchFileResult:
    path: str
    vendor: str
    status: str  # ok | skipped | error
    inserted: int = 0
    updated: int = 0
    total: int = 0
    message: str = ""
    markup: Optional[float] = None


@dataclass
class BatchResult:
    files: list[BatchFileResult] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.files if f.status == "ok")

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.files if f.status == "error")

    @property
    def rows_total(self) -> int:
        return sum(f.total for f in self.files)


def _vendor_from_name(path: Path, override: str = "") -> str:
    if override:
        return override
    stem = path.stem
    # strip common noise
    for bit in (
        " wholesale price list",
        " Wholesale Price List",
        " Retail Pricelist",
        " retail pricelist",
        " Price List",
        " Pricelist",
        " price list",
        " pricelist",
        " Pricebook",
        " pricebook",
    ):
        if bit.lower() in stem.lower():
            # case-insensitive replace once
            idx = stem.lower().find(bit.lower())
            if idx >= 0:
                stem = (stem[:idx] + stem[idx + len(bit) :]).strip(" _-")
    return stem[:80] or path.name


class BatchImporter:
    def __init__(
        self,
        repo: PriceBookRepository,
        imports: Optional[ImportService] = None,
    ):
        self.repo = repo
        self.imports = imports or ImportService()

    def discover(self, folder: str | Path, recursive: bool = False) -> list[Path]:
        root = Path(folder)
        if not root.is_dir():
            return []
        pattern = "**/*" if recursive else "*"
        files = []
        for p in sorted(root.glob(pattern)):
            if not p.is_file():
                continue
            name_l = p.name.lower()
            if any(b in name_l for b in SKIP_NAME_BITS):
                continue
            if p.suffix.lower() in EXCEL_EXT | PDF_EXT:
                files.append(p)
        return files

    def run(
        self,
        folder: str | Path,
        *,
        recursive: bool = False,
        mode: str = "upsert",
        multiplier: float = DEFAULT_MULTIPLIER,
        use_workbook_markup: bool = True,
        vendor_override: str = "",
        excel_only: bool = False,
        progress: Optional[Callable[[str], None]] = None,
    ) -> BatchResult:
        result = BatchResult()
        files = self.discover(folder, recursive=recursive)
        if excel_only:
            files = [f for f in files if f.suffix.lower() in EXCEL_EXT]

        for path in files:
            vendor = _vendor_from_name(path, vendor_override)
            if progress:
                progress(f"Importing {path.name}…")
            try:
                data = path.read_bytes()
                if path.suffix.lower() in EXCEL_EXT:
                    prev = self.imports.preview_excel(
                        data,
                        filename=path.name,
                        vendor=vendor,
                        multiplier=multiplier,
                        use_workbook_markup=use_workbook_markup,
                    )
                    rows = prev.rows
                    markup = prev.detected_markup
                    mult_used = prev.multiplier_used
                else:
                    prev_pdf = self.imports.preview_pdf(
                        data,
                        filename=path.name,
                        vendor=vendor,
                        multiplier=multiplier,
                        max_pages=None,
                    )
                    rows = prev_pdf.rows
                    markup = None
                    mult_used = multiplier

                if not rows:
                    result.files.append(
                        BatchFileResult(
                            path=str(path),
                            vendor=vendor,
                            status="skipped",
                            message="0 rows parsed",
                            markup=markup,
                        )
                    )
                    continue

                # apply mult to rows if needed
                for r in rows:
                    r["multiplier"] = mult_used
                    if r.get("base_price") is not None:
                        r["adjusted_price"] = round(
                            float(r["base_price"]) * float(mult_used), 2
                        )

                if mode == "replace_source":
                    deleted = self.repo.delete_by_source(path.name)
                    n = self.repo.insert_rows(rows)
                    counts = {
                        "inserted": n,
                        "updated": 0,
                        "total": n,
                        "deleted": deleted,
                    }
                elif mode == "upsert":
                    counts = self.repo.upsert_rows(rows)
                else:
                    n = self.repo.insert_rows(rows)
                    counts = {"inserted": n, "updated": 0, "total": n}

                # remember vendor mult
                self.repo.set_vendor_multiplier(vendor, float(mult_used))

                result.files.append(
                    BatchFileResult(
                        path=str(path),
                        vendor=vendor,
                        status="ok",
                        inserted=counts.get("inserted", 0),
                        updated=counts.get("updated", 0),
                        total=counts.get("total", 0),
                        message=f"mult={mult_used:g}",
                        markup=markup,
                    )
                )
            except Exception as e:
                result.files.append(
                    BatchFileResult(
                        path=str(path),
                        vendor=vendor,
                        status="error",
                        message=str(e)[:300],
                    )
                )
        return result
