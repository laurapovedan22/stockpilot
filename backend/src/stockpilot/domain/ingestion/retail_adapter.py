import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

SOURCE = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
ALIASES = {
    "invoice_id": ("Invoice", "InvoiceNo"),
    "product_sku": ("StockCode",),
    "description": ("Description",),
    "quantity": ("Quantity",),
    "unit_price": ("Price", "UnitPrice"),
    "invoice_datetime": ("InvoiceDate",),
    "country": ("Country",),
}


def fetch(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "online_retail_II.xlsx"
    if path.exists():
        return path
    archive = directory / "retail.zip"
    with httpx.stream("GET", SOURCE, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        size = 0
        with archive.open("wb") as target:
            for block in response.iter_bytes():
                size += len(block)
                if size > 100 * 1024 * 1024:
                    raise ValueError("Source archive exceeds 100 MiB")
                target.write(block)
    with zipfile.ZipFile(archive) as bundle:
        entry = next(info for info in bundle.infolist() if Path(info.filename).name == path.name)
        if entry.file_size > 100 * 1024 * 1024:
            raise ValueError("XLSX exceeds 100 MiB")
        path.write_bytes(bundle.read(entry))
    manifest = {
        "source": SOURCE,
        "doi": "10.24432/C5CG6D",
        "license": "CC BY 4.0",
        "creator": "Chen, D. (2012)",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (directory / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return path


def convert(path: Path, destination: Path) -> dict:
    if path.suffix.lower() != ".xlsx" or path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Only XLSX up to 100 MiB accepted")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frames = []
    manifest: dict[str, Any] = {"checksum": digest, "sheets": {}, "excluded_noncommercial": 0}
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for sheet in workbook.sheet_names:
            frame = pd.read_excel(workbook, sheet_name=sheet, dtype={"StockCode": str})
            mapping = {}
            for canonical, aliases in ALIASES.items():
                found = [alias for alias in aliases if alias in frame.columns]
                if len(found) != 1:
                    raise ValueError(
                        f"Sheet {sheet}: expected exactly one of {aliases}; actual {list(frame.columns)}"
                    )
                mapping[found[0]] = canonical
            manifest["sheets"][sheet] = {
                "headers": list(frame.columns),
                "mapping": mapping,
                "rows": len(frame),
            }
            frame = frame.rename(columns=mapping)[list(ALIASES)]
            frame["external_row_id"] = [f"{digest}:{sheet}:{row + 2}" for row in range(len(frame))]
            frame["product_sku"] = frame.product_sku.str.strip()
            # UCI merchandise follows numeric catalog codes, optionally one letter suffix.
            commercial = frame.product_sku.map(
                lambda value: bool(re.fullmatch(r"\d{5}[A-Za-z]?", str(value)))
            )
            manifest["excluded_noncommercial"] += int((~commercial).sum())
            frame = frame[commercial].copy()
            frame["invoice_datetime"] = pd.to_datetime(frame.invoice_datetime).dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
            frames.append(frame)
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(destination, index=False)
    manifest["canonical_rows"] = len(combined)
    manifest["maximum_timestamp"] = str(combined.invoice_datetime.max())
    destination.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
