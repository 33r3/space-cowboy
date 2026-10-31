"""Colony economy rules (generation/colony_economics.py)."""
import pytest

from generation import colony_economics as ce

YIELDS = {'food': 1.0, 'water': 1.0, 'minerals': 0.5}


def colony(**kw):
    return ce.migrate_colony({'planetId': 'x', **kw})


def test_extraction_scales_with_size_and_dev():
    c = colony(size=3, developmentLevel=2)            # size x2.0, dev x1.5
    assert ce.extraction_per_tick(c, YIELDS) == {'food': 3.0, 'water': 3.0, 'minerals': 1.5}


def test_consumption_unlocks_with_dev():
    c = colony(size=2, developmentLevel=3)            # size x1.0, dev x2.5
    con = ce.consumption_per_tick(c)
    assert con['food'] == 0.5 and con['water'] == 0.5          # size only
    assert con['minerals'] == 0.5                              # 0.2 x 2.5
    assert con['metals'] == 0.25 and con['organicFuels'] == 0.25
    assert con['fusionFuel'] == 0.0


def test_well_fed_colony_grows_after_ten_ticks():
    c = colony(size=1, stockpiles={'food': 100, 'water': 100})
    c = ce.apply_ticks(c, YIELDS, 9)
    assert c['size'] == 1 and c['growthProgress'] == 9
    c = ce.apply_ticks(c, YIELDS, 1)
    assert c['size'] == 2 and c['growthProgress'] == 0


def test_apply_ticks_does_not_mutate_its_input():
    c = colony(stockpiles={'food': 5})
    ce.apply_ticks(c, YIELDS, 3)
    assert c['stockpiles']['food'] == 5


def test_starving_ten_ticks_demotes_dev():
    c = colony(size=2, developmentLevel=2)            # needs minerals, has none
    c = ce.apply_ticks(c, {'food': 1, 'water': 1}, 10)
    assert c['developmentLevel'] == 1 and c['starvationTicks'] == 0


def test_starving_at_dev_1_abandons_but_never_the_homeworld():
    starving = {'food': 0, 'water': 0}
    assert ce.apply_ticks(colony(), starving, 10)['status'] == 'abandoned'
    hw = ce.apply_ticks(colony(isHomeworld=True), starving, 30)
    assert hw['status'] == 'active'


def test_in_transit_and_abandoned_colonies_do_not_tick():
    for status in ('in_transit', 'abandoned'):
        c = colony(status=status)
        assert ce.apply_ticks(c, YIELDS, 5)['stockpiles'] == c['stockpiles']


def test_upgrade_needs_and_spends_the_cost():
    c = colony(developmentLevel=1, stockpiles={'minerals': 49, 'metals': 20})
    ok, reason = ce.can_upgrade_dev(c)
    assert not ok and 'minerals' in reason
    c['stockpiles']['minerals'] = 50
    assert ce.can_upgrade_dev(c) == (True, '')
    up = ce.apply_upgrade_dev(c)
    assert up['developmentLevel'] == 2
    assert up['stockpiles']['minerals'] == 0 and up['stockpiles']['metals'] == 0
    assert ce.can_upgrade_dev(colony(developmentLevel=5))[0] is False


def test_colonization_cost_rises_on_hostile_worlds():
    assert ce.colonization_cost(100) == {'metals': 50.0, 'food': 25.0, 'water': 15.0}
    assert ce.colonization_cost(50) == {'metals': 100.0, 'food': 50.0, 'water': 30.0}
    assert ce.colonization_range(2) == 0.0 and ce.colonization_range(3) == 300.0
    assert ce.scout_range(4) == pytest.approx(900.0)
