import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

RULE_VERSION = "1.0"
FIELDS = {
    "sales": [
        "external_row_id",
        "invoice_id",
        "product_sku",
        "description",
        "quantity",
        "unit_price",
        "invoice_datetime",
        "country",
    ],
    "inventory": [
        "product_sku",
        "on_hand_units",
        "reserved_units",
        "unit_cost",
        "currency",
        "supplier_code",
        "lead_time_days",
        "pack_size",
        "minimum_order_units",
        "holding_cost_per_unit_day",
        "stockout_penalty_per_unit",
    ],
    "inbound": ["external_order_id", "product_sku", "quantity_units", "expected_arrival_date"],
}


def integer(value: str, minimum: int | None = None) -> int:
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise ValueError("Expected an integer")
    number = int(parsed)
    if number < -(2**31) or number > 2**31 - 1:
        raise ValueError("Integer exceeds supported 32-bit range")
    if minimum is not None and number < minimum:
        raise ValueError(f"Must be at least {minimum}")
    return number


def money(value: str, minimum: Decimal = Decimal(0)) -> Decimal:
    result = Decimal(value)
    if not result.is_finite() or result < minimum or result >= Decimal("10000000000"):
        raise ValueError("Invalid non-negative decimal; use decimal point")
    if result != result.quantize(Decimal("0.0001")):
        raise ValueError("Money supports at most four decimal places")
    return result


def validate_csv(
    content: bytes,
    kind: str,
    mapping: dict[str, str],
    currency: str,
    timezone: str,
    existing_ids: set[str] | None = None,
) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="strict")
    try:
        delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    required = set(FIELDS[kind]) - (
        {"description", "country", "external_row_id"} if kind == "sales" else set()
    )
    missing = [field for field in required if mapping.get(field, field) not in headers]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    seen = set(existing_ids or set())
    signatures: set[tuple[str, ...]] = set()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for row_number, original in enumerate(reader, start=2):
        row = {
            field: (original.get(mapping.get(field, field)) or "").strip() for field in FIELDS[kind]
        }
        try:
            if None in original:
                raise ValueError("Row has more values than header columns")
            if not row["product_sku"]:
                raise ValueError("SKU is required")
            if len(row["product_sku"]) > 80:
                raise ValueError("SKU exceeds 80 characters")
            if kind == "sales":
                quantity = integer(row["quantity"])
                price = Decimal(row["unit_price"])
                if not price.is_finite() or abs(price) >= Decimal("10000000000"):
                    raise ValueError("Invalid price")
                if price != price.quantize(Decimal("0.0001")):
                    raise ValueError("Price supports at most four decimal places")
                dt = datetime.fromisoformat(row["invoice_datetime"])
                local = (
                    dt.replace(tzinfo=ZoneInfo(timezone))
                    if dt.tzinfo is None
                    else dt.astimezone(ZoneInfo(timezone))
                )
                row["invoice_datetime"] = local.isoformat()
                row["day"] = local.date().isoformat()
                row["quantity"] = str(quantity)
                row["unit_price"] = str(price)
                cancellation = row["invoice_id"].upper().startswith("C") or quantity < 0
                row["cancellation"] = str(cancellation)
                if cancellation or quantity == 0 or price <= 0:
                    exclusions.append(
                        {
                            "row": row_number,
                            "message": "Cancellation, return or non-positive demand/price",
                            "category": "demand_exclusion",
                        }
                    )
                if not row["description"]:
                    row["description"] = row["product_sku"]
                    warnings.append(
                        {"row": row_number, "message": "Missing description; using SKU"}
                    )
                if (
                    len(row["description"]) > 300
                    or len(row["invoice_id"]) > 120
                    or len(row["country"]) > 80
                    or len(row["external_row_id"]) > 160
                ):
                    raise ValueError("Text field exceeds supported length")
                identifier = row["external_row_id"]
                if identifier and identifier in seen:
                    raise ValueError("Duplicate external_row_id")
                if identifier:
                    seen.add(identifier)
                signature = tuple(
                    row[field] for field in FIELDS[kind] if field != "external_row_id"
                )
                if not identifier and signature in signatures:
                    warnings.append(
                        {
                            "row": row_number,
                            "message": "Identical row without ID; retained as potentially legitimate",
                        }
                    )
                signatures.add(signature)
            elif kind == "inventory":
                for field in ["on_hand_units", "reserved_units", "minimum_order_units"]:
                    row[field] = str(integer(row[field], 0))
                for field in ["pack_size", "lead_time_days"]:
                    row[field] = str(integer(row[field], 1))
                if int(row["lead_time_days"]) > 30:
                    raise ValueError("Lead time must be 1–30 days")
                if int(row["reserved_units"]) > int(row["on_hand_units"]):
                    raise ValueError("Reserved units exceed on-hand units")
                for field in [
                    "unit_cost",
                    "holding_cost_per_unit_day",
                    "stockout_penalty_per_unit",
                ]:
                    row[field] = str(money(row[field]))
                if row["currency"] != currency:
                    raise ValueError("Currency does not match dataset")
                if not row["supplier_code"] or len(row["supplier_code"]) > 80:
                    raise ValueError("Supplier code must contain 1–80 characters")
                if row["product_sku"] in seen:
                    raise ValueError("Duplicate inventory SKU")
                seen.add(row["product_sku"])
            else:
                row["quantity_units"] = str(integer(row["quantity_units"], 1))
                row["expected_arrival_date"] = (
                    datetime.fromisoformat(row["expected_arrival_date"]).date().isoformat()
                )
                if row["external_order_id"] in seen or not row["external_order_id"]:
                    raise ValueError("Missing or duplicate external_order_id")
                if len(row["external_order_id"]) > 160:
                    raise ValueError("Order identifier exceeds 160 characters")
                seen.add(row["external_order_id"])
            rows.append({"row": row_number, "values": row})
        except (ValueError, InvalidOperation, OverflowError) as exc:
            errors.append({"row": row_number, "message": str(exc)})
    dates = [row["values"]["day"] for row in rows if "day" in row["values"]]
    return {
        "rules_version": RULE_VERSION,
        "headers": headers,
        "received": reader.line_num - 1,
        "valid": len(rows),
        "errors": errors,
        "warnings": warnings,
        "exclusions": exclusions,
        "duplicates": sum("Duplicate" in e["message"] for e in errors),
        "min_date": min(dates) if dates else None,
        "max_date": max(dates) if dates else None,
        "rows": rows,
        "delimiter": delimiter,
    }
