from datetime import date

import pytest

from stockpilot.domain.forecasting.aggregation import daily_series
from stockpilot.domain.ingestion.validation import validate_csv

HEADER = "external_row_id,invoice_id,product_sku,description,quantity,unit_price,invoice_datetime,country\n"


def test_leading_zero_returns_description_and_duplicate():
    text = (
        HEADER
        + "a,I,00012,,3,2.50,2024-01-01T12:00:00,UK\n"
        + "b,C100,00012,Mug,-2,2.50,2024-01-02T12:00:00,UK\n"
        + "a,I,00012,Mug,3,2.50,2024-01-03T12:00:00,UK\n"
    )
    report = validate_csv(text.encode(), "sales", {}, "GBP", "Europe/London")
    assert report["rows"][0]["values"]["product_sku"] == "00012"
    assert report["rows"][0]["values"]["description"] == "00012"
    assert len(report["warnings"]) == 1
    assert len(report["exclusions"]) == 1
    assert report["errors"][0]["row"] == 4


def test_identical_rows_without_identifier_are_retained():
    line = ",I,00012,Mug,3,2.5,2024-01-01T12:00:00,UK\n"
    result = validate_csv((HEADER + line + line).encode(), "sales", {}, "GBP", "Europe/London")
    assert len(result["rows"]) == 2
    assert "potentially legitimate" in result["warnings"][0]["message"]


def test_local_date_and_fractional_quantity():
    content = (
        HEADER
        + "a,I,00012,Mug,1,2,2024-06-01T23:30:00+00:00,UK\n"
        + "b,I,00012,Mug,1.5,2,2024-06-02T00:00:00,UK\n"
    )
    result = validate_csv(content.encode(), "sales", {}, "GBP", "Europe/London")
    assert result["rows"][0]["values"]["day"] == "2024-06-02"
    assert result["errors"][0]["row"] == 3


def test_inventory_blocks_reserved_currency_pack():
    header = "product_sku,on_hand_units,reserved_units,unit_cost,currency,supplier_code,lead_time_days,pack_size,minimum_order_units,holding_cost_per_unit_day,stockout_penalty_per_unit\n"
    result = validate_csv(
        (
            header
            + "00012,2,3,1,GBP,S,7,6,12,.01,2\n"
            + "00013,3,0,1,EUR,S,7,6,12,.01,2\n"
            + "00014,3,0,1,GBP,S,7,0,12,.01,2\n"
        ).encode(),
        "inventory",
        {},
        "GBP",
        "Europe/London",
    )
    assert len(result["errors"]) == 3
    assert not result["rows"]


def test_aggregation_does_not_fill_before_coverage_or_subtract_returns():
    rows = [
        dict(day="2024-01-02", quantity=3, unit_price=2, cancellation=False),
        dict(day="2024-01-04", quantity=-1, unit_price=2, cancellation=True),
        dict(day="2024-01-05", quantity=7, unit_price=2, cancellation=False),
    ]
    series = daily_series(rows, date(2024, 1, 5), last_day_complete=False)
    assert series.index[0].date() == date(2024, 1, 2)
    assert series.to_list() == [3, 0, 0]


def test_invalid_utf8_and_missing_columns():
    with pytest.raises(UnicodeError):
        validate_csv(b"\xff", "sales", {}, "GBP", "Europe/London")
    with pytest.raises(ValueError, match="Missing columns"):
        validate_csv(b"sku\n0001\n", "sales", {}, "GBP", "Europe/London")


def test_coverage_starts_at_first_positive_sale_not_a_return():
    rows = [
        dict(day="2024-01-01", quantity=-2, unit_price=2, cancellation=True),
        dict(day="2024-01-03", quantity=3, unit_price=2, cancellation=False),
    ]
    series = daily_series(rows, date(2024, 1, 4))
    assert series.index[0].date() == date(2024, 1, 3)
    assert series.to_list() == [3, 0]


def test_nonpositive_prices_are_audited_and_excluded_from_demand():
    text = HEADER + "a,I,00012,Mug,2,-1,2024-01-01T12:00:00,UK\n"
    report = validate_csv(text.encode(), "sales", {}, "GBP", "Europe/London")
    assert not report["errors"]
    assert len(report["rows"]) == 1
    assert len(report["exclusions"]) == 1


def test_csv_extra_columns_and_excess_decimal_precision_are_blocking():
    text = (
        HEADER
        + "a,I,00012,Mug,2,1,2024-01-01T12:00:00,UK,extra\n"
        + "b,I,00012,Mug,2,1.00001,2024-01-01T12:00:00,UK\n"
    )
    report = validate_csv(text.encode(), "sales", {}, "GBP", "Europe/London")
    assert len(report["errors"]) == 2
