"""The HTTP API as it behaves today (Flask, JSON save files). These pin
behaviour before the move to FastAPI + a database."""
import pytest

from conftest import HOMEWORLD, NEAR, NEAR_ID, colonies


def test_homeworld_is_founded_once(client):
    client.get('/api/homeworld')
    cols = colonies(client)
    assert list(cols) == [HOMEWORLD]
    hw = cols[HOMEWORLD]
    assert hw['isHomeworld'] and hw['size'] == 3 and hw['developmentLevel'] == 3
    assert hw['stockpiles']['metals'] == 150.0
    assert hw['sizeName'] == 'Town' and hw['devName'] == 'Advanced'


def test_colonies_catch_up_on_elapsed_ticks(client, clock):
    before = colonies(client)[HOMEWORLD]
    clock.advance(minutes=5, seconds=30)            # 5 whole ticks
    after = colonies(client)[HOMEWORLD]
    for res, net in before['netFlowPerTick'].items():
        assert after['stockpiles'][res] == pytest.approx(
            max(0.0, before['stockpiles'][res] + 5 * net), abs=0.01), res


def test_colonization_preview_lists_the_homeworld_as_source(client):
    q = '&'.join(f'{k}={v}' for k, v in NEAR.items())
    prev = client.get(f'/api/colonization-preview?{q}').get_json()
    assert prev['eligible']
    [src] = prev['sources']
    assert src['planetId'] == HOMEWORLD and src['transitTicks'] == 4 and src['canAfford']


def colonize(client, **extra):
    return client.post('/api/colonies', json={**NEAR, **extra})


def test_colonizing_spends_cost_then_arrives_after_transit(client, clock):
    hw0 = colonies(client)[HOMEWORLD]['stockpiles']
    r = colonize(client)
    assert r.status_code == 201
    cost_metals = 150.0 - colonies(client)[HOMEWORLD]['stockpiles']['metals']
    assert cost_metals > 50                          # habitability < 100 costs more
    col = colonies(client)[NEAR_ID]
    assert col['status'] == 'in_transit' and col['ticksRemaining'] == 4
    clock.advance(minutes=3)
    assert colonies(client)[NEAR_ID]['status'] == 'in_transit'
    clock.advance(minutes=1)
    col = colonies(client)[NEAR_ID]
    assert col['status'] == 'active' and col['size'] == 1 and col['developmentLevel'] == 1
    assert hw0['metals'] == 150.0


def test_colonizing_an_existing_colony_is_refused(client):
    assert colonize(client).status_code == 201
    assert colonize(client).status_code == 409


def test_colonizing_needs_a_source_in_range(client):
    far = {'cx': 20, 'cy': 20, 'starIndex': 0, 'planetIndex': 0}
    r = client.post('/api/colonies', json=far)
    assert r.status_code in (403, 404)


def test_upgrade_endpoint(client):
    r = client.post(f'/api/colonies/{HOMEWORLD}/upgrade')
    assert r.status_code == 400                       # 200 metals needed, has 150
    assert 'metals' in r.get_json()['error']
    assert client.post('/api/colonies/nope/upgrade').status_code == 404


def test_ships_by_dev_level(client):
    ships = client.get(f'/api/ships?planetId={HOMEWORLD}').get_json()
    assert [s['id'] for s in ships] == ['freighter_mk1', 'freighter_mk2']


def arrived_colony(client, clock):
    assert colonize(client).status_code == 201
    clock.advance(minutes=4)
    assert colonies(client)[NEAR_ID]['status'] == 'active'


def route_body(cargo_out, cargo_back=None):
    return {'name': 'Milk run', 'shipClass': 'freighter_mk1', 'legs': [
        {'fromPlanetId': HOMEWORLD, 'toPlanetId': NEAR_ID, 'cargo': cargo_out},
        {'fromPlanetId': NEAR_ID, 'toPlanetId': HOMEWORLD, 'cargo': cargo_back or {}},
    ]}


