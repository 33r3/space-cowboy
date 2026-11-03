"""
Colony markets and free traders — pure functions, no I/O (docs/market.md).

Every colony works out how much of each resource it wants to keep (its
target): RESERVE_TICKS of what it uses, plus its next upgrade's cost when
it is saving for one, unless the owner set a figure. Above the target is
surplus it will sell; below it is a shortfall it will buy. The local
price follows: dear when short, cheap when overflowing.

A free trader is a freighter with no fixed route. When idle it takes the
job that earns the most per tick of flying: fly to a colony with surplus
(or load where it is), carry what a short colony wants, unload. Goods only
ever move from surplus to shortfall, so traders never shuffle stock in
circles, and when nobody is short they wait.

Amounts here are plain floats (units), prices are credits per unit.
"""
import math
from dataclasses import dataclass, field

from .colony_economics import ALL_RESOURCES, consumption_per_tick, upgrade_cost

# ── Knobs ─────────────────────────────────────────────────────────────────────

# What a unit is worth at a colony that has exactly what it wants
BASE_PRICE: dict[str, float] = {
    'food': 1.0, 'water': 1.0, 'minerals': 2.0, 'organicFuels': 3.0,
    'metals': 4.0, 'chemFeedstocks': 6.0, 'fusionFuel': 8.0, 'radioactives': 12.0,
}
RESERVE_TICKS = 60                  # keep an hour of what the colony uses
PRICE_FLOOR, PRICE_CEIL = 0.25, 4.0  # price range, as multiples of the base price
MIN_LOAD = 1.0                       # don't fly for less than one unit in all


# ── One colony's market ───────────────────────────────────────────────────────

def auto_targets(colony: dict, save_for_upgrade: bool = False) -> dict[str, float]:
    """What a colony wants to keep of each resource, before the owner's
    overrides. `colony` is an economy dict (habitability included, so life
    support counts)."""
    use = consumption_per_tick(colony)
    up = (upgrade_cost(colony) or {}) if save_for_upgrade else {}
    return {r: round(use.get(r, 0.0) * RESERVE_TICKS + up.get(r, 0.0), 3) for r in ALL_RESOURCES}


def price(resource: str, stock: float, target: float) -> float:
    """Credits per unit here: the base price times target/stock, kept
    between PRICE_FLOOR and PRICE_CEIL times the base (+1 so an empty,
    unwanted stock stays finite)."""
    ratio = (target + 1.0) / (stock + 1.0)
    return BASE_PRICE[resource] * min(PRICE_CEIL, max(PRICE_FLOOR, ratio))


@dataclass
class Market:
    """A colony as traders see it. `stock` is what it will have once the
    traders already on their way have loaded and unloaded."""
    stock:  dict[str, float]
    target: dict[str, float]
    no_export: set[str] = field(default_factory=set)
    no_import: set[str] = field(default_factory=set)

    def surplus(self, r: str) -> float:
        return 0.0 if r in self.no_export else max(0.0, self.stock.get(r, 0.0) - self.target.get(r, 0.0))

    def shortfall(self, r: str) -> float:
        return 0.0 if r in self.no_import else max(0.0, self.target.get(r, 0.0) - self.stock.get(r, 0.0))

    def price(self, r: str, change: float = 0.0) -> float:
        return price(r, max(0.0, self.stock.get(r, 0.0) + change), self.target.get(r, 0.0))

    def sells(self) -> bool:
        return any(self.surplus(r) > 0 for r in ALL_RESOURCES)

    def buys(self) -> bool:
        return any(self.shortfall(r) > 0 for r in ALL_RESOURCES)


def make_market(colony: dict, stock: dict[str, float], settings: dict | None = None,
                save_for_upgrade: bool = False) -> Market:
    """settings: {resource: {'keep': float | None, 'export': bool, 'import': bool}}."""
    target = auto_targets(colony, save_for_upgrade)
    no_export, no_import = set(), set()
    for r, s in (settings or {}).items():
        if s.get('keep') is not None:
            target[r] = float(s['keep'])
        if s.get('export') is False:
            no_export.add(r)
        if s.get('import') is False:
            no_import.add(r)
    return Market(dict(stock), target, no_export, no_import)


