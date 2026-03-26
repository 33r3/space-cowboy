"""
Colony economic engine — pure functions, no I/O.

Resources flow each tick:
  extraction = planet_yields × size_mult × dev_mult
  consumption = base (food/water × size) + dev-unlocked resources × size × dev
  stockpile   += extraction - consumption  (floor 0)

Colony size grows after GROWTH_TICKS_NEEDED consecutive well-fed ticks.
Development level can be upgraded by spending stockpile resources.
"""
import copy
from datetime import datetime, timezone

# ── Constants ─────────────────────────────────────────────────────────────────

TICK_SECONDS = 60   # 1 real-world minute = 1 game tick

SIZE_NAMES = ['Outpost', 'Settlement', 'Town', 'City', 'Megacity']
SIZE_MULT  = [0.5, 1.0, 2.0, 4.0, 8.0]

DEV_NAMES  = ['Primitive', 'Industrial', 'Advanced', 'Sophisticated', 'Transcendent']
DEV_MULT   = [1.0, 1.5, 2.5, 4.0, 6.0]

GROWTH_TICKS_NEEDED = 10   # consecutive well-fed ticks required to grow

# Base per-tick consumption, scaled by size multiplier only
BASE_CONSUMPTION: dict[str, float] = {
    'food':  0.5,
    'water': 0.5,
}

# Additional consumption unlocked at each dev level, scaled by size × dev
DEV_CONSUMPTION: dict[int, dict[str, float]] = {
    2: {'minerals':       0.2},
    3: {'metals':         0.1,  'organicFuels':   0.1},
    4: {'chemFeedstocks': 0.05, 'fusionFuel':     0.05},
    5: {'radioactives':   0.02},
}

# Stockpile cost to upgrade from level N to N+1
DEV_UPGRADE_COSTS: dict[int, dict[str, float]] = {
    1: {'minerals': 50,  'metals': 20},
    2: {'minerals': 100, 'metals': 50,  'organicFuels': 30},
    3: {'metals':   200, 'chemFeedstocks': 100, 'fusionFuel': 50},
    4: {'metals':   500, 'chemFeedstocks': 200, 'fusionFuel': 100, 'radioactives': 50},
}

ALL_RESOURCES = [
    'food', 'water', 'organicFuels', 'chemFeedstocks',
    'minerals', 'fusionFuel', 'metals', 'radioactives',
]

STARTER_STOCKPILES = {
    'food': 10.0, 'water': 10.0, 'minerals': 5.0, 'metals': 5.0,
    'organicFuels': 0.0, 'chemFeedstocks': 0.0, 'fusionFuel': 0.0, 'radioactives': 0.0,
}

# ── Colonization constraints ──────────────────────────────────────────────────

MIN_DEV_TO_COLONIZE = 3   # source colony must be at least Advanced

COLONIZATION_RANGE_LY: dict[int, float] = {
    3: 300.0,   # Advanced
    4: 600.0,   # Sophisticated
    5: 1200.0,  # Transcendent
}

COLONIZATION_BASE_COST: dict[str, float] = {
    'metals': 50.0,
    'food':   25.0,
    'water':  15.0,
}


def colonization_cost(target_habitability: int) -> dict[str, float]:
    """Scale base colonization cost by difficulty of the target world.
    Lower habitability → higher cost (hostile worlds require more investment)."""
    mult = 100 / max(1, target_habitability)
    return {k: round(v * mult, 1) for k, v in COLONIZATION_BASE_COST.items()}


def colonization_range(source_dev_level: int) -> float:
    """Max colonization range in light-years for a given source dev level."""
    return COLONIZATION_RANGE_LY.get(source_dev_level, 0.0)

# ── Migration ─────────────────────────────────────────────────────────────────

def migrate_colony(colony: dict) -> dict:
    """Ensure colony has all required fields (backward-compat defaults)."""
    colony = dict(colony)
    colony.setdefault('size', 1)
    colony.setdefault('developmentLevel', 1)
    colony.setdefault('growthProgress', 0)
    colony.setdefault('lastTickedAt', _now_iso())
    colony.setdefault('stockpiles', {r: 0.0 for r in ALL_RESOURCES})
    # Ensure all resource keys exist in stockpiles
    for r in ALL_RESOURCES:
        colony['stockpiles'].setdefault(r, 0.0)
    return colony

# ── Core economic functions ───────────────────────────────────────────────────

def extraction_per_tick(colony: dict, planet_yields: dict) -> dict[str, float]:
    """Resources extracted per tick, scaled by size and dev level."""
    s = SIZE_MULT[colony['size'] - 1]
    d = DEV_MULT[colony['developmentLevel'] - 1]
    return {k: round(v * s * d, 3) for k, v in planet_yields.items()}


