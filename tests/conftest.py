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
def client(tmp_path, monkeypatch, clock):
    """The Flask app with its save files in a temp dir and the clock frozen."""
    monkeypatch.setattr(app_module, '_COLONIES_FILE', str(tmp_path / 'colonies.json'))
    monkeypatch.setattr(app_module, '_ROUTES_FILE', str(tmp_path / 'routes.json'))
    monkeypatch.setattr(app_module, '_SCOUTS_FILE', str(tmp_path / 'scouts.json'))
    c = app_module.app.test_client()
    assert c.get('/api/homeworld').status_code == 200
    return c


def colonies(client) -> dict:
    return {c['planetId']: c for c in client.get('/api/colonies').get_json()['colonies']}
