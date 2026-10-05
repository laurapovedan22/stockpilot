import json
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from stockpilot.api.dependencies import DB, local_only
from stockpilot.api.errors import AppError
from stockpilot.api.schemas import ConfirmInput
from stockpilot.config import settings
from stockpilot.db.models import ImportBatch
from stockpilot.db.repositories import scoped, serialize
from stockpilot.services.imports import preview, validate_confirmation
from stockpilot.worker.queue import enqueue

router = APIRouter()


@router.post("/datasets/{dataset_id}/imports/preview", dependencies=[Depends(local_only)])
async def preview_import(
    dataset_id: str,
    db: DB,
    file: UploadFile = File(),
    kind: Literal["sales", "inventory", "inbound"] = Form(),
    mapping: str = Form("{}"),
):
    content = await file.read(settings.max_csv_bytes + 1)
    try:
        parsed = json.loads(mapping)
        if not isinstance(parsed, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
        ):
            raise ValueError("Mapping must be a string-to-string object")
    except (ValueError, TypeError) as exc:
        raise AppError(400, "INVALID_MAPPING", "Mapping must be a JSON object") from exc
    batch = preview(db, dataset_id, content, kind, parsed)
    db.commit()
    return {
        "token": batch.id,
        "status": batch.status,
        "checksum": batch.checksum,
        "report": {**batch.report, "rows": batch.report.get("rows", [])[:25]},
    }


@router.post(
    "/datasets/{dataset_id}/imports/confirm", status_code=202, dependencies=[Depends(local_only)]
)
def confirm_import(dataset_id: str, inputs: ConfirmInput, db: DB):
    batch = scoped(db, ImportBatch, inputs.token, dataset_id)
    validate_confirmation(batch, inputs.excluded_rows)
    job = enqueue(
        db,
        dataset_id,
        "import",
        {
            "batch_id": batch.id,
            "excluded_rows": inputs.excluded_rows,
            "last_day_complete": inputs.last_day_complete,
        },
        key=batch.key,
    )
    db.commit()
    return serialize(job)


@router.get("/imports/{identifier}")
def import_report(identifier: str, dataset_id: str, db: DB):
    batch = scoped(db, ImportBatch, identifier, dataset_id)
    return {k: v for k, v in serialize(batch).items() if k != "path"} | {
        "report": {k: v for k, v in batch.report.items() if k != "rows"}
    }
