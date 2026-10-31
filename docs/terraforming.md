# Terraforming (v1, 2026-10-31)

Decisions (Brent): habitability matters through life-support upkeep and a
size cap; a noticeable change takes days; colonists terraform their own
planet first, higher tech reaches other systems; v1 levers are
temperature and pressure (water, air chemistry and life come later).

## How a planet changes

A planet keeps its generated layers plus two offsets, `temperatureDeltaK`
and `pressureDeltaAtm` (planets.overrides.terraforming). From them
generation/terraform.py `derive_planet()` recomputes:

- air: pressure; the greenhouse effect scales with pressure (so thickening
  also warms); toxicity rises above 2 atm; breathable = N2/O2 at 0.5-2 atm
- water: ice, liquid and vapour from the new temperature (same rule as
  generation, `planet_factory.water_phase`)
- life: doesn't change stage yet, but food and the biosphere's organics
  fall as the climate leaves the one that life formed in, and drop to 20%
  without liquid water
- habitability and colony yields

With zero offsets it reproduces the generated planet exactly (checked on
6,973 planets), and generation itself is unchanged (hash of 14,994).

## What habitability costs (all colonies on the planet, every owner)

| habitability | max colony size |
|---|---|
| 65+ | Megacity (5) |
| 45-64 | City (4) |
| 25-44 | Town (3) |
| 10-24 | Settlement (2) |
| under 10 | Outpost (1) |

- Above the cap a colony loses one size per hour (SHRINK_TICKS = 60).
- Below 45, life support every tick: water 0.2 and metals 0.05 at
  habitability 0, scaled down linearly to nothing at 45, times the size
  multiplier. Unpaid, it counts as starving (the usual dev-loss rules).

## Projects

- Start: a colony of yours on the planet at Advanced (dev 3)+, or a
  Transcendent (dev 5) one within 300 Ly. One project per lever per
  player per planet. Everyone else with a colony there is notified.
- Target: an offset from the natural planet (±150 K, ±5 atm).
- Speed: 10 K or 0.2 atm per 3 days at dev 3; x1.5 at dev 4, x2 at dev 5.
- Cost per tick, from the paying colony:
  warming 0.05 chem feedstocks + 0.02 fusion fuel; cooling 0.08 metals +
  0.02 fusion; thickening 0.04 chem + 0.04 fusion; thinning 0.05 fusion +
  0.03 metals. Unpaid: the project stalls (owner told once) and resumes
  when paid.
- Opposing projects on one planet both pay and both pull; the net moves.
- A project ends when the offset reaches its target, when it's stopped,
  or when its colony can no longer run it.

All numbers are knobs at the top of generation/terraform.py.

## Not yet

- Adaptation tech (cuts life support for its owner): needs a tech system.
- Levers: water (import/drain), air chemistry (breathable/toxic), seeding
  life or blight.
- Balance: these costs and rates are first guesses, unplayed.
