"""Terraforming: planets move, habitability bites, rivals get hurt."""
import pytest
from sqlalchemy import select

from conftest import HOMEWORLD, NEAR_ID
from generation import colony_economics as ce
from generation import terraform as tf
from server.models import Colony, Notification, Planet, Player, TerraformProject
from server.ticker import advance
from test_ticker import GALAXY, NEAR as NEAR_ROW, T0, colony, s  # noqa: F401,F811 (s: fixture)

KAINAI = GALAXY.planet(NEAR_ID)
KAINAI_STAR = GALAXY.star(0, -1, 1)


# ── The rules ─────────────────────────────────────────────────────────────────

def test_size_cap_and_life_support_follow_habitability():
    assert [tf.size_cap(h) for h in (100, 65, 64, 45, 25, 10, 9)] == [5, 5, 4, 4, 3, 2, 1]
    assert tf.life_support(45, 1.0) == {} and tf.life_support(90, 8.0) == {}
    assert tf.life_support(0, 1.0) == tf.LIFE_SUPPORT_PER_TICK
    assert tf.life_support(22.5, 2.0) == {'water': 0.2, 'metals': 0.05}


def test_cooling_freezes_seas_and_starves_life():
    cold = tf.derive_planet(KAINAI, KAINAI_STAR, {'temperatureDeltaK': -100})
    assert cold['surfaceTempK'] == pytest.approx(KAINAI['surfaceTempK'] - 100)
    assert cold['hydrosphere']['liquidFraction'] < KAINAI['hydrosphere']['liquidFraction']
    assert cold['colonyYields']['water'] < KAINAI['colonyYields']['water']
    assert cold['colonyYields']['food'] < KAINAI['colonyYields']['food']
    assert cold['habitability']['total'] < KAINAI['habitability']['total']
    assert cold['terraforming']['temperatureDeltaK'] == -100


def test_thickening_the_air_warms_it_too():
    thick = tf.derive_planet(KAINAI, KAINAI_STAR, {'pressureDeltaAtm': 1.0})
    assert thick['atmosphere']['pressure'] == pytest.approx(KAINAI['atmosphere']['pressure'] + 1)
    assert thick['surfaceTempK'] > KAINAI['surfaceTempK']
    assert tf.derive_planet(KAINAI, KAINAI_STAR, {'pressureDeltaAtm': -5})['atmosphere']['pressure'] == 0


def test_harsh_worlds_cost_life_support_and_cap_size():
    c = ce.migrate_colony({'planetId': 'x', 'size': 3, 'habitability': 20,
                           'stockpiles': {'food': 100, 'water': 100, 'metals': 100}})
    con = ce.consumption_per_tick(c)
    assert con['metals'] == pytest.approx(tf.life_support(20, 2.0)['metals'])
    assert con['water'] == pytest.approx(1.0 + tf.life_support(20, 2.0)['water'])
    yields = {'food': 5, 'water': 5, 'metals': 1}
    c = ce.apply_ticks(c, yields, tf.SHRINK_TICKS - 1)
    assert c['size'] == 3                                   # cap 2 at hab 20: shrinking...
    c = ce.apply_ticks(c, yields, 1)
    assert c['size'] == 2
    c = ce.apply_ticks(c, yields, 500)
    assert c['size'] == 2                                   # ...and never grows past the cap


def test_without_habitability_nothing_changes():
    """Old saves and the Flask app pass no habitability: no cap, no upkeep."""
    c = ce.migrate_colony({'planetId': 'x', 'size': 5, 'stockpiles': {'food': 99, 'water': 99}})
    assert ce.consumption_per_tick(c)['metals'] == 0
    assert ce.apply_ticks(c, {'food': 9, 'water': 9}, 100)['size'] == 5


# ── Projects on the clock ─────────────────────────────────────────────────────

def project(s, col, lever='temperature', target=-1.0, planet_id=None):
    pr = TerraformProject(planet_id=planet_id or col.planet_id, owner_id=col.owner_id,
                          colony_id=col.id, lever=lever, target=target, status='active',
                          started_tick=T0)
    s.add(pr)
    s.flush()
    return pr


def offset(s, planet_id, key='temperatureDeltaK'):
    row = s.get(Planet, planet_id)
    return row.overrides.get('terraforming', {}).get(key, 0.0) if row else 0.0


RICH = {'food': 500, 'water': 500, 'metals': 500, 'fusionFuel': 500, 'chemFeedstocks': 500}


def test_a_project_moves_its_planet_and_pays_each_tick(s, monkeypatch):
    import server.ticker as tk
    monkeypatch.setattr(tk, 'run_economy', lambda *a: None)     # only the project spends
    col = colony(s, NEAR_ROW, size=2, dev=3, stock=RICH)
    pr = project(s, col, target=-1.0)
    rate = tf.lever_rate('temperature', 3)
    advance(s, GALAXY, T0 + 10)
    assert offset(s, NEAR_ID) == pytest.approx(-10 * rate)
    have = {x.resource: x.amount for x in col.stockpiles}
    assert have['metals'] == 500_000 - 10 * 80             # orbital shades: 0.08 metals a tick
    assert have['fusionFuel'] == 500_000 - 10 * 20
    advance(s, GALAXY, T0 + int(1 / rate) + 5)
    assert offset(s, NEAR_ID) == -1.0 and pr.status == 'done'
    [note] = s.scalars(select(Notification)).all()
    assert 'done' in note.message and 'Kainai III' in note.message


