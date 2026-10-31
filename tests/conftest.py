import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import time_machine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
HOMEWORLD = '0,0:8:2'          # Zeum III, the seed-42 homeworld
NEAR = {'cx': 0, 'cy': -1, 'starIndex': 1, 'planetIndex': 2}   # Kainai III, 181 Ly
NEAR_ID = '0,-1:1:2'
NEAR_STAR = '0,-1:1'             # beyond the homeworld's sensors: needs a survey


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


class _Response:
    """httpx responses with a Flask-style get_json() (the tests were written
    against the old Flask app)."""
    def __init__(self, r):
        self._r = r
        self.status_code = r.status_code

    def get_json(self):
        return self._r.json()


class _Client:
    def __init__(self, tc):
        self._tc = tc
        self.player_id = 1

    def as_player(self, player_id: int) -> None:
        from server.app import current_player_id
        self.player_id = player_id
        self.api.dependency_overrides[current_player_id] = lambda: player_id

    def survey(self, star_id: str) -> None:
        from server.models import Player, Survey
        with self.api.state.game.sessionmaker() as s:
            if s.get(Player, self.player_id) is None:
                s.add(Player(id=self.player_id, name=f'Player {self.player_id}', created_tick=0))
                s.flush()
            s.merge(Survey(player_id=self.player_id, star_id=star_id, surveyed_tick=0))
            s.commit()

    def __getattr__(self, verb):
        return lambda *a, **kw: _Response(getattr(self._tc, verb)(*a, **kw))


@pytest.fixture
def fastapi_client(tmp_path, clock):
    """The server on a fresh SQLite database, ticker off (each request
    catches the world up itself). c.as_player(n) acts as player n;
    c.survey(star_id) lets the current player know a system."""
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


@pytest.fixture
def client(fastapi_client):
    return fastapi_client


def colonies(client) -> dict:
    return {c['planetId']: c for c in client.get('/api/colonies').get_json()['colonies']}

