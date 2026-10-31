"""Stars are public; a system's planets only once you know it (proximity
and development level, or a probe's survey). The server enforces it."""
import math

from conftest import NEAR, NEAR_STAR
from generation.chunk_generator import chunks_in_bounds, generate_chunk
from server.models import Colony, Stockpile
from server.vision import PROBE_SURVEY_RADIUS_LY, SENSOR_RANGE_LY
from test_ticker import GALAXY

HOME_STAR = '0,0:8'
HX, HY = GALAXY.star_pos(0, 0, 8)


def stars_between(lo, hi):
    cs = GALAXY.config.chunk_size_ly
    out = []
    for cx, cy in chunks_in_bounds(HX - hi, HY - hi, HX + hi, HY + hi, cs):
        for s in generate_chunk(cx, cy, GALAXY.config, GALAXY.density_field):
            if lo < math.hypot(s['worldX'] - HX, s['worldY'] - HY) <= hi:
                out.append(s['id'])
    return out


def system(c, star_id):
    chunk, idx = star_id.split(':')
    cx, cy = chunk.split(',')
    return c.get(f'/api/system?cx={cx}&cy={cy}&index={idx}').get_json()


def test_home_and_nearby_systems_are_known_far_ones_are_not(client):
    assert system(client, HOME_STAR)['surveyed'] and system(client, HOME_STAR)['planets']
    near = stars_between(1, SENSOR_RANGE_LY[3])
    far = stars_between(SENSOR_RANGE_LY[3] + 1, 300)
    assert near and far
    assert all(system(client, sid)['surveyed'] for sid in near[:5])
    for sid in far[:5]:
        s = system(client, sid)
        assert not s['surveyed'] and s['planets'] == []
        assert s['starId'] == sid                               # the star itself is still there


def test_unknown_planets_cannot_be_colonized_or_terraformed(client):
    q = '&'.join(f'{k}={v}' for k, v in NEAR.items())
    assert client.get(f'/api/colonization-preview?{q}').status_code == 404
    assert client.post('/api/colonies', json=NEAR).status_code == 404
    assert client.get('/api/terraform?planetId=0,-1:1:2').status_code == 404


def test_a_probe_surveys_its_target_and_neighbours(client, clock):
    clock.advance(minutes=60)                                   # for the probe's radioactives
    prev = client.get(f'/api/scout-preview?starId={NEAR_STAR}').get_json()
    assert prev['eligible'] and prev['surveyed'] is False
    client.post('/api/scouts', json={'sourcePlanetId': '0,0:8:2', 'destStarCx': 0,
                                     'destStarCy': -1, 'destStarIndex': 1})
    clock.advance(minutes=3)
    assert not system(client, NEAR_STAR)['surveyed']            # still flying
    clock.advance(minutes=1)
    s = system(client, NEAR_STAR)
    assert s['surveyed'] and len(s['planets']) >= 3
    [note] = client.get('/api/notifications').get_json()
    assert note['message'].startswith('Probe arrived at')
    nx, ny = GALAXY.star_pos(0, -1, 1)
    for sid in stars_between(0, 400):
        pos = GALAXY.star_pos(*map(int, sid.replace(':', ',').split(',')))
        if 0 < math.hypot(pos[0] - nx, pos[1] - ny) <= PROBE_SURVEY_RADIUS_LY:
            assert system(client, sid)['surveyed'], sid
    assert client.get(f'/api/scout-preview?starId={NEAR_STAR}').get_json()['surveyed']
    assert client.post('/api/colonies', json=NEAR).status_code == 201


def test_sensors_reach_further_with_development(client):
    ring = [sid for sid in stars_between(SENSOR_RANGE_LY[3] + 1, SENSOR_RANGE_LY[4])
            if not system(client, sid)['surveyed']]
    assert ring
    game = client.api.state.game
    with game.sessionmaker() as s:                               # make the homeworld dev 4
        hw = s.query(Colony).filter_by(planet_id='0,0:8:2').one()
        hw.dev_level = 4
        for st in s.query(Stockpile).filter_by(colony_id=hw.id):
            st.amount = 10_000_000
        s.commit()
    assert all(system(client, sid)['surveyed'] for sid in ring)


def test_other_players_cannot_see_your_systems(client):
    client.as_player(2)
    s = system(client, HOME_STAR)
    assert not s['surveyed'] and s['planets'] == []


def test_known_lists_sensor_range_and_surveys(client):
    known = set(client.get('/api/known').get_json()['starIds'])
    assert HOME_STAR in known and NEAR_STAR not in known
    assert set(stars_between(0, SENSOR_RANGE_LY[3])) <= known
    assert not known & set(stars_between(SENSOR_RANGE_LY[3] + 1, 300))
    client.survey(NEAR_STAR)
    assert NEAR_STAR in client.get('/api/known').get_json()['starIds']
    client.as_player(2)
    assert client.get('/api/known').get_json()['starIds'] == []