def test_route_spends_setup_and_first_cargo_then_delivers(client, clock):
    arrived_colony(client, clock)
    hw = colonies(client)[HOMEWORLD]['stockpiles']
    r = client.post('/api/routes', json=route_body({'food': 10}))
    assert r.status_code == 201
    hw2 = colonies(client)[HOMEWORLD]['stockpiles']
    assert hw2['food'] == pytest.approx(hw['food'] - 10)
    assert hw2['minerals'] == pytest.approx(hw['minerals'] - 30)        # setup cost
    near_food = colonies(client)[NEAR_ID]['stockpiles']['food']
    [route] = client.get('/api/routes').get_json()['routes']
    assert route['currentLeg']['transitTicks'] == 2                    # 181 Ly at 100 Ly/tick
    clock.advance(minutes=2)
    client.get('/api/routes')
    [route] = client.get('/api/routes').get_json()['routes']
    assert route['currentLegIndex'] == 1
    got = colonies(client)[NEAR_ID]['stockpiles']['food']
    assert got > near_food + 9                       # delivered (plus 2 ticks of economy)


def test_route_validation(client, clock):
    arrived_colony(client, clock)
    assert client.post('/api/routes', json=route_body({'food': 21})).status_code == 400  # capacity 20
    bad = route_body({})
    bad['shipClass'] = 'heavy_hauler'                                  # needs dev 4
    assert client.post('/api/routes', json=bad).status_code == 403
    assert client.post('/api/routes', json={'shipClass': 'freighter_mk1', 'legs': []}).status_code == 400


def test_route_edit_and_delete(client, clock):
    arrived_colony(client, clock)
    rid = client.post('/api/routes', json=route_body({})).get_json()['route']['routeId']
    r = client.patch(f'/api/routes/{rid}', json={'name': 'Renamed'})
    assert r.get_json()['route']['name'] == 'Renamed'
    assert client.delete(f'/api/routes/{rid}').status_code == 200
    assert client.delete(f'/api/routes/{rid}').status_code == 404


@pytest.mark.xfail(strict=True, reason='BUG: a route loads what the colony has but '
                   'delivers the full declared cargo, creating resources')
def test_routes_cannot_create_resources(client, clock):
    arrived_colony(client, clock)
    # the new colony starts with 10 food; ask it to ship 20 back every trip
    client.post('/api/routes', json=route_body({}, {'food': 20}))
    total0 = sum(c['stockpiles']['food'] for c in colonies(client).values())
    clock.advance(minutes=4)                          # out and back
    client.get('/api/routes')
    cols = colonies(client)
    produced = sum(c['netFlowPerTick']['food'] for c in cols.values()) * 4
    total1 = sum(c['stockpiles']['food'] for c in cols.values())
    assert total1 <= total0 + produced + 0.01


def test_scouts_launch_spend_and_arrive(client, clock):
    clock.advance(minutes=60)                         # build up radioactives etc.
    colonies(client)
    prev = client.get('/api/scout-preview?starId=0,-1:1').get_json()
    assert prev['eligible']
    r = client.post('/api/scouts', json={'sourcePlanetId': HOMEWORLD,
                                         'destStarCx': 0, 'destStarCy': -1, 'destStarIndex': 1})
    assert r.status_code == 201, r.get_json()
    scout = r.get_json()
    assert scout['transitTicks'] == 4
    clock.advance(minutes=4)
    [s] = client.get('/api/scouts').get_json()
    assert s['status'] == 'arrived'


@pytest.mark.xfail(strict=True, reason='BUG: a colony that arrived while nobody was '
                   'looking starts ticking from the next read, not from its arrival')
def test_arrival_ticks_count_from_arrival(client, clock):
    colonize(client)
    clock.advance(minutes=4 + 20)                     # arrived 20 ticks ago
    from generation.colony_economics import STARTER_STOCKPILES
    assert colonies(client)[NEAR_ID]['stockpiles'] != STARTER_STOCKPILES
