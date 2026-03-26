"""
Trade route engine — pure functions, no I/O.

Routes move cargo between colonies on repeat cycles. Each route has one or
more legs; a ship departs each leg automatically once the previous leg
arrives. Cargo is best-effort: if the source can't fill the full amount,
it ships what's available.
"""
import copy
import math
from datetime import datetime, timezone

from generation.colony_economics import TICK_SECONDS

# ── Ship classes ───────────────────────────────────────────────────────────────

SHIP_CLASSES: dict[str, dict] = {
    'freighter_mk1': {
        'id':             'freighter_mk1',
        'name':           'Freighter Mk.I',
        'devRequired':    2,
        'capacity':       20,
        'speedLyPerTick': 100,
        'maxRangeLy':     300,
        'setupCost': {
            'minerals':     30,
            'metals':       20,
            'organicFuels': 5,
            'radioactives': 2,
            'fusionFuel':   5,
        },
    },
    'freighter_mk2': {
        'id':             'freighter_mk2',
        'name':           'Freighter Mk.II',
        'devRequired':    3,
        'capacity':       50,
        'speedLyPerTick': 200,
        'maxRangeLy':     600,
        'setupCost': {
            'minerals':        80,
            'metals':          50,
            'organicFuels':    20,
            'chemFeedstocks':  10,
            'radioactives':    5,
            'fusionFuel':      10,
        },
    },
    'heavy_hauler': {
        'id':             'heavy_hauler',
        'name':           'Heavy Hauler',
        'devRequired':    4,
        'capacity':       150,
        'speedLyPerTick': 150,
        'maxRangeLy':     600,
        'setupCost': {
            'minerals':        200,
            'metals':          120,
            'organicFuels':    30,
            'chemFeedstocks':  40,
            'radioactives':    15,
            'fusionFuel':      20,
        },
    },
    'jump_freighter': {
        'id':             'jump_freighter',
        'name':           'Jump Freighter',
        'devRequired':    5,
        'capacity':       100,
        'speedLyPerTick': 500,
        'maxRangeLy':     1200,
        'setupCost': {
            'minerals':        150,
            'metals':          200,
            'organicFuels':    50,
            'chemFeedstocks':  80,
            'radioactives':    30,
            'fusionFuel':      50,
        },
    },
}


def available_ship_classes(dev_level: int) -> list[dict]:
    """Ship classes available to a colony at the given development level."""
    return [
        sc for sc in SHIP_CLASSES.values()
        if sc['devRequired'] <= dev_level
    ]


# ── Distance / transit helpers ─────────────────────────────────────────────────

def _star_pos(col: dict, config, density_field) -> tuple[float, float] | None:
    """Return (worldX, worldY) for a colony's star."""
    from generation.chunk_generator import regenerate_star
    star = regenerate_star(col['cx'], col['cy'], col['starIndex'], config, density_field)
    return (star['worldX'], star['worldY']) if star else None


def leg_distance(from_col: dict, to_col: dict, config, density_field) -> float:
    """Euclidean light-year distance between two colonies' stars."""
    a = _star_pos(from_col, config, density_field)
    b = _star_pos(to_col, config, density_field)
    if a is None or b is None:
        return float('inf')
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def leg_transit_ticks(distance_ly: float, ship_class_id: str) -> int:
    """Whole ticks needed to complete one leg (minimum 1)."""
    speed = SHIP_CLASSES[ship_class_id]['speedLyPerTick']
    return max(1, math.ceil(distance_ly / speed))


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_route(
    legs: list[dict],
    ship_class_id: str,
    colonies_by_id: dict,
    config,
    density_field,
) -> tuple[bool, str]:
    """
    Validate all legs of a prospective route.
    Returns (True, '') or (False, reason string).
    """
    if ship_class_id not in SHIP_CLASSES:
        return False, f'unknown ship class: {ship_class_id}'

    ship = SHIP_CLASSES[ship_class_id]

    if not legs:
        return False, 'route must have at least one leg'

    for i, leg in enumerate(legs):
        from_id = leg.get('fromPlanetId')
        to_id   = leg.get('toPlanetId')

        if from_id not in colonies_by_id:
            return False, f'leg {i}: fromPlanetId {from_id!r} is not a known colony'
        if to_id not in colonies_by_id:
            return False, f'leg {i}: toPlanetId {to_id!r} is not a known colony'
        if from_id == to_id:
            return False, f'leg {i}: source and destination are the same colony'

        from_col = colonies_by_id[from_id]
        to_col   = colonies_by_id[to_id]
        dist = leg_distance(from_col, to_col, config, density_field)

        if dist > ship['maxRangeLy']:
            return False, (
                f'leg {i}: distance {dist:.1f} Ly exceeds ship max range '
                f'{ship["maxRangeLy"]} Ly'
            )

        cargo = leg.get('cargo', {})
        total = sum(cargo.values())
        if total > ship['capacity']:
            return False, (
                f'leg {i}: cargo total {total} exceeds ship capacity '
                f'{ship["capacity"]}'
            )

    return True, ''


