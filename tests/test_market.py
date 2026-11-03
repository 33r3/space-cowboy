"""Colony markets and free traders (generation/market.py, server/trade.py)."""
import pytest
from sqlalchemy import select

from generation import market as mk
from server.models import Colony, MarketSetting, Ship, World
from server.ticker import advance
from server.trade import OwnerMarkets
from server.units import to_float, to_fixed

from test_ticker import GALAXY, HOME, NEAR, T0, colony, food, no_economy, s  # noqa: F401 (fixtures)


# ── The rules ─────────────────────────────────────────────────────────────────

def test_prices_are_dear_when_short_and_cheap_when_overflowing():
    assert mk.price('metals', 10, 10) == mk.BASE_PRICE['metals']
    assert mk.price('metals', 0, 100) == mk.BASE_PRICE['metals'] * mk.PRICE_CEIL
    assert mk.price('metals', 1000, 0) == mk.BASE_PRICE['metals'] * mk.PRICE_FLOOR
    assert mk.price('food', 5, 20) > mk.price('food', 15, 20) > mk.price('food', 40, 20)


def _m(stock, target, **kw):
    return mk.Market(dict(stock), dict(target), **kw)


def test_cargo_goes_only_from_surplus_to_shortfall_and_fits_the_hold():
    src = _m({'food': 100, 'metals': 50, 'water': 5}, {'food': 20, 'metals': 10, 'water': 20})
    dst = _m({'food': 0, 'metals': 0, 'water': 0}, {'food': 30, 'metals': 100, 'water': 20})
    cargo, value = mk.plan_cargo(src, dst, capacity=50)
    assert 'water' not in cargo                    # src is short of water itself
    assert sum(cargo.values()) == 50
    assert cargo['metals'] == 40                   # all src can spare, dearer gap first
    assert cargo['food'] == 10
    assert value > 0
    cargo, _ = mk.plan_cargo(src, dst, capacity=500)
    assert cargo == {'metals': 40, 'food': 30}     # food: no more than dst wants


def test_no_job_when_nobody_is_short():
    markets = {1: _m({'food': 100}, {'food': 10}), 2: _m({'food': 50}, {'food': 10})}
    job = mk.best_job(1, 20, 300, lambda d: 1, markets, lambda a, b: 0 if a == b else 100)
    assert job is None


