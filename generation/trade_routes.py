"""
Trade route engine — pure functions, no I/O.

Routes move cargo between colonies on repeat cycles. Each route has one or
more legs; a ship departs each leg automatically once the previous leg
arrives.

Delta loading: when a leg arrives at a waypoint that is also the departure
point for the next leg, only the *difference* between inbound and outbound
cargo is transacted. Goods that pass through untouched never enter the
colony's stockpile, preventing the colony economy from temporarily absorbing
and re-releasing them.

If a route leg encounters an abandoned colony, the route is paused and an
event is appended to the route's `events` list.
"""
import copy
import math
from datetime import datetime, timezone

from generation.colony_economics import TICK_SECONDS

# ── Ship classes ───────────────────────────────────────────────────────────────

SCOUT_COST: dict[str, float] = {
    'minerals':     30.0,
    'metals':       20.0,
    'organicFuels':  5.0,
    'radioactives':  2.0,
    'fusionFuel':    5.0,
}

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


# ── Notifications ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _add_event(route: dict, colony, colony_id: str, event_type: str) -> None:
    """
    Append an event to route['events'] and pause the route.
    colony may be None if the planet no longer exists in colonies_data.
    """
    name = colony.get('name', colony_id) if colony else colony_id
    if event_type == 'abandoned_transit':
        msg = f'Ship stalled — {name} has been abandoned.'
    else:
        msg = f'Unexpected event at {name}.'

    route.setdefault('events', [])
    route['events'].append({
        'message':   msg,
        'timestamp': _now_iso(),
        'read':      False,
    })
    # Keep last 10
    route['events'] = route['events'][-10:]
    route['status'] = 'paused'


# ── Tick engine ────────────────────────────────────────────────────────────────

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

    Delta loading rule (contiguous legs):
      When leg[N].toPlanetId == leg[N+1].fromPlanetId the same colony acts as
      both destination and next departure point. Instead of fully unloading then
      fully reloading, compute the net delta per resource:
        net = inbound_cargo[res] - outbound_cargo[res]
        net > 0 → unload net units to colony
        net < 0 → load |net| units from colony (best-effort)
      Goods carried unchanged pass through without touching the stockpile.

    Non-contiguous legs:
      Full unload at destination, then full load from next leg's source
      (best-effort for both).

    Abandoned colonies:
      If a leg's destination (or next source) is abandoned, add an event to
      the route and pause it. A paused route does not advance.

    Returns (updated_routes_data, updated_colonies_data, changed).
    """
    routes_data   = copy.deepcopy(routes_data)
    colonies_data = copy.deepcopy(colonies_data)
    changed       = False

    # Build quick lookup: planetId → colony dict (mutable refs into list)
    col_index: dict[str, int] = {}
    for i, c in enumerate(colonies_data['colonies']):
        col_index[c['planetId']] = i

    def get_col(planet_id: str) -> dict | None:
        idx = col_index.get(planet_id)
        return colonies_data['colonies'][idx] if idx is not None else None

    now = datetime.now(tz=timezone.utc)

    for route in routes_data['routes']:
        # Only active routes advance
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

        while True:
            current_leg  = legs[leg_idx % len(legs)]
            to_id        = current_leg['toPlanetId']

            dist          = _leg_dist_cached(current_leg, get_col, config, density_field)
            transit_ticks = leg_transit_ticks(dist, ship_id)
            transit_secs  = transit_ticks * TICK_SECONDS

            if elapsed_s < transit_secs:
                break

            # ── Check destination ──────────────────────────────────────────
            to_col = get_col(to_id)
            if to_col is None or to_col.get('status') == 'abandoned':
                _add_event(route, to_col, to_id, 'abandoned_transit')
                changed = True
                break

            next_idx  = (leg_idx + 1) % len(legs)
            next_leg  = legs[next_idx]
            next_from_id = next_leg['fromPlanetId']

            if to_id == next_from_id:
                # ── Delta (atomic) transaction ─────────────────────────────
                curr    = current_leg.get('cargo', {})
                nxt     = next_leg.get('cargo', {})
                all_res = set(list(curr.keys()) + list(nxt.keys()))
                stocks  = to_col.setdefault('stockpiles', {})
                for res in all_res:
                    net = curr.get(res, 0) - nxt.get(res, 0)
                    if net > 0:
                        stocks[res] = round(stocks.get(res, 0.0) + net, 3)
                    elif net < 0:
                        available   = stocks.get(res, 0.0)
                        stocks[res] = round(available - min(available, -net), 3)
            else:
                # ── Non-contiguous: full unload, then full load at next source
                stocks = to_col.setdefault('stockpiles', {})
                for res, amt in current_leg.get('cargo', {}).items():
                    stocks[res] = round(stocks.get(res, 0.0) + amt, 3)

                next_col = get_col(next_from_id)
                if next_col is None or next_col.get('status') == 'abandoned':
                    _add_event(route, next_col, next_from_id, 'abandoned_transit')
                    # Advance leg index before breaking (ship is in transit)
                    leg_idx  = next_idx
                    departed = datetime.fromtimestamp(
                        departed.timestamp() + transit_secs, tz=timezone.utc
                    )
                    elapsed_s -= transit_secs
                    changed = True
                    break
                else:
                    src = next_col.setdefault('stockpiles', {})
                    for res, amt in next_leg.get('cargo', {}).items():
                        available = src.get(res, 0.0)
                        src[res]  = round(available - min(available, amt), 3)

            # ── Advance leg ────────────────────────────────────────────────
            leg_idx   = next_idx
            departed  = datetime.fromtimestamp(
                departed.timestamp() + transit_secs, tz=timezone.utc
            )
            elapsed_s -= transit_secs
            changed = True

        if changed:
            route['currentLegIndex'] = leg_idx
            route['legDepartedAt']   = departed.isoformat()

    return routes_data, colonies_data, changed


def _leg_dist_cached(leg: dict, get_col, config, density_field) -> float:
    """Compute distance for a single leg, returning inf if either colony is missing."""
    from_col = get_col(leg['fromPlanetId'])
    to_col   = get_col(leg['toPlanetId'])
    if from_col is None or to_col is None:
        return float('inf')
    return leg_distance(from_col, to_col, config, density_field)
