"""Ticks and fixed-point resource amounts."""
from datetime import datetime, timezone

from generation.colony_economics import TICK_SECONDS

EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)
SCALE = 1000            # stored amounts are thousandths


def tick_of(dt: datetime) -> int:
    return int((dt - EPOCH).total_seconds() // TICK_SECONDS)


def now_tick() -> int:
    return tick_of(datetime.now(tz=timezone.utc))


def time_of(tick: int) -> datetime:
    from datetime import timedelta
    return EPOCH + timedelta(seconds=tick * TICK_SECONDS)


def to_fixed(x: float) -> int:
    return round(x * SCALE)


def to_float(n: int) -> float:
    return n / SCALE


def fixed_map(d: dict) -> dict:
    return {k: to_fixed(v) for k, v in d.items()}


def float_map(d: dict) -> dict:
    return {k: to_float(v) for k, v in d.items()}