# ── Jobs ──────────────────────────────────────────────────────────────────────

def _offers(m: Market) -> tuple[dict, dict]:
    """({resource: (surplus, price)}, {resource: (shortfall, price)}) of
    one market, nonzero amounts only."""
    sell = {r: (v, m.price(r)) for r in ALL_RESOURCES if (v := m.surplus(r)) > 0}
    buy = {r: (v, m.price(r)) for r in ALL_RESOURCES if (v := m.shortfall(r)) > 0}
    return sell, buy


def _options(sell: dict, buy: dict) -> list[tuple[float, str, float]]:
    """(price gap, resource, most that can move), biggest gap first."""
    out = [(buy[r][1] - sell[r][1], r, min(sell[r][0], buy[r][0])) for r in sell.keys() & buy.keys()]
    out.sort(reverse=True)
    return out


def _bound(options, capacity: float) -> float:
    """What a load could be worth at today's price gaps: never less than
    its real value, since moving goods narrows the gap."""
    value, room = 0.0, capacity
    for gap, _, most in options:
        if room <= 0 or gap <= 0:
            break
        amt = min(most, room)
        value += amt * gap
        room -= amt
    return value


def _plan(src: Market, dst: Market, sell: dict, buy: dict, capacity: float, options=None):
    options = _options(sell, buy) if options is None else options
    if not options:
        return {}, 0.0
    cargo, value, room = {}, 0.0, capacity
    for gap, r, most in options:
        if room <= 0 or gap <= 0:
            break
        amt = round(min(most, room), 3)
        if amt <= 0:
            continue
        cargo[r] = amt
        room -= amt
        value += amt * (dst.price(r, amt / 2) - src.price(r, -amt / 2))
    return cargo, value


def plan_cargo(src: Market, dst: Market, capacity: float) -> tuple[dict[str, float], float]:
    """What to carry from src to dst: the resources with the biggest price
    gap first, each no more than src can spare and dst wants. Returns
    (cargo, value), value = credits the move is worth (price gap at the
    midpoint of the move, times the amount)."""
    return _plan(src, dst, _offers(src)[0], _offers(dst)[1], capacity)


@dataclass
class Job:
    source: object          # colony keys, whatever the caller uses
    dest:   object
    cargo:  dict[str, float]
    value:  float
    ticks:  int             # flying time, the empty leg to the source included


def best_job(at, capacity: float, max_range: float, transit, markets: dict, dist) -> Job | None:
    """The most valuable job per tick of flying for a trader sitting at
    colony `at`. transit(distance) -> ticks; dist(a, b) -> Ly between two
    colonies. A job's legs (the empty one included) are each within
    max_range."""
    offers = {k: _offers(m) for k, m in markets.items()}
    sellers = [k for k, (sell, _) in offers.items() if sell and dist(at, k) <= max_range]
    buyers = [k for k, (_, buy) in offers.items() if buy]
    best, best_score = None, 0.0
    for s in sellers:
        sell = offers[s][0]
        empty = 0 if s == at else transit(dist(at, s))
        for d in buyers:
            buy = offers[d][1]
            if d == s or sell.keys().isdisjoint(buy.keys()):
                continue
            leg = dist(s, d)
            if leg > max_range:
                continue
            ticks = empty + transit(leg)
            options = _options(sell, buy)
            if _bound(options, capacity) / ticks <= best_score:
                continue
            cargo, value = _plan(markets[s], markets[d], sell, buy, capacity, options)
            if sum(cargo.values()) < MIN_LOAD or value <= 0:
                continue
            score = value / ticks
            if score > best_score:
                best, best_score = Job(s, d, cargo, value, ticks), score
    return best


def reserve(job: Job, markets: dict) -> None:
    """Book a job into the markets, so the next trader plans around it."""
    for r, amt in job.cargo.items():
        markets[job.source].stock[r] = markets[job.source].stock.get(r, 0.0) - amt
        markets[job.dest].stock[r] = markets[job.dest].stock.get(r, 0.0) + amt


def transit_ticks(distance_ly: float, speed_ly_per_tick: float) -> int:
    return max(1, math.ceil(distance_ly / speed_ly_per_tick))
