"""Free traders on the database (generation/market.py has the rules).

A trader is a Ship of kind 'trader'. Idle, it waits at the colony in
to_colony_id. Each tick, after the economy, every idle trader takes the
best job its owner's markets offer (run_traders); its arrivals come
through the event queue like every other ship (trader_arrives):

    pickup   flew empty to a colony with surplus: load what it still can
             spare (up to what was planned) and fly on to the buyer
    deliver  unload everything at the buyer, go idle there

Traders only work between their owner's own colonies, and a colony's
market counts what traders already on their way will take and bring, so
two traders don't chase the same shortfall.
"""
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from generation import market as mk
from generation.trade_routes import SHIP_CLASSES

from .galaxy import Galaxy
from .models import Colony, Event, MarketSetting, Notification, Ship
from .units import float_map, to_fixed, to_float


def settings_of(session: Session, colony_ids) -> dict[int, dict[str, dict]]:
    """{colony id: {resource: {'keep': units | None, 'export', 'import'}}}."""
    out: dict[int, dict] = defaultdict(dict)
    rows = session.scalars(select(MarketSetting).where(MarketSetting.colony_id.in_(list(colony_ids))))
    for m in rows:
        out[m.colony_id][m.resource] = {'keep': None if m.keep is None else to_float(m.keep),
                                        'export': m.export, 'import': m.import_}
    return out


def colony_market(galaxy: Galaxy, col: Colony, overrides: dict | None, stock: dict[str, int],
                  settings: dict | None) -> mk.Market:
    """col's market with `stock` (thousandths) on hand."""
    from .ticker import colony_dict
    d = colony_dict(col)
    state = galaxy.state(col.planet_id, overrides)
    if state is not None:
        d['habitability'] = state[1]
    return mk.make_market(d, float_map(stock), settings, col.save_for_upgrade)


class OwnerMarkets:
    """One owner's active colonies as traders see them this tick."""

    def __init__(self, session: Session, galaxy: Galaxy, owner_id: int):
        from .models import Planet
        from .ticker import stockpiles
        self.session, self.galaxy = session, galaxy
        cols = session.scalars(select(Colony).where(Colony.owner_id == owner_id,
                                                    Colony.status == 'active')).all()
        settings = settings_of(session, [c.id for c in cols])
        on_way = self._on_the_way(owner_id)
        self.markets: dict[int, mk.Market] = {}
        for c in cols:
            row = session.get(Planet, c.planet_id)
            stock = stockpiles(c)
            for r, amt in on_way.get(c.id, {}).items():
                stock[r] = stock.get(r, 0) + amt
            self.markets[c.id] = colony_market(galaxy, c, row.overrides if row else None,
                                               stock, settings.get(c.id))
        self._pos: dict[int, tuple[float, float] | None] = {}
        self._dist: dict[tuple[int, int], float] = {}

    def _on_the_way(self, owner_id: int) -> dict[int, dict[str, int]]:
        """Per colony, what traders under way will add (deliveries) or take
        (pickups not yet made)."""
        out: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        ships = self.session.scalars(select(Ship).where(
            Ship.owner_id == owner_id, Ship.kind == 'trader', Ship.status == 'in_transit')).all()
        for sh in ships:
            t = sh.trade or {}
            if t.get('phase') == 'deliver':
                for r, amt in sh.cargo.items():
                    out[sh.to_colony_id][r] += amt
            elif t.get('phase') == 'pickup':
                for r, amt in t.get('want', {}).items():
                    out[sh.to_colony_id][r] -= amt
                    out[t['then']][r] += amt
        return out

    def pos(self, colony_id: int) -> tuple[float, float] | None:
        if colony_id not in self._pos:
            c = self.session.get(Colony, colony_id)
            self._pos[colony_id] = self.galaxy.star_pos(c.cx, c.cy, c.star_index) if c else None
        return self._pos[colony_id]

    def dist(self, a: int, b: int) -> float:
        if a == b:
            return 0.0
        key = (a, b) if a < b else (b, a)
        d = self._dist.get(key)
        if d is None:
            pa, pb = self.pos(a), self.pos(b)
            d = float('inf') if pa is None or pb is None else \
                ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5
            self._dist[key] = d
        return d


def _depart(session: Session, ship: Ship, src_id: int, dst_id: int, ticks: int, tick: int,
            cargo: dict[str, int], **trade) -> None:
    ship.status = 'in_transit'
    ship.from_colony_id, ship.to_colony_id = src_id, dst_id
    ship.departed_tick, ship.arrival_tick = tick, tick + ticks
    ship.cargo = cargo
    keep = {k: v for k, v in (ship.trade or {}).items() if k in ('retire', 'trips', 'value', 'last')}
    ship.trade = {**keep, **trade}                  # new dict: JSON change
    session.add(Event(due_tick=ship.arrival_tick, kind='ship_arrives', ref_id=ship.id))