def consumption_per_tick(colony: dict) -> dict[str, float]:
    """Resources consumed per tick across all active needs."""
    s   = SIZE_MULT[colony['size'] - 1]
    d   = DEV_MULT[colony['developmentLevel'] - 1]
    dev = colony['developmentLevel']

    result: dict[str, float] = {}

    # Base food + water scale with size only
    for k, base in BASE_CONSUMPTION.items():
        result[k] = round(base * s, 3)

    # Dev-unlocked resources scale with size × dev
    for level in range(2, dev + 1):
        for k, base in DEV_CONSUMPTION.get(level, {}).items():
            result[k] = round(result.get(k, 0.0) + base * s * d, 3)

    # Pad missing keys with 0 so callers don't need to handle KeyError
    for r in ALL_RESOURCES:
        result.setdefault(r, 0.0)

    return result


def net_flow_per_tick(colony: dict, planet_yields: dict) -> dict[str, float]:
    """Net resource flow per tick (extraction - consumption)."""
    ext = extraction_per_tick(colony, planet_yields)
    con = consumption_per_tick(colony)
    return {k: round(ext.get(k, 0.0) - con.get(k, 0.0), 3) for k in ALL_RESOURCES}


def apply_ticks(colony: dict, planet_yields: dict, n_ticks: int) -> dict:
    """
    Apply n_ticks of economic activity.
    Returns a new colony dict — does not mutate the input.
    """
    if n_ticks <= 0:
        return colony

    colony     = copy.deepcopy(colony)
    stockpiles = colony['stockpiles']

    ext = extraction_per_tick(colony, planet_yields)
    con = consumption_per_tick(colony)

    for _ in range(n_ticks):
        # Extraction
        for k, v in ext.items():
            stockpiles[k] = round(stockpiles.get(k, 0.0) + v, 3)

        # Consumption — check food + water satisfaction for growth
        food_ok  = stockpiles.get('food',  0.0) >= con.get('food',  0.0)
        water_ok = stockpiles.get('water', 0.0) >= con.get('water', 0.0)

        for k, v in con.items():
            if v > 0:
                stockpiles[k] = max(0.0, round(stockpiles.get(k, 0.0) - v, 3))

        # Growth progress
        if food_ok and water_ok:
            colony['growthProgress'] = colony.get('growthProgress', 0) + 1
        else:
            colony['growthProgress'] = max(0, colony.get('growthProgress', 0) - 1)

        # Size increase
        if colony['growthProgress'] >= GROWTH_TICKS_NEEDED and colony['size'] < 5:
            colony['size']          += 1
            colony['growthProgress'] = 0
            # Recalculate rates for new size
            ext = extraction_per_tick(colony, planet_yields)
            con = consumption_per_tick(colony)

    colony['stockpiles'] = stockpiles
    return colony


def pending_ticks(last_ticked_at_iso: str) -> int:
    """Return the number of whole ticks elapsed since last_ticked_at_iso."""
    last = datetime.fromisoformat(last_ticked_at_iso.replace('Z', '+00:00'))
    now  = datetime.now(tz=timezone.utc)
    elapsed = (now - last).total_seconds()
    return max(0, int(elapsed / TICK_SECONDS))


# ── Development upgrade ───────────────────────────────────────────────────────

def can_upgrade_dev(colony: dict) -> tuple[bool, str]:
    """Return (True, '') if colony can upgrade, else (False, reason)."""
    dev = colony['developmentLevel']
    if dev >= 5:
        return False, 'already at maximum development level'
    cost = DEV_UPGRADE_COSTS.get(dev, {})
    for resource, amount in cost.items():
        if colony['stockpiles'].get(resource, 0.0) < amount:
            return False, f'insufficient {resource} (need {amount}, have {colony["stockpiles"].get(resource, 0.0):.1f})'
    return True, ''


def apply_upgrade_dev(colony: dict) -> dict:
    """Deduct upgrade costs and increment development level. Returns new dict."""
    colony = copy.deepcopy(colony)
    cost   = DEV_UPGRADE_COSTS[colony['developmentLevel']]
    for resource, amount in cost.items():
        colony['stockpiles'][resource] = round(
            colony['stockpiles'].get(resource, 0.0) - amount, 3
        )
    colony['developmentLevel'] += 1
    colony['growthProgress']    = 0
    return colony


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def size_name(colony: dict) -> str:
    return SIZE_NAMES[colony['size'] - 1]


def dev_name(colony: dict) -> str:
    return DEV_NAMES[colony['developmentLevel'] - 1]


def upgrade_cost(colony: dict) -> dict[str, float] | None:
    """Return upgrade cost dict, or None if already max level."""
    dev = colony['developmentLevel']
    return DEV_UPGRADE_COSTS.get(dev)
