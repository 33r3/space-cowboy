import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import time_machine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app as app_module  # noqa: E402

START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
HOMEWORLD = '0,0:8:2'          # Zeum III, the seed-42 homeworld
NEAR = {'cx': 0, 'cy': -1, 'starIndex': 1, 'planetIndex': 2}   # Kainai III, 181 Ly
NEAR_ID = '0,-1:1:2'


class Clock:
    """Frozen game clock; advance(minutes=n) moves it on n ticks."""
    def __init__(self, traveller):
        self._t = traveller

    def advance(self, **kw):
        self._t.shift(timedelta(**kw))


@pytest.fixture
def clock():
    with time_machine.travel(START, tick=False) as t:
        yield Clock(t)


@pytest.fixture
def flask_client(tmp_path, monkeypatch, clock):
    """The old Flask app with its save files in a temp dir and the clock frozen."""
    monkeypatch.setattr(app_module, '_COLONIES_FILE', str(tmp_path / 'colonies.json'))
    monkeypatch.setattr(app_module, '_ROUTES_FILE', str(tmp_path / 'routes.json'))
    monkeypatch.setattr(app_module, '_SCOUTS_FILE', str(tmp_path / 'scouts.json'))
    c = app_module.app.test_client()
    assert c.get('/api/homeworld').status_code == 200
    return c


class _Response:
    """httpx responses with Flask's get_json(), so one test body fits both."""
    def __init__(self, r):
        self._r = r
        self.status_code = r.status_code

    def get_json(self):
        return self._r.json()


class _Client:
    def __init__(self, tc):
        self._tc = tc

    def as_player(self, player_id: int) -> None:
        from server.app import current_player_id
        self.api.dependency_overrides[current_player_id] = lambda: player_id

    def __getattr__(self, verb):
        return lambda *a, **kw: _Response(getattr(self._tc, verb)(*a, **kw))


@pytest.fixture
def fastapi_client(tmp_path, clock):
    """The FastAPI server on a fresh SQLite database, ticker off (each
    request catches the world up itself)."""
    from fastapi.testclient import TestClient
    from server.app import Game, create_app
    from server.db import make_engine, make_sessionmaker
    from server.models import Base
    engine = make_engine(f'sqlite:///{tmp_path}/test.db')
    Base.metadata.create_all(engine)
    api = create_app(Game(make_sessionmaker(engine)), run_ticker=False)
    with TestClient(api) as tc:
        c = _Client(tc)
        c.api = api
        assert c.get('/api/homeworld').status_code == 200
        yield c


@pytest.fixture(params=['flask', 'fastapi'])
def client(request):
    """Both servers: the API tests must pass on each."""
    return request.getfixturevalue(f'{request.param}_client')


def colonies(client) -> dict:
    return {c['planetId']: c for c in client.get('/api/colonies').get_json()['colonies']}


@pytest.fixture
def flask_bug(request):
    """flask_bug('why'): this test is expected to fail on the old Flask
    server only (a known bug the database version fixes)."""
    def mark(reason):
        if request.node.callspec.params.get('client') == 'flask':
            request.applymarker(pytest.mark.xfail(strict=True, reason='BUG: ' + reason))
    return mark
