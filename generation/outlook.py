"""
Outlook — where each colony, and the whole civilization, is heading at
today's rates. Pure functions, no I/O.

A resource's state, from its net flow per tick and its stock:
  ok        growing comfortably
  tight     still growing, but by less than TIGHT_SHARE of what is used
            (one bad turn, or one more colony, and it falls)
  falling   shrinking; runway = ticks until the stock is gone
  critical  shrinking and gone within CRITICAL_TICKS
Only resources something uses can be tight, falling or critical.
"""
import math

from .colony_economics import ALL_RESOURCES, consumption_per_tick, net_flow_per_tick

TIGHT_SHARE = 0.10
CRITICAL_TICKS = 60          # an hour
ORDER = {'ok': 0, 'tight': 1, 'falling': 2, 'critical': 3}


def state(net: float, used: float, stock: float) -> tuple[str, float | None]:
    """(state, runway in ticks or None when not shrinking)."""
    if net < 0:
        runway = stock / -net
        return ('critical' if runway < CRITICAL_TICKS else 'falling'), runway
    if used > 0 and net < used * TIGHT_SHARE:
        return 'tight', None
    return 'ok', None


def resource_rows(stock: dict, made: dict, used: dict, incoming: dict | None = None) -> list[dict]:
    incoming = incoming or {}
    rows = []
    for r in ALL_RESOURCES:
        m, u = made.get(r, 0.0), used.get(r, 0.0)
        net = round(m - u, 3)
        have = stock.get(r, 0.0) + incoming.get(r, 0.0)
        st, runway = state(net, u, have)
        rows.append({'resource': r, 'stock': round(stock.get(r, 0.0), 3),
                     'incoming': round(incoming.get(r, 0.0), 3),
                     'made': round(m, 3), 'used': round(u, 3), 'net': net, 'state': st,
                     'runwayTicks': None if runway is None else round(runway, 1)})
    return rows


def worst(rows: list[dict]) -> dict | None:
    """The row most in trouble (shortest runway first), or None if all ok."""
    bad = [r for r in rows if r['state'] != 'ok']
    if not bad:
        return None
    return max(bad, key=lambda r: (ORDER[r['state']], -(r['runwayTicks'] or math.inf)))


def outpost(yields: dict, habitability: int) -> dict[str, float]:
    """Net flow per tick of a brand-new outpost on a planet."""
    d = {'size': 1, 'developmentLevel': 1, 'habitability': habitability}
    return net_flow_per_tick(d, yields)


def outpost_use(habitability: int = 100) -> dict[str, float]:
    d = {'size': 1, 'developmentLevel': 1, 'habitability': habitability}
    return {k: v for k, v in consumption_per_tick(d).items() if v > 0}


def room_for_outposts(civ_rows: list[dict]) -> dict[str, int]:
    """How many more outposts that produce nothing the civilization's
    surplus could feed, per resource an outpost eats."""
    by = {r['resource']: r for r in civ_rows}
    return {k: max(0, math.floor(by[k]['net'] / v)) for k, v in outpost_use().items()}
