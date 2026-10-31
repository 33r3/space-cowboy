"""The ticker: the one thing that moves game time forward.

For each tick, in order:
  1. events due by this tick, oldest first (ships arriving: colony ships
     land, scouts arrive, freighters unload and set off on the next leg);
  2. terraforming projects, oldest first, each paid by its colony;
  3. the economy, one tick for every active colony, on the planets as
     terraforming just left them.

Everything players see happened in that order, whoever looks first.
"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from generation import terraform as tf
from generation.colony_economics import apply_ticks
from generation.trade_routes import leg_transit_ticks

from .galaxy import Galaxy, split_star_id
from .models import (Colony, Event, Notification, Planet, Route, Ship, Stockpile,
                     TerraformProject, World)
from .units import fixed_map, float_map, to_fixed


# ── Colony rows <-> the economy's dicts ───────────────────────────────────────

def colony_dict(col: Colony) -> dict:
    return {
        'planetId': col.planet_id, 'size': col.size, 'developmentLevel': col.dev_level,
        'growthProgress': col.growth_progress, 'starvationTicks': col.starvation_ticks,
        'status': col.status, 'isHomeworld': col.is_homeworld,
        'overCapTicks': col.over_cap_ticks,
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
        from .vision import survey_around
        new = survey_around(session, galaxy, ship.owner_id, ship.to_star_id, tick)
        star = galaxy.star(*split_star_id(ship.to_star_id))
        _notify(session, ship.owner_id, tick,
                f'Probe arrived at {star["name"] if star else ship.to_star_id}: '
                f'{len(new)} system{"s" if len(new) != 1 else ""} surveyed.')
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


# ── Terraforming ──────────────────────────────────────────────────────────────

def _fmt_cost(cost: dict) -> str:
    return ', '.join(f'{v:g} {k}' for k, v in cost.items())


def run_terraforming(session: Session, galaxy: Galaxy, tick: int) -> None:
    """Each live project, oldest first: pay this tick's cost from its
    colony, then move its planet's offset one step toward the target.
    Opposing projects on one planet both pay and pull; the net is what
    moves."""
    projects = session.scalars(select(TerraformProject)
                               .where(TerraformProject.status.in_(('active', 'stalled')))
                               .order_by(TerraformProject.id)).all()
    for pr in projects:
        lever = tf.LEVERS[pr.lever]
        payer = session.get(Colony, pr.colony_id)
        planet = session.get(Planet, pr.planet_id)
        if planet is None:
            planet = Planet(planet_id=pr.planet_id, overrides={}, updated_tick=tick)
            session.add(planet)
        deltas = dict(planet.overrides.get('terraforming', {}))
        current = deltas.get(lever['key'], 0.0)
        where = payer.name if payer else 'its colony'
        base = galaxy.planet(pr.planet_id)
        name = base['name'] if base else pr.planet_id
        need = tf.MIN_DEV_LOCAL if payer and payer.planet_id == pr.planet_id else tf.MIN_DEV_REMOTE
        if payer is None or payer.status != 'active' or payer.dev_level < need:
            _end(session, pr, tick, 'stopped',
                 f'Terraforming {name} stopped: {where} can no longer run it.')
            continue
        if current == pr.target:
            _end(session, pr, tick, 'done', f'Terraforming {name} done: {pr.lever} reached its target.')
            continue
        cost = tf.lever_cost(pr.lever, 1 if pr.target > current else -1)
        have = stockpiles(payer)
        if any(have.get(k, 0) < to_fixed(v) for k, v in cost.items()):
            if pr.status != 'stalled':
                pr.status = 'stalled'
                _notify(session, pr.owner_id, tick,
                        f'Terraforming {name} stalled: {where} can\'t pay {_fmt_cost(cost)} a tick.')
            continue
        pr.status = 'active'
        for k, v in cost.items():
            have[k] -= to_fixed(v)
        _set_fixed(payer, have)
        deltas[lever['key']] = tf.step_toward(current, pr.target, tf.lever_rate(pr.lever, payer.dev_level))
        planet.overrides = {**planet.overrides, 'terraforming': deltas}     # new dict: JSON change
        planet.updated_tick = tick
        if deltas[lever['key']] == pr.target:
            _end(session, pr, tick, 'done', f'Terraforming {name} done: {pr.lever} reached its target.')


def _end(session, pr, tick, status, message):
    pr.status, pr.ended_tick = status, tick
    _notify(session, pr.owner_id, tick, message)


# ── Economy ───────────────────────────────────────────────────────────────────

def run_economy(session: Session, galaxy: Galaxy) -> None:
    """One tick of the economy for every active colony, read and written in
    bulk (the per-object ORM path cost ~0.3 ms a colony)."""
    session.flush()
    cols = session.execute(
        select(Colony.id, Colony.planet_id, Colony.size, Colony.dev_level,
               Colony.growth_progress, Colony.starvation_ticks, Colony.is_homeworld,
               Colony.over_cap_ticks)
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
    for cid, pid, size, dev, growth, starve, home, over_cap in cols:
        state = galaxy.state(pid, overrides.get(pid))
        if state is None:
            continue
        yields, hab = state
        before = stock.get(cid, {})
        after = apply_ticks({'size': size, 'developmentLevel': dev, 'growthProgress': growth,
                             'starvationTicks': starve, 'status': 'active', 'isHomeworld': home,
                             'overCapTicks': over_cap, 'habitability': hab,
                             'stockpiles': float_map(before)}, yields, 1)
        col_rows.append({'id': cid, 'size': after['size'], 'dev_level': after['developmentLevel'],
                         'growth_progress': after['growthProgress'],
                         'starvation_ticks': after['starvationTicks'], 'status': after['status'],
                         'over_cap_ticks': after['overCapTicks']})
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
        run_terraforming(session, galaxy, world.last_tick)
        run_economy(session, galaxy)
        session.flush()
        ran += 1
    return ran

