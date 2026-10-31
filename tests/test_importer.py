"""Old JSON saves import into the database as player 1."""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app as app_module
from conftest import HOMEWORLD, NEAR_ID, colonies
from server.importer import import_saves
from server.models import Base, Colony, Event, Planet, Route, Ship
from server.units import now_tick, to_float


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def build_save(client, clock):
    """Homeworld, a colony that has landed, a route and a scout in flight,
    and a second colony ship still on its way."""
    client.post('/api/colonies', json={'cx': 0, 'cy': -1, 'starIndex': 1, 'planetIndex': 2})
    clock.advance(minutes=60)
    colonies(client)
    client.post('/api/routes', json={'name': 'Run', 'shipClass': 'freighter_mk1', 'legs': [
        {'fromPlanetId': HOMEWORLD, 'toPlanetId': NEAR_ID, 'cargo': {'food': 5}},
        {'fromPlanetId': NEAR_ID, 'toPlanetId': HOMEWORLD, 'cargo': {}}]})
    client.post('/api/scouts', json={'sourcePlanetId': HOMEWORLD, 'destStarCx': 0,
                                     'destStarCy': -1, 'destStarIndex': 1})
    client.post('/api/colonies', json={'cx': 1, 'cy': 1, 'starIndex': 28, 'planetIndex': 2})
    read = lambda p: json.load(open(p))
    return (read(app_module._COLONIES_FILE), read(app_module._ROUTES_FILE),
            read(app_module._SCOUTS_FILE))


def test_import_round_trip(flask_client, clock, session):
    client = flask_client
    cols_json, routes_json, scouts_json = build_save(client, clock)
    clock.advance(minutes=1)                       # the import catches colonies up
    expected = colonies(client)
    import_saves(session, cols_json, routes_json, scouts_json,
                 app_module.config, app_module.density_field,
                 homeworld=app_module.find_homeworld(app_module.config, app_module.density_field))
    rows = {c.planet_id: c for c in session.scalars(select(Colony))}
    assert set(rows) == set(expected)
    for pid, col in expected.items():
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
    assert hw.overrides['colonyYields']['metals'] >= 0.15


def test_import_of_an_empty_save(session, clock):
    p = import_saves(session, {'colonies': []}, {'routes': []}, [], None, None)
    assert p.id == 1 and session.scalars(select(Colony)).all() == []
