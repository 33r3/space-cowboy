"""The ticker: events in order, then the economy, one tick at a time."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app as app_module
from generation.colony_economics import ALL_RESOURCES, STARTER_STOCKPILES, apply_ticks
from server.galaxy import Galaxy
from server.models import (Base, Colony, Event, Notification, Player, Route, RouteLeg, Ship,
                           Stockpile, World)
from server.ticker import advance, colony_dict, planet_of
from server.units import fixed_map, to_float

T0 = 1000
GALAXY = Galaxy(app_module.config, app_module.density_field)
HOME = ('0,0:8:2', 0, 0, 8)
NEAR = ('0,-1:1:2', 0, -1, 1)         # 181 Ly away


@pytest.fixture
def s():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(World(id=1, last_tick=T0))
        session.add(Player(id=1, name='P1', created_tick=T0))
        session.flush()
        yield session


def colony(s, where, status='active', size=1, dev=1, stock=None, **kw):
    pid, cx, cy, star = where
    amounts = {r: 0.0 for r in ALL_RESOURCES} | (stock or {})
    col = Colony(owner_id=1, planet_id=pid, name=pid, cx=cx, cy=cy, star_index=star,
                 founded_tick=T0, status=status, size=size, dev_level=dev,
                 growth_progress=0, starvation_ticks=0, is_homeworld=False,
                 stockpiles=[Stockpile(resource=r, amount=v)
                             for r, v in fixed_map(amounts).items()], **kw)
    s.add(col)
    s.flush()
    return col


def food(col):
    return next(to_float(x.amount) for x in col.stockpiles if x.resource == 'food')


def ship(s, kind, arrival, **kw):
    sh = Ship(uid=f'{kind}-{arrival}-{len(kw)}', owner_id=1, kind=kind, status='in_transit',
              departed_tick=T0, arrival_tick=arrival, cargo={}, **kw)
    s.add(sh)
    s.flush()
    s.add(Event(due_tick=arrival, kind='ship_arrives', ref_id=sh.id))
    s.flush()
    return sh


def test_economy_matches_the_old_rules_tick_for_tick(s):
    col = colony(s, HOME, size=3, dev=3, stock={'food': 100, 'water': 100, 'minerals': 200,
                                                'metals': 150, 'organicFuels': 100})
    before = colony_dict(col)
    yields = planet_of(s, GALAXY, col.planet_id)['colonyYields']
    assert advance(s, GALAXY, T0 + 7) == 7
    expected = apply_ticks(before, yields, 7)
    got = colony_dict(col)
    assert got['stockpiles'] == pytest.approx(expected['stockpiles'], abs=0.001)
    assert (got['size'], got['growthProgress']) == (expected['size'], expected['growthProgress'])
    assert advance(s, GALAXY, T0 + 7) == 0


def test_arrived_colony_produces_from_its_arrival_tick(s):
    col = colony(s, NEAR, status='in_transit', stock=STARTER_STOCKPILES)
    ship(s, 'colony_ship', T0 + 4, to_colony_id=col.id)
    advance(s, GALAXY, T0 + 3)
    assert col.status == 'in_transit' and food(col) == 10.0
    advance(s, GALAXY, T0 + 24)
    assert col.status == 'active'
    yields = planet_of(s, GALAXY, col.planet_id)['colonyYields']
    expected = apply_ticks({**colony_dict(colony(s, ('x:0:0', 0, 0, 0), stock=STARTER_STOCKPILES)),
                            'planetId': col.planet_id}, yields, 21)
    assert colony_dict(col)['stockpiles'] == pytest.approx(expected['stockpiles'], abs=0.001)


def route(s, a, b, out=None, back=None, status='active'):
    r = Route(id='r1', owner_id=1, name='Run', ship_class='freighter_mk1', status=status,
              current_leg=0, legs=[RouteLeg(idx=0, from_colony_id=a.id, to_colony_id=b.id,
                                            cargo=fixed_map(out or {})),
                                   RouteLeg(idx=1, from_colony_id=b.id, to_colony_id=a.id,
                                            cargo=fixed_map(back or {}))])
    s.add(r)
    sh = ship(s, 'freighter', T0 + 2, from_colony_id=a.id, to_colony_id=b.id)
    sh.cargo = fixed_map(out or {})
    r.ship_id = sh.id
    s.flush()
    return r, sh


@pytest.fixture
def no_economy(monkeypatch):
    import server.ticker as tk
    monkeypatch.setattr(tk, 'run_economy', lambda *a: None)


def test_freighters_only_deliver_what_they_loaded(s, no_economy):
    """The old engine shipped the full order even when the source was short."""
    home = colony(s, HOME, stock={'food': 50})
    near = colony(s, NEAR, stock={'food': 10})
    r, sh = route(s, home, near, out={'food': 5}, back={'food': 20})
    total = lambda: food(home) + food(near) + to_float(sh.cargo.get('food', 0))
    assert total() == 65
    advance(s, GALAXY, T0 + 2)                 # unload 5 at near, load what it has
    assert r.current_leg == 1 and sh.arrival_tick == T0 + 4
    assert sh.cargo == {'food': 15000} and food(near) == 0
    for t in range(3, 13):
        advance(s, GALAXY, T0 + t)
        assert total() == 65, t


def test_events_run_oldest_first(s):
    seen = []
    import server.ticker as tk
    orig = tk.HANDLERS['ship_arrives']
    tk.HANDLERS['ship_arrives'] = lambda s_, g, e, t: seen.append((e.due_tick, e.id))
    try:
        s.add_all([Event(due_tick=T0 + 3, kind='ship_arrives', ref_id=0),
                   Event(due_tick=T0 + 1, kind='ship_arrives', ref_id=0),
                   Event(due_tick=T0 + 3, kind='ship_arrives', ref_id=0),
                   Event(due_tick=T0 - 5, kind='ship_arrives', ref_id=0)])   # overdue
        s.flush()
        advance(s, GALAXY, T0 + 5)
    finally:
        tk.HANDLERS['ship_arrives'] = orig
    assert [d for d, _ in seen] == [T0 - 5, T0 + 1, T0 + 3, T0 + 3]
    assert seen[2][1] < seen[3][1]
    assert all(e.processed_tick for e in s.scalars(select(Event)))


def test_route_to_an_abandoned_colony_stalls_and_says_so(s):
    home = colony(s, HOME, stock={'food': 50, 'water': 50})
    near = colony(s, NEAR, status='abandoned')
    r, sh = route(s, home, near, out={'food': 5})
    advance(s, GALAXY, T0 + 2)
    assert r.status == 'paused' and r.current_leg == 0 and sh.cargo == {'food': 5000}
    [n] = s.scalars(select(Notification)).all()
    assert 'abandoned' in n.message and n.route_id == 'r1'


def test_scouts_arrive(s):
    sc = ship(s, 'scout', T0 + 4, to_star_id='0,-1:1')
    advance(s, GALAXY, T0 + 4)
    assert sc.status == 'arrived'
