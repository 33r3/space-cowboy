"""Nobody can see or spend what another player owns."""
from conftest import HOMEWORLD, NEAR, NEAR_ID, colonies


def setup_p1(c, clock):
    """Player 1: homeworld (fixture), a landed colony, a route, a scout."""
    c.post('/api/colonies', json=NEAR)
    clock.advance(minutes=60)
    rid = c.post('/api/routes', json={'name': 'P1 run', 'shipClass': 'freighter_mk1', 'legs': [
        {'fromPlanetId': HOMEWORLD, 'toPlanetId': NEAR_ID, 'cargo': {}},
        {'fromPlanetId': NEAR_ID, 'toPlanetId': HOMEWORLD, 'cargo': {}}]}).get_json()['route']['routeId']
    assert c.post('/api/scouts', json={'sourcePlanetId': HOMEWORLD, 'destStarCx': 0,
                                       'destStarCy': -1, 'destStarIndex': 1}).status_code == 201
    return rid


def test_a_second_player_sees_and_touches_nothing_of_the_first(fastapi_client, clock):
    c = fastapi_client
    rid = setup_p1(c, clock)
    p1_before = colonies(c)

    c.as_player(2)
    assert c.get('/api/colonies').get_json() == {'homeworld': None, 'colonies': []}
    assert c.get('/api/routes').get_json() == {'routes': []}
    assert c.get('/api/scouts').get_json() == []
    assert c.post(f'/api/colonies/{HOMEWORLD}/upgrade').status_code == 404
    assert c.get(f'/api/ships?planetId={HOMEWORLD}').status_code == 404
    q = '&'.join(f'{k}={v}' for k, v in NEAR.items())
    assert c.get(f'/api/colonization-preview?{q}').get_json()['eligible'] is False
    far = {'cx': 1, 'cy': 1, 'starIndex': 28, 'planetIndex': 2}
    assert c.post('/api/colonies', json={**far, 'sourcePlanetId': HOMEWORLD}).status_code == 404
    assert c.post('/api/colonies', json=far).status_code == 403
    assert c.post('/api/routes', json={'shipClass': 'freighter_mk1', 'legs': [
        {'fromPlanetId': HOMEWORLD, 'toPlanetId': NEAR_ID, 'cargo': {'food': 5}}]}).status_code == 404
    assert c.post('/api/scouts', json={'sourcePlanetId': HOMEWORLD, 'destStarCx': 0,
                                       'destStarCy': -1, 'destStarIndex': 1}).status_code == 404
    assert c.patch(f'/api/routes/{rid}', json={'name': 'mine now'}).status_code == 404
    assert c.delete(f'/api/routes/{rid}').status_code == 404
    assert c.post(f'/api/routes/{rid}/events/read').status_code == 404

    c.as_player(1)
    after = colonies(c)
    assert {k: v['stockpiles'] for k, v in after.items()} == \
        {k: v['stockpiles'] for k, v in p1_before.items()}
    [route] = c.get('/api/routes').get_json()['routes']
    assert route['name'] == 'P1 run'