def _load(col: Colony, want: dict[str, float], spare: mk.Market | None = None) -> dict[str, int]:
    """Take up to `want` (units) out of col's stockpiles, and, given its
    market, no more than its surplus. Returns what was loaded (thousandths)."""
    loaded = {}
    for st in col.stockpiles:
        if st.resource not in want:
            continue
        most = to_fixed(want[st.resource])
        if spare is not None:
            most = min(most, to_fixed(spare.surplus(st.resource)))
        take = max(0, min(most, st.amount))
        if take > 0:
            st.amount -= take
            loaded[st.resource] = take
    return loaded


def _transit(ship: Ship, distance: float) -> int:
    return mk.transit_ticks(distance, SHIP_CLASSES[ship.ship_class]['speedLyPerTick'])


def run_traders(session: Session, galaxy: Galaxy, tick: int) -> int:
    """Every idle trader, oldest first per owner, takes its best job.
    Returns how many set off."""
    idle = session.scalars(select(Ship).where(Ship.kind == 'trader', Ship.status == 'idle')
                           .order_by(Ship.owner_id, Ship.id)).all()
    by_owner: dict[int, list[Ship]] = defaultdict(list)
    for sh in idle:
        by_owner[sh.owner_id].append(sh)
    sent = 0
    for owner_id, ships in by_owner.items():
        view = OwnerMarkets(session, galaxy, owner_id)
        if not any(m.buys() for m in view.markets.values()):
            continue
        for sh in ships:
            sc = SHIP_CLASSES[sh.ship_class]
            job = mk.best_job(sh.to_colony_id, sc['capacity'], sc['maxRangeLy'],
                              lambda d, sc=sc: mk.transit_ticks(d, sc['speedLyPerTick']),
                              view.markets, view.dist)
            if job is None:
                continue
            mk.reserve(job, view.markets)
            if job.source == sh.to_colony_id:
                loaded = _load(session.get(Colony, job.source), job.cargo)
                _depart(session, sh, job.source, job.dest, job.ticks, tick, loaded,
                        phase='deliver', planned=round(job.value, 2))
            else:
                _depart(session, sh, sh.to_colony_id, job.source,
                        _transit(sh, view.dist(sh.to_colony_id, job.source)), tick, {},
                        phase='pickup', want=job.cargo, then=job.dest,
                        planned=round(job.value, 2))
            sent += 1
    return sent


def _idle_at(ship: Ship, colony_id: int, **trade) -> None:
    ship.status, ship.to_colony_id, ship.cargo = 'idle', colony_id, {}
    keep = {k: v for k, v in (ship.trade or {}).items() if k in ('retire', 'trips', 'value', 'last')}
    ship.trade = {**keep, **trade}


def trader_arrives(session: Session, galaxy: Galaxy, ship: Ship, tick: int) -> None:
    from .models import Planet
    t = dict(ship.trade or {})
    here = session.get(Colony, ship.to_colony_id)
    alive = here is not None and here.status == 'active'

    if t.get('phase') == 'pickup':
        dest = session.get(Colony, t.get('then'))
        if not alive or dest is None or dest.status != 'active':
            _idle_at(ship, ship.to_colony_id)
            return
        from .ticker import stockpiles
        row = session.get(Planet, here.planet_id)
        spare = colony_market(galaxy, here, row.overrides if row else None, stockpiles(here),
                              settings_of(session, [here.id]).get(here.id))
        loaded = _load(here, t.get('want', {}), spare)
        if not loaded:                               # someone else got there first
            _idle_at(ship, here.id)
            return
        view_dist = galaxy.distance((here.cx, here.cy, here.star_index),
                                    (dest.cx, dest.cy, dest.star_index))
        _depart(session, ship, here.id, dest.id, _transit(ship, view_dist), tick, loaded,
                phase='deliver', planned=t.get('planned', 0.0))
        return

    # deliver
    if not alive:
        back = session.get(Colony, ship.from_colony_id)
        if back is not None and back.status == 'active' and back.id != ship.to_colony_id \
                and not t.get('returning'):
            d = galaxy.distance((here.cx, here.cy, here.star_index),
                                (back.cx, back.cy, back.star_index)) if here else 0.0
            _depart(session, ship, ship.to_colony_id, back.id, _transit(ship, d), tick,
                    dict(ship.cargo), phase='deliver', planned=0.0, returning=True)
            return
        if ship.cargo:
            session.add(Notification(player_id=ship.owner_id, tick=tick, message=(
                f'A free trader lost its cargo: {here.name if here else "its buyer"} '
                f'is abandoned and it had nowhere to take it.')))
        _idle_at(ship, ship.to_colony_id)
        return
    by_res = {st.resource: st for st in here.stockpiles}
    for r, amt in ship.cargo.items():
        if r in by_res:
            by_res[r].amount += amt
    src = session.get(Colony, ship.from_colony_id)
    last = {'tick': tick, 'from': src.name if src else '?', 'to': here.name,
            'cargo': float_map(ship.cargo)}
    if t.get('retire'):
        session.delete(ship)
        return
    ship.trade = {**t, 'trips': t.get('trips', 0) + (1 if ship.cargo else 0),
                  'value': round(t.get('value', 0.0) + t.get('planned', 0.0), 2), 'last': last}
    _idle_at(ship, here.id)
