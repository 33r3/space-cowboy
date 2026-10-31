"""The ticker: the one thing that moves game time forward.

For each tick, in order:
  1. events due by this tick, oldest first (ships arriving: colony ships
     land, scouts arrive, freighters unload and set off on the next leg);
  2. the economy, one tick for every active colony.

Everything players see happened in that order, whoever looks first.
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from generation.colony_economics import apply_ticks
from generation.trade_routes import leg_transit_ticks

from .galaxy import Galaxy
from .models import Colony, Event, Notification, Planet, Route, Ship, Stockpile, World
from .units import fixed_map, float_map


# ── Colony rows <-> the economy's dicts ───────────────────────────────────────

def colony_dict(col: Colony) -> dict:
    return {
        'planetId': col.planet_id, 'size': col.size, 'developmentLevel': col.dev_level,
        'growthProgress': col.growth_progress, 'starvationTicks': col.starvation_ticks,
        'status': col.status, 'isHomeworld': col.is_homeworld,
        'stockpiles': float_map({s.resource: s.amount for s in col.stockpiles}),
    }


def stockpiles(col: Colony) -> dict[str, int]:
    return {s.resource: s.amount for s in col.stockpiles}


def planet_of(session: Session, galaxy: Galaxy, planet_id: str) -> dict | None:
    row = session.get(Planet, planet_id)
    return galaxy.planet(planet_id, row.overrides if row else None)


# ── Events ────────────────────────────────────────────────────────────────────

def _notify(session, player_id, tick, message, route_id=None):
    session.add(Notification(player_id=player_id, tick=tick, message=message,
                             route_id=route_id))


def _ship_arrives(session: Session, galaxy: Galaxy, ship: Ship, tick: int) -> None:
    if ship.kind == 'colony_ship':
        ship.status = 'arrived'
        col = session.get(Colony, ship.to_colony_id)
        if col.status == 'in_transit':
            col.status = 'active'
    elif ship.kind == 'scout':
        ship.status = 'arrived'
    elif ship.kind == 'freighter':
        _freighter_arrives(session, galaxy, ship, tick)


def _star_of(col: Colony) -> tuple[int, int, int]:
    return col.cx, col.cy, col.star_index


def _freighter_arrives(session: Session, galaxy: Galaxy, ship: Ship, tick: int) -> None:
    route = session.scalars(select(Route).where(Route.ship_id == ship.id)).one_or_none()
    if route is None:                       # route deleted while under way
        ship.status = 'arrived'
        return
    legs = route.legs
    dest = session.get(Colony, ship.to_colony_id)
    if dest is None or dest.status == 'abandoned':
        _stall(session, route, dest, tick)
        return

    # Unload everything aboard. The ship carries what was really loaded,
    # so a route can never deliver more than it took.
    have = stockpiles(dest)
    for res, amt in ship.cargo.items():
        have[res] = have.get(res, 0) + amt
    _set_fixed(dest, have)
    ship.cargo = {}

    nxt_idx = (route.current_leg + 1) % len(legs)
    nxt = legs[nxt_idx]
    route.current_leg = nxt_idx
    src = session.get(Colony, nxt.from_colony_id)
    if src is None or src.status == 'abandoned':
        _stall(session, route, src, tick)
        return

    # Load what the next leg orders, as far as the source has it. (When the
    # next leg starts somewhere else the ship jumps there, as it always has.)
    have = stockpiles(src)
    loaded = {}
    for res, want in nxt.cargo.items():
        take = min(want, have.get(res, 0))
        if take > 0:
            loaded[res] = take
            have[res] -= take
    _set_fixed(src, have)
    to = session.get(Colony, nxt.to_colony_id)
    dist = galaxy.distance(_star_of(src), _star_of(to))
    ship.from_colony_id, ship.to_colony_id = src.id, to.id
    ship.departed_tick = tick
    ship.arrival_tick = tick + leg_transit_ticks(dist, route.ship_class)
    ship.cargo = loaded
    session.add(Event(due_tick=ship.arrival_tick, kind='ship_arrives', ref_id=ship.id))


def _set_fixed(col: Colony, amounts: dict[str, int]) -> None:
    by_res = {s.resource: s for s in col.stockpiles}
    for res, amount in amounts.items():
        if res in by_res:
            by_res[res].amount = amount


def _stall(session, route: Route, col: Colony | None, tick: int) -> None:
    name = col.name if col else 'the destination'
    route.status = 'paused'
    _notify(session, route.owner_id, tick, f'Ship stalled — {name} has been abandoned.',
            route_id=route.id)


HANDLERS = {'ship_arrives': lambda s, g, e, t: _ship_arrives(s, g, s.get(Ship, e.ref_id), t)}


def run_events(session: Session, galaxy: Galaxy, tick: int) -> int:
    """Every unprocessed event due by `tick`, oldest first. Events added
    while running (a freighter's next leg) wait for their own tick."""
    events = session.scalars(
        select(Event).where(Event.processed_tick.is_(None), Event.due_tick <= tick)
        .order_by(Event.due_tick, Event.id)).all()
    for ev in events:
        HANDLERS[ev.kind](session, galaxy, ev, tick)
        ev.processed_tick = tick
    return len(events)


# ── Economy ───────────────────────────────────────────────────────────────────

def run_economy(session: Session, galaxy: Galaxy) -> None:
    """One tick of the economy for every active colony, read and written in
    bulk (the per-object ORM path cost ~0.3 ms a colony)."""
    session.flush()
    cols = session.execute(
        select(Colony.id, Colony.planet_id, Colony.size, Colony.dev_level,
               Colony.growth_progress, Colony.starvation_ticks, Colony.is_homeworld)
        .where(Colony.status == 'active')).all()
    if not cols:
        return
    stock: dict[int, dict[str, int]] = {}
    for cid, res, amt in session.execute(
            select(Stockpile.colony_id, Stockpile.resource, Stockpile.amount)
            .join(Colony).where(Colony.status == 'active')):
        stock.setdefault(cid, {})[res] = amt
    overrides = dict(session.execute(select(Planet.planet_id, Planet.overrides)).all())

    col_rows, stock_rows = [], []
    for cid, pid, size, dev, growth, starve, home in cols:
        yields = galaxy.yields(pid, overrides.get(pid))
        if yields is None:
            continue
        before = stock.get(cid, {})
        after = apply_ticks({'size': size, 'developmentLevel': dev, 'growthProgress': growth,
                             'starvationTicks': starve, 'status': 'active', 'isHomeworld': home,
                             'stockpiles': float_map(before)}, yields, 1)
        col_rows.append({'id': cid, 'size': after['size'], 'dev_level': after['developmentLevel'],
                         'growth_progress': after['growthProgress'],
                         'starvation_ticks': after['starvationTicks'], 'status': after['status']})
        for res, amt in fixed_map(after['stockpiles']).items():
            if before.get(res) != amt and res in before:
                stock_rows.append({'colony_id': cid, 'resource': res, 'amount': amt})
    session.execute(update(Colony), col_rows)
    if stock_rows:
        session.execute(update(Stockpile), stock_rows)
    session.expire_all()


# ── The clock ─────────────────────────────────────────────────────────────────

def advance(session: Session, galaxy: Galaxy, to_tick: int) -> int:
    """Run every tick from the world's last tick up to `to_tick`. Returns
    how many ticks ran. The caller commits."""
    world = session.get(World, 1)
    ran = 0
    while world.last_tick < to_tick:
        world.last_tick += 1
        run_events(session, galaxy, world.last_tick)
        run_economy(session, galaxy)
        session.flush()
        ran += 1
    return ran

