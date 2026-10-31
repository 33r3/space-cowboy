"""What a player knows. Every star is visible to everyone; the planets of a
system (type, habitability, yields, ...) only when the player knows that
system (Brent 2026-10-31: "some combination of greater proximity, probes,
or tech advances"):

  proximity + tech   a system within the sensor range of one of their
                     active colonies; the range grows with the colony's
                     development level (its own system is always known)
  probes             a system a probe of theirs has surveyed (stored in
                     surveys): the one it reached and those within
                     PROBE_SURVEY_RADIUS_LY of it

The server enforces it: unknown systems come back without planets, and
nobody can colonize or terraform a planet they don't know.
"""
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from generation.chunk_generator import chunks_in_bounds, generate_chunk

from .galaxy import Galaxy, split_star_id
from .models import Colony, Survey

SENSOR_RANGE_LY = {1: 0.0, 2: 40.0, 3: 100.0, 4: 200.0, 5: 400.0}
PROBE_SURVEY_RADIUS_LY = 60.0


def star_of_planet(planet_id: str) -> str:
    return planet_id.rsplit(':', 1)[0]


class Vision:
    """One player's knowledge, for one request or tick."""
    def __init__(self, session: Session, galaxy: Galaxy, player_id: int):
        self.s, self.galaxy, self.player_id = session, galaxy, player_id
        self._sensors = None
        self._surveyed = None

    def _load(self):
        if self._sensors is None:
            cols = self.s.scalars(select(Colony).where(Colony.owner_id == self.player_id,
                                                       Colony.status == 'active')).all()
            self._sensors = []
            for c in cols:
                pos = self.galaxy.star_pos(c.cx, c.cy, c.star_index)
                if pos:
                    self._sensors.append((f'{c.cx},{c.cy}:{c.star_index}', pos,
                                          SENSOR_RANGE_LY.get(c.dev_level, 0.0)))
            self._surveyed = set(self.s.scalars(
                select(Survey.star_id).where(Survey.player_id == self.player_id)))

    def knows(self, star_id: str) -> bool:
        self._load()
        if star_id in self._surveyed:
            return True
        try:
            pos = self.galaxy.star_pos(*split_star_id(star_id))
        except ValueError:
            return False
        if pos is None:
            return False
        for own_star, spos, reach in self._sensors:
            if own_star == star_id or math.hypot(pos[0] - spos[0], pos[1] - spos[1]) <= reach:
                return True
        return False

    def known_star_ids(self) -> set[str]:
        """Every system the player knows: surveyed ones plus those inside
        their colonies' sensor ranges (at most 400 Ly each, so small)."""
        self._load()
        known = set(self._surveyed)
        for own_star, (x, y), reach in self._sensors:
            known.add(own_star)
            if reach > 0:
                known.update(stars_near(self.galaxy, x, y, reach))
        return known

    def knows_planet(self, planet_id: str) -> bool:
        return self.knows(star_of_planet(planet_id))


def stars_near(galaxy: Galaxy, x: float, y: float, radius: float) -> list[str]:
    cs = galaxy.config.chunk_size_ly
    out = []
    for cx, cy in chunks_in_bounds(x - radius, y - radius, x + radius, y + radius, cs):
        for star in generate_chunk(cx, cy, galaxy.config, galaxy.density_field):
            if math.hypot(star['worldX'] - x, star['worldY'] - y) <= radius:
                out.append(star['id'])
    return out


def survey_around(session: Session, galaxy: Galaxy, player_id: int, star_id: str,
                  tick: int) -> list[str]:
    """A probe arrived at star_id: its owner now knows it and its
    neighbours. Returns the newly surveyed star ids."""
    pos = galaxy.star_pos(*split_star_id(star_id))
    if pos is None:
        return []
    known = set(session.scalars(select(Survey.star_id).where(Survey.player_id == player_id)))
    new = [sid for sid in stars_near(galaxy, *pos, PROBE_SURVEY_RADIUS_LY) if sid not in known]
    if star_id not in known and star_id not in new:
        new.append(star_id)
    session.add_all(Survey(player_id=player_id, star_id=sid, surveyed_tick=tick) for sid in new)
    return new