# ── Tick engine ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))


def tick_routes(
    routes_data: dict,
    colonies_data: dict,
    config,
    density_field,
) -> tuple[dict, dict, bool]:
    """
    Advance all active routes by processing completed legs.

    For each active route:
      - Compute elapsed seconds since legDepartedAt
      - While elapsed >= transit_ticks * TICK_SECONDS:
          1. Deliver this leg's cargo to the destination (best-effort)
          2. Advance to next leg (wraps around)
          3. Bump legDepartedAt by transit_secs (no drift)
          4. Deduct next leg's cargo from its source (best-effort)

    Returns (updated_routes_data, updated_colonies_data, changed).
    """
    routes_data   = copy.deepcopy(routes_data)
    colonies_data = copy.deepcopy(colonies_data)
    changed       = False

    # Build quick lookup: planetId → colony dict (mutable, index into list)
    col_index: dict[str, int] = {}
    for i, c in enumerate(colonies_data['colonies']):
        col_index[c['planetId']] = i

    def get_col(planet_id: str) -> dict | None:
        idx = col_index.get(planet_id)
        return colonies_data['colonies'][idx] if idx is not None else None

    now = datetime.now(tz=timezone.utc)

    for route in routes_data['routes']:
        if route.get('status') != 'active':
            continue

        ship_id = route['shipClass']
        if ship_id not in SHIP_CLASSES:
            continue

        legs = route['legs']
        if not legs:
            continue

        leg_idx   = route['currentLegIndex']
        departed  = _parse_iso(route['legDepartedAt'])
        elapsed_s = (now - departed).total_seconds()

        # Process as many completed legs as time allows
        while True:
            leg     = legs[leg_idx % len(legs)]
            from_id = leg['fromPlanetId']
            to_id   = leg['toPlanetId']

            from_col = get_col(from_id)
            to_col   = get_col(to_id)
            if from_col is None or to_col is None:
                break

            dist          = leg_distance(from_col, to_col, config, density_field)
            transit_ticks = leg_transit_ticks(dist, ship_id)
            transit_secs  = transit_ticks * TICK_SECONDS

            if elapsed_s < transit_secs:
                break

            # ── Deliver cargo to destination ───────────────────────────────
            cargo = leg.get('cargo', {})
            dest_stocks = to_col.setdefault('stockpiles', {})
            for resource, amount in cargo.items():
                dest_stocks[resource] = round(
                    dest_stocks.get(resource, 0.0) + amount, 3
                )

            # ── Advance to next leg ────────────────────────────────────────
            leg_idx = (leg_idx + 1) % len(legs)
            departed = datetime.fromtimestamp(
                departed.timestamp() + transit_secs, tz=timezone.utc
            )
            elapsed_s -= transit_secs
            changed = True

            # ── Deduct next leg cargo from its source (best-effort) ────────
            next_leg      = legs[leg_idx]
            next_from_col = get_col(next_leg['fromPlanetId'])
            if next_from_col is not None:
                src_stocks = next_from_col.setdefault('stockpiles', {})
                for resource, amount in next_leg.get('cargo', {}).items():
                    available = src_stocks.get(resource, 0.0)
                    deduct    = min(available, amount)
                    src_stocks[resource] = round(available - deduct, 3)

        if changed:
            route['currentLegIndex'] = leg_idx
            route['legDepartedAt']   = departed.isoformat()

    return routes_data, colonies_data, changed
