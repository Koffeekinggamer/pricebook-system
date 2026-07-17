"""
Public facade for the Price Book backend.

UI and scripts should prefer this over touching repository/importers directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional, Union

import pandas as pd

from backend.batch import BatchImporter, BatchResult
from backend.config import DB_PATH, DEFAULT_MULTIPLIER, DEFAULT_SEARCH_LIMIT
from backend.db import init_db
from backend.export import to_csv_bytes, to_excel_bytes, to_pdf_bytes
from backend.import_service import ExcelImportPreview, ImportService, PdfImportPreview
from backend.normalize import map_columns, read_excel_bytes
from backend.quotes import QuoteRepository
from backend.repository import PriceBookRepository


class PriceBookService:
    """Single entry point: catalog, import, pricing, quotes, batch, export."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.repo = PriceBookRepository(self.db_path)
        self.quotes = QuoteRepository(self.db_path)
        self.imports = ImportService()
        self.batch = BatchImporter(self.repo, self.imports)
        self._ready = False

    # ------------------------------------------------------------------ lifecycle
    def init(self) -> Path:
        path = init_db(self.db_path)
        self._ready = True
        return path

    def ensure_ready(self) -> None:
        if not self._ready:
            self.init()

    @property
    def path(self) -> Path:
        return self.db_path

    # ------------------------------------------------------------------ read
    def stats(self) -> dict:
        self.ensure_ready()
        s = self.repo.stats()
        s["quotes"] = self.quotes.quote_count()
        return s

    def row_count(self) -> int:
        self.ensure_ready()
        return self.repo.row_count()

    def search(
        self,
        query: str = "",
        *,
        collection: Optional[str] = None,
        vendor: Optional[str] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> pd.DataFrame:
        self.ensure_ready()
        return self.repo.search(
            query, collection=collection, vendor=vendor, limit=limit
        )

    def get_row(self, row_id: int) -> Optional[dict]:
        self.ensure_ready()
        return self.repo.get_row_by_id(row_id)

    def list_vendors(self) -> list[str]:
        self.ensure_ready()
        return self.repo.list_vendors()

    def list_collections(self, vendor: Optional[str] = None) -> list[str]:
        self.ensure_ready()
        return self.repo.list_collections(vendor=vendor)

    def list_source_files(self) -> list[str]:
        self.ensure_ready()
        return self.repo.list_source_files()

    def vendor_summary(self) -> pd.DataFrame:
        self.ensure_ready()
        return self.repo.vendor_summary()

    def find_duplicates(self, limit: int = 100) -> pd.DataFrame:
        self.ensure_ready()
        return self.repo.find_duplicate_groups(limit=limit)

    def cleanup_duplicates(self, *, dry_run: bool = True) -> dict:
        self.ensure_ready()
        return self.repo.cleanup_duplicates(dry_run=dry_run)

    # ------------------------------------------------------------------ write
    def add_rows(self, rows: list[dict], *, mode: str = "append") -> dict:
        """
        Commit rows to master.

        Modes:
          - replace_vendor / replace_builder / replace_source:
              delete ALL rows for this builder, then insert (one catalog per builder)
          - upsert: update matching identities, insert new
          - append: always insert
        """
        self.ensure_ready()
        if not rows:
            return {"inserted": 0, "updated": 0, "deleted": 0, "total": 0}

        from backend.standardize import resolve_builder_vendor

        # Canonical vendor on every row (prevents filename twins)
        vend_raw = rows[0].get("vendor") or ""
        source = rows[0].get("source_file") or ""
        vend = resolve_builder_vendor(vend_raw, filename=str(source)) or vend_raw
        for r in rows:
            r["vendor"] = vend

        deleted = 0
        if mode in ("replace_source", "replace_vendor", "replace_builder"):
            # One builder = one book: wipe this vendor entirely, then load
            if vend:
                deleted = self.repo.delete_by_vendor(vend)
            elif source:
                deleted = self.repo.delete_by_source(source)
            n = self.repo.insert_rows(rows)
            return {
                "inserted": n,
                "updated": 0,
                "deleted": deleted,
                "total": n,
            }

        if mode == "upsert":
            result = self.repo.upsert_rows(rows)
            result["deleted"] = 0
            return result

        n = self.repo.insert_rows(rows)
        return {"inserted": n, "updated": 0, "deleted": 0, "total": n}

    def delete_by_source(self, source_file: str) -> int:
        self.ensure_ready()
        return self.repo.delete_by_source(source_file)

    def delete_by_vendor(self, vendor: str) -> int:
        self.ensure_ready()
        return self.repo.delete_by_vendor(vendor)

    # ------------------------------------------------------------------ pricing
    def get_vendor_multiplier(
        self, vendor: str, default: float = DEFAULT_MULTIPLIER
    ) -> float:
        self.ensure_ready()
        return self.repo.get_vendor_multiplier(vendor, default=default)

    def set_vendor_multiplier(
        self, vendor: str, multiplier: float, notes: str = ""
    ) -> None:
        self.ensure_ready()
        self.repo.set_vendor_multiplier(vendor, multiplier, notes=notes)

    def list_vendor_settings(self) -> pd.DataFrame:
        self.ensure_ready()
        return self.repo.list_vendor_settings()

    def reapply_multiplier(
        self, new_mult: float, *, vendor: Optional[str] = None
    ) -> int:
        self.ensure_ready()
        return self.repo.reapply_multiplier(new_mult, vendor=vendor)

    def recompute_adjusted(self, vendor: Optional[str] = None) -> int:
        self.ensure_ready()
        return self.repo.recompute_adjusted(vendor=vendor)

    def standardize_master(self) -> dict:
        """Apply canonical field rules to every master row (in place)."""
        self.ensure_ready()
        return self.repo.standardize_all()

    def resolve_multiplier(
        self,
        vendor: str = "",
        sidebar_mult: float = DEFAULT_MULTIPLIER,
        detected_markup: Optional[float] = None,
        prefer_workbook: bool = False,
        prefer_saved_vendor: bool = True,
    ) -> float:
        if prefer_workbook and detected_markup:
            return float(detected_markup)
        if prefer_saved_vendor and vendor:
            saved = self.get_vendor_multiplier(vendor, default=-1.0)
            if saved > 0:
                return float(saved)
        return float(sidebar_mult)

    # ------------------------------------------------------------------ import
    def preview_excel(self, data: bytes, **kwargs) -> ExcelImportPreview:
        return self.imports.preview_excel(data, **kwargs)

    def preview_excel_manual(self, data: bytes, **kwargs) -> list[dict]:
        return self.imports.preview_excel_manual(data, **kwargs)

    def preview_pdf(self, data: bytes, **kwargs) -> PdfImportPreview:
        return self.imports.preview_pdf(data, **kwargs)

    def map_columns(self, df: pd.DataFrame) -> dict[str, str]:
        return map_columns(df)

    def read_excel_bytes(self, data: bytes) -> pd.DataFrame:
        return read_excel_bytes(data)

    def batch_import(
        self,
        folder: str | Path,
        *,
        recursive: bool = False,
        mode: str = "upsert",
        multiplier: float = DEFAULT_MULTIPLIER,
        use_workbook_markup: bool = True,
        vendor_override: str = "",
        excel_only: bool = True,
        progress: Optional[Callable[[str], None]] = None,
    ) -> BatchResult:
        self.ensure_ready()
        return self.batch.run(
            folder,
            recursive=recursive,
            mode=mode,
            multiplier=multiplier,
            use_workbook_markup=use_workbook_markup,
            vendor_override=vendor_override,
            excel_only=excel_only,
            progress=progress,
        )

    def discover_batch_files(
        self, folder: str | Path, recursive: bool = False
    ) -> list[Path]:
        return self.batch.discover(folder, recursive=recursive)

    # ------------------------------------------------------------------ quotes
    def create_quote(self, **kwargs) -> int:
        self.ensure_ready()
        return self.quotes.create_quote(**kwargs)

    def update_quote(self, quote_id: int, **kwargs) -> None:
        self.ensure_ready()
        self.quotes.update_quote(quote_id, **kwargs)

    def delete_quote(self, quote_id: int) -> None:
        self.ensure_ready()
        self.quotes.delete_quote(quote_id)

    def get_quote(self, quote_id: int) -> Optional[dict]:
        self.ensure_ready()
        return self.quotes.get_quote(quote_id)

    def list_quotes(self, limit: int = 100) -> pd.DataFrame:
        self.ensure_ready()
        return self.quotes.list_quotes(limit=limit)

    def quote_lines(self, quote_id: int) -> pd.DataFrame:
        self.ensure_ready()
        return self.quotes.list_lines(quote_id)

    def quote_totals(self, quote_id: int) -> dict[str, Any]:
        self.ensure_ready()
        return self.quotes.totals(quote_id)

    def add_quote_line_from_id(
        self,
        quote_id: int,
        pricebook_id: int,
        *,
        qty: float = 1.0,
        line_discount_pct: float = 0.0,
    ) -> int:
        self.ensure_ready()
        row = self.repo.get_row_by_id(pricebook_id)
        if not row:
            raise ValueError(f"No pricebook row id={pricebook_id}")
        return self.quotes.add_line_from_pricebook(
            quote_id, row, qty=qty, line_discount_pct=line_discount_pct
        )

    def add_quote_line_from_row(
        self, quote_id: int, pricebook_row: dict, **kwargs
    ) -> int:
        self.ensure_ready()
        return self.quotes.add_line_from_pricebook(
            quote_id, pricebook_row, **kwargs
        )

    def add_custom_quote_line(self, quote_id: int, **kwargs) -> int:
        self.ensure_ready()
        return self.quotes.add_custom_line(quote_id, **kwargs)

    def update_quote_line(self, line_id: int, **kwargs) -> None:
        self.ensure_ready()
        self.quotes.update_line(line_id, **kwargs)

    def delete_quote_line(self, line_id: int) -> None:
        self.ensure_ready()
        self.quotes.delete_line(line_id)

    def export_quote_excel(self, quote_id: int) -> bytes:
        self.ensure_ready()
        return self.quotes.export_excel(quote_id)

    def export_quote_pdf(self, quote_id: int) -> bytes:
        self.ensure_ready()
        return self.quotes.export_pdf(quote_id)

    # ------------------------------------------------------------------ export catalog
    def export_excel(self, df: pd.DataFrame) -> bytes:
        return to_excel_bytes(df)

    def export_csv(self, df: pd.DataFrame) -> bytes:
        return to_csv_bytes(df)

    def export_pdf(self, df: pd.DataFrame, title: str = "Price Book Export") -> bytes:
        return to_pdf_bytes(df, title=title)
