from datetime import date

import pandas as pd


def daily_series(rows: list[dict], cutoff: date, last_day_complete: bool = True) -> pd.Series:
    """Never fill before the first positive sale; always return a dated index."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.Series(index=pd.DatetimeIndex([]), dtype=float)
    frame["day"] = pd.to_datetime(frame["day"])
    frame = frame[frame.day <= pd.Timestamp(cutoff)]
    if not last_day_complete:
        frame = frame[frame.day < pd.Timestamp(cutoff)]
        cutoff = (pd.Timestamp(cutoff) - pd.Timedelta(days=1)).date()
    if frame.empty:
        return pd.Series(index=pd.DatetimeIndex([]), dtype=float)
    positive = frame[(frame.quantity > 0) & (frame.unit_price > 0) & (~frame.cancellation)]
    if positive.empty:
        return pd.Series(index=pd.DatetimeIndex([]), dtype=float)
    first = positive.day.min()
    return (
        positive.groupby("day")
        .quantity.sum()
        .reindex(pd.date_range(first, cutoff), fill_value=0)
        .astype(float)
    )
