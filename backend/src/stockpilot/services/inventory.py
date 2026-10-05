from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.api.schemas import InventoryInput
from stockpilot.db.models import Inbound, InventoryItem, Snapshot
from stockpilot.db.repositories import latest, scoped, serialize
from stockpilot.worker.queue import dataset_lock


def edit_inventory(
    session: Session, identifier: str, dataset_id: str, inputs: InventoryInput
) -> Snapshot:
    dataset_lock(session, dataset_id)
    item = scoped(session, InventoryItem, identifier, dataset_id)
    current = latest(session, Snapshot, dataset_id)
    if current.id != item.snapshot_id or current.version != inputs.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "Inventory snapshot changed; refresh")
    if inputs.reserved > inputs.on_hand:
        raise AppError(400, "INVALID_INVENTORY", "Reserved units exceed on-hand units")
    snapshot = Snapshot(
        dataset_id=dataset_id,
        as_of_date=current.as_of_date,
        version=current.version + 1,
        origin="local edit",
    )
    session.add(snapshot)
    session.flush()
    for previous in session.scalars(
        select(InventoryItem).where(InventoryItem.snapshot_id == current.id)
    ):
        values = serialize(previous)
        for key in ("id", "created_at", "snapshot_id"):
            values.pop(key)
        if previous.id == identifier:
            values.update(on_hand=inputs.on_hand, reserved=inputs.reserved)
        session.add(InventoryItem(snapshot_id=snapshot.id, **values))
    for order in session.scalars(select(Inbound).where(Inbound.snapshot_id == current.id)):
        values = serialize(order)
        for key in ("id", "created_at", "snapshot_id"):
            values.pop(key)
        session.add(Inbound(snapshot_id=snapshot.id, **values))
    return snapshot
