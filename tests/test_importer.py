"""Old JSON saves import into the database as player 1."""
import json
import pathlib

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from conftest import HOMEWORLD
from generation.config import DEFAULT_CONFIG
from generation.density_field import DensityField
from generation.homeworld import find_homeworld
from server.importer import import_saves
from server.models import Base, Colony, Event, Planet, Route, Ship
from server.units import now_tick, to_float

DATA = pathlib.Path(__file__).parent / 'data' / 'old_save'
DENSITY = DensityField(DEFAULT_CONFIG)


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def load(name):
    return json.load(open(DATA / f'{name}.json'))


def test_import_round_trip(clock, session):
    """A save the old Flask app wrote (homeworld, a landed colony, a route
    and a scout under way, a colony ship still flying) imports to what
    Flask itself showed for it at that moment."""
    expected = load('expected_colonies')
    clock.advance(minutes=expected['now_minutes_after_start'])
    import_saves(session, load('colonies'), load('routes'), load('scouts'), DEFAULT_CONFIG,
                 DENSITY, homeworld=find_homeworld(DEFAULT_CONFIG, DENSITY))
    rows = {c.planet_id: c for c in session.scalars(select(Colony))}
    assert set(rows) == set(expected['colonies'])
    for pid, col in expected['colonies'].items():
        row = rows[pid]
        assert (row.status, row.size, row.dev_level, row.is_homeworld) == \
            (col['status'], col['size'], col['developmentLevel'], col['isHomeworld'])
        got = {s.resource: to_float(s.amount) for s in row.stockpiles}
        assert got == pytest.approx(col['stockpiles'], abs=0.001), pid

    ships = {s.kind: s for s in session.scalars(select(Ship))}
    assert set(ships) == {'colony_ship', 'freighter', 'scout'}
    assert ships['freighter'].cargo == {'food': 5000}
    assert ships['scout'].arrival_tick == ships['scout'].departed_tick + 4
    events = session.scalars(select(Event)).all()
    assert len(events) == 3 and all(e.due_tick > now_tick() - 1 for e in events)
    route = session.scalars(select(Route)).one()
    assert [l.idx for l in route.legs] == [0, 1] and route.ship_id == ships['freighter'].id
    hw = session.get(Planet, HOMEWORLD)
    assert hw.overrides['yieldFloor']['metals'] >= 0.15


def test_import_of_an_empty_save(session, clock):
    p = import_saves(session, {'colonies': []}, {'routes': []}, [], None, None)
    assert p.id == 1 and session.scalars(select(Colony)).all() == []