def test_best_job_weighs_value_against_flying_time():
    markets = {1: _m({'food': 100}, {'food': 0}),
               2: _m({'food': 0}, {'food': 20}),       # near
               3: _m({'food': 0}, {'food': 20})}       # far, same need
    far = {(1, 2): 50, (1, 3): 250, (2, 3): 200}
    dist = lambda a, b: 0 if a == b else far[tuple(sorted((a, b)))]
    job = mk.best_job(1, 20, 300, lambda d: max(1, -(-d // 100)), markets, dist)
    assert (job.source, job.dest) == (1, 2)
    mk.reserve(job, markets)
    job2 = mk.best_job(1, 20, 300, lambda d: max(1, -(-d // 100)), markets, dist)
    assert (job2.source, job2.dest) == (1, 3)     # 2 is supplied now


def test_owner_settings_override_the_automatic_targets():
    colony = {'size': 1, 'developmentLevel': 1, 'stockpiles': {}}
    auto = mk.auto_targets(colony)
    assert auto['food'] == 0.25 * mk.RESERVE_TICKS and auto['metals'] == 0
    m = mk.make_market(colony, {'food': 100, 'metals': 0},
                       {'food': {'export': False}, 'metals': {'keep': 40}})
    assert m.surplus('food') == 0 and m.shortfall('metals') == 40
    saving = mk.auto_targets(colony, save_for_upgrade=True)
    assert saving['metals'] == 20 and saving['minerals'] == 50     # dev 1 -> 2 costs


# ── Traders in the ticker ─────────────────────────────────────────────────────

def trader(s, at, cls='freighter_mk1', owner_id=1, uid=None):
    sh = Ship(uid=uid or f'trader-{at.id}-{cls}', owner_id=owner_id, kind='trader', status='idle',
              to_colony_id=at.id, departed_tick=T0, arrival_tick=T0, cargo={},
              ship_class=cls, trade={})
    s.add(sh)
    s.flush()
    return sh


def total(s, res='food'):
    stocks = sum(food(c) for c in s.scalars(select(Colony))) if res == 'food' else None
    aboard = sum(to_float(sh.cargo.get(res, 0)) for sh in s.scalars(select(Ship)))
    return round(stocks + aboard, 3)


def test_a_trader_carries_surplus_to_a_colony_that_is_short(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    near = colony(s, NEAR, stock={'food': 0})
    want = OwnerMarkets(s, GALAXY, 1).markets[near.id].shortfall('food')
    assert want > 0
    sh = trader(s, home)
    before = total(s)
    advance(s, GALAXY, T0 + 1)
    assert sh.status == 'in_transit' and sh.trade['phase'] == 'deliver'
    assert to_float(sh.cargo['food']) == min(20, want)
    assert total(s) == before
    for t in range(2, 12):
        advance(s, GALAXY, T0 + t)
        assert total(s) == before, t
    # it keeps going until near has what it wants, then waits there or at home
    assert abs(OwnerMarkets(s, GALAXY, 1).markets[near.id].shortfall('food')) < 1e-6
    assert sh.trade['trips'] >= 1 and sh.trade['last']['to'] == near.name
    assert sh.status == 'idle'


def test_a_trader_flies_empty_to_the_seller_first(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    near = colony(s, NEAR, stock={'food': 0})
    sh = trader(s, near)
    advance(s, GALAXY, T0 + 1)
    assert sh.trade['phase'] == 'pickup' and sh.to_colony_id == home.id and sh.cargo == {}
    while sh.trade.get('phase') == 'pickup':
        advance(s, GALAXY, s.get(World, 1).last_tick + 1)
    assert sh.trade['phase'] == 'deliver' and sh.to_colony_id == near.id
    assert sh.cargo['food'] == to_fixed(15)          # near wants 60 ticks of 0.25
    assert food(home) == 185


def test_two_traders_dont_chase_one_shortfall(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    near = colony(s, NEAR, stock={'food': 0})
    s.add(MarketSetting(colony_id=near.id, resource='food', keep=to_fixed(15)))
    a, b = trader(s, home), trader(s, home, uid='second')
    advance(s, GALAXY, T0 + 1)
    assert a.status == 'in_transit' and b.status == 'idle'     # 15 fits in one hold


def test_no_export_keeps_goods_home(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    colony(s, NEAR, stock={'food': 0})
    s.add(MarketSetting(colony_id=home.id, resource='food', export=False))
    sh = trader(s, home)
    advance(s, GALAXY, T0 + 3)
    assert sh.status == 'idle' and food(home) == 200


def test_a_scrapped_trader_finishes_its_delivery_then_goes(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    near = colony(s, NEAR, stock={'food': 0})
    sh = trader(s, home)
    advance(s, GALAXY, T0 + 1)
    sh.trade = {**sh.trade, 'retire': True}
    advance(s, GALAXY, T0 + 4)
    assert s.scalars(select(Ship)).all() == []
    assert food(near) == 15 and food(home) == 185


def test_cargo_for_an_abandoned_colony_goes_back(s, no_economy):
    home = colony(s, HOME, stock={'food': 200})
    near = colony(s, NEAR, stock={'food': 0})
    sh = trader(s, home)
    advance(s, GALAXY, T0 + 1)
    near.status = 'abandoned'
    advance(s, GALAXY, T0 + 3)
    assert sh.to_colony_id == home.id and sh.trade.get('returning')
    advance(s, GALAXY, T0 + 6)
    assert sh.status == 'idle' and food(home) == 200


# ── The API ───────────────────────────────────────────────────────────────────

from conftest import HOMEWORLD, NEAR_ID, colonies          # noqa: E402
from test_api import arrived_colony                         # noqa: E402


def test_build_a_trader_and_watch_it_supply_a_new_colony(client, clock):
    arrived_colony(client, clock)
    hw = colonies(client)[HOMEWORLD]['stockpiles']
    r = client.post('/api/traders', json={'planetId': HOMEWORLD, 'shipClass': 'freighter_mk1'})
    assert r.status_code == 201
    assert colonies(client)[HOMEWORLD]['stockpiles']['minerals'] == pytest.approx(hw['minerals'] - 30)
    m = client.get(f'/api/market?planetId={NEAR_ID}').get_json()
    food_row = next(x for x in m['resources'] if x['resource'] == 'food')
    assert food_row['shortfall'] > 0 and food_row['price'] > food_row['basePrice']
    clock.advance(minutes=1)
    [t] = client.get('/api/traders').get_json()['traders']
    assert t['status'] == 'deliver' and t['toName'] and t['cargo']
    m = client.get(f'/api/market?planetId={NEAR_ID}').get_json()
    assert any(x['incoming'] > 0 for x in m['resources'])     # counted before it lands
    clock.advance(minutes=3)
    [t] = client.get('/api/traders').get_json()['traders']
    assert t['trips'] >= 1


def test_market_settings_round_trip(client, clock):
    arrived_colony(client, clock)
    r = client.patch('/api/market', json={'planetId': HOMEWORLD, 'saveForUpgrade': True,
                                          'resources': {'metals': {'keep': 500, 'export': False}}})
    assert r.status_code == 200
    m = r.get_json()
    metals = next(x for x in m['resources'] if x['resource'] == 'metals')
    assert m['saveForUpgrade'] and metals['keep'] == 500 and metals['target'] == 500
    assert metals['export'] is False and metals['surplus'] == 0
    m = client.patch('/api/market', json={'planetId': HOMEWORLD, 'resources': {
        'metals': {'keep': None, 'export': True}}}).get_json()
    metals = next(x for x in m['resources'] if x['resource'] == 'metals')
    assert metals['keep'] is None and metals['target'] == metals['autoTarget']
    assert client.patch('/api/market', json={'planetId': HOMEWORLD, 'resources': {
        'metals': {'keep': -1}}}).status_code == 400
    assert client.patch('/api/market', json={'planetId': HOMEWORLD, 'resources': {
        'gold': {}}}).status_code == 400


def test_traders_are_their_owners(client, clock):
    arrived_colony(client, clock)
    tid = client.post('/api/traders', json={'planetId': HOMEWORLD, 'shipClass': 'freighter_mk1'}
                      ).get_json()['trader']['traderId']
    assert client.post('/api/traders', json={'planetId': HOMEWORLD, 'shipClass': 'heavy_hauler'}
                       ).status_code == 403                                # needs dev 4
    client.as_player(2)
    assert client.get('/api/traders').get_json() == {'traders': []}
    assert client.delete(f'/api/traders/{tid}').status_code == 404
    assert client.get(f'/api/market?planetId={HOMEWORLD}').status_code == 404
    client.as_player(1)
    assert client.delete(f'/api/traders/{tid}').get_json()['scrapped'] is True   # idle: at once
    assert client.get('/api/traders').get_json() == {'traders': []}


# ── Outlook ───────────────────────────────────────────────────────────────────

from generation import outlook as ol                       # noqa: E402


def test_outlook_states():
    assert ol.state(1.0, 2.0, 50) == ('ok', None)
    assert ol.state(0.1, 2.0, 50) == ('tight', None)          # grows by under 10% of use
    assert ol.state(0.0, 0.0, 0) == ('ok', None)              # nothing uses it
    assert ol.state(-0.5, 2.0, 100) == ('falling', 200)
    assert ol.state(-1.0, 2.0, 30) == ('critical', 30)
    rows = ol.resource_rows({'food': 30, 'water': 100}, {'food': 1, 'water': 1}, {'food': 2, 'water': 0.95})
    assert ol.worst(rows)['resource'] == 'food'
    assert ol.room_for_outposts([{'resource': r, 'net': 1.0} for r in ('food', 'water')]) == \
        {'food': 4, 'water': 4}                                # an outpost eats 0.25 of each


def test_outlook_api(client, clock):
    from conftest import NEAR, NEAR_STAR
    from test_api import colonize
    client.survey(NEAR_STAR)
    q = '&'.join(f'{k}={v}' for k, v in NEAR.items())
    pre = client.get(f'/api/colonization-preview?{q}').get_json()
    assert pre['eligible'] and pre['asOutpost']['food'] < 0.5      # an outpost's whole net
    assert colonize(client).status_code == 201
    o = client.get('/api/outlook').get_json()
    assert o['civ']['colonies'] == 1 and len(o['civ']['landing']) == 1
    assert o['civ']['afterLanding'] is not None
    clock.advance(minutes=4)
    o = client.get('/api/outlook').get_json()
    assert o['civ']['colonies'] == 2 and o['civ']['afterLanding'] is None
    food = next(r for r in o['civ']['resources'] if r['resource'] == 'food')
    cols = o['colonies']
    assert food['made'] == pytest.approx(sum(
        next(r['made'] for r in c['resources'] if r['resource'] == 'food') for c in cols))
    assert set(o['civ']['roomForOutposts']) == {'food', 'water'}