def test_a_project_stalls_when_unpaid_and_resumes(s):
    col = colony(s, NEAR_ROW, size=2, dev=3, stock={'food': 50, 'water': 50})
    pr = project(s, col, target=+5.0)                      # warming needs chem + fusion
    advance(s, GALAXY, T0 + 3)
    assert pr.status == 'stalled' and offset(s, NEAR_ID) == 0.0
    assert len(s.scalars(select(Notification)).all()) == 1  # said once, not every tick
    for st in col.stockpiles:
        if st.resource in ('chemFeedstocks', 'fusionFuel'):
            st.amount = 100_000
    advance(s, GALAXY, T0 + 4)
    assert pr.status == 'active' and offset(s, NEAR_ID) > 0


def test_opposing_projects_cancel_out(s):
    s.add(Player(id=2, name='P2', created_tick=T0))
    s.flush()
    mine = colony(s, NEAR_ROW, size=2, dev=3, stock=RICH)
    theirs = colony(s, NEAR_ROW, size=2, dev=3, stock=RICH, owner_id=2)
    project(s, mine, target=+50)
    project(s, theirs, target=-50)
    advance(s, GALAXY, T0 + 20)
    assert offset(s, NEAR_ID) == pytest.approx(0.0, abs=1e-9)


def test_a_project_stops_when_its_colony_falls(s):
    col = colony(s, NEAR_ROW, size=2, dev=3, stock=RICH)
    pr = project(s, col, target=-5)
    col.dev_level = 2
    advance(s, GALAXY, T0 + 1)
    assert pr.status == 'stopped'


def test_weaponised_cooling_shrinks_a_rival(s, monkeypatch):
    """Cool a shared world hard and the rival's colony loses size."""
    monkeypatch.setitem(tf.LEVERS['temperature'], 'rate', 25.0)      # fast-forward the days
    s.add(Player(id=2, name='P2', created_tick=T0))
    s.flush()
    attacker = colony(s, NEAR_ROW, size=1, dev=3, stock=RICH)
    victim = colony(s, NEAR_ROW, size=5, dev=1, stock={'food': 900, 'water': 900}, owner_id=2)
    project(s, attacker, target=-tf.LEVERS['temperature']['max'])
    advance(s, GALAXY, T0 + 10)
    hab = GALAXY.planet(NEAR_ID, s.get(Planet, NEAR_ID).overrides)['habitability']['total']
    assert tf.size_cap(hab) < 5
    advance(s, GALAXY, T0 + 10 + tf.SHRINK_TICKS)
    assert victim.size == 4


# ── The API ───────────────────────────────────────────────────────────────────

def test_terraform_api(fastapi_client, clock):
    c = fastapi_client
    info = c.get(f'/api/terraform?planetId={HOMEWORLD}').get_json()
    assert info['temperatureDeltaK'] == 0 and info['sizeCap'] == 5
    [src] = info['sources']
    assert src['planetId'] == HOMEWORLD and src['perDay']['temperature'] == pytest.approx(10 / 3, abs=0.01)

    assert c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'gravity',
                                          'target': 1}).status_code == 400
    assert c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'temperature',
                                          'target': 999}).status_code == 400
    r = c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'temperature', 'target': 5})
    assert r.status_code == 201 and r.get_json()['mine']
    assert c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'temperature',
                                          'target': 3}).status_code == 409
    clock.advance(minutes=30)
    info = c.get(f'/api/terraform?planetId={HOMEWORLD}').get_json()
    assert 0 < info['temperatureDeltaK'] < 5
    [proj] = info['projects']
    system = c.get('/api/system?cx=0&cy=0&index=8').get_json()
    hw = next(p for p in system['planets'] if p['id'] == HOMEWORLD)
    assert hw['terraforming']['activeProjects'] == [{'lever': 'temperature', 'target': 5.0,
                                                     'status': 'active'}]
    assert 'habitability' in c.get('/api/colonies').get_json()['colonies'][0]

    c.as_player(2)
    assert c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'pressure',
                                          'target': 1}).status_code == 404    # unknown to p2
    c.survey('0,0:8')
    assert c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'pressure',
                                          'target': 1}).status_code == 403    # known, no colony
    assert c.delete(f'/api/terraform/{proj["id"]}').status_code == 404
    c.as_player(1)
    assert c.delete(f'/api/terraform/{proj["id"]}').get_json() == {'ok': True}
    assert c.get(f'/api/terraform?planetId={HOMEWORLD}').get_json()['projects'] == []


def test_colonists_hear_when_someone_terraforms_their_world(fastapi_client, clock):
    c = fastapi_client
    game = c.api.state.game
    with game.sessionmaker() as s2:                       # player 2 lives on the homeworld too
        s2.add(Player(id=2, name='Rival', created_tick=0))
        s2.flush()
        s2.add(Colony(owner_id=2, planet_id=HOMEWORLD, name='Squatters', cx=0, cy=0, star_index=8,
                      founded_tick=0, status='active', size=1, dev_level=1, growth_progress=0,
                      starvation_ticks=0, is_homeworld=False))
        s2.commit()
    c.post('/api/terraform', json={'planetId': HOMEWORLD, 'lever': 'pressure', 'target': -0.5})
    c.as_player(2)
    [note] = c.get('/api/notifications').get_json()
    assert 'Player 1 began terraforming Zeum III' in note['message'] and not note['read']
    c.post('/api/notifications/read')
    assert c.get('/api/notifications').get_json()[0]['read']
