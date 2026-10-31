# Foundation design: database, owners, event queue

Status: steps 1-4 built 2026-10-31 (tables, importer, ticker, FastAPI, owner
checks). The Flask app.py was removed 2026-10-31 (surveys made the servers differ).

Target (Brent): 20-500 players per universe on a hosted server, persistent
real-time (the universe runs while you're offline), 1 tick = 1 real minute.

## What stays the same

- The galaxy is generated from the seed, chunk by chunk. Stars and planets
  are never stored; only what players change is.
- generation/ (galaxy, stars, planets, economy rules, ship classes) keeps
  its pure functions. The economy rules move unchanged.
- The browser client and the JSON shapes the API returns. The FastAPI
  routes answer with the same fields, so static/js keeps working.

## Time

- Game time is an integer **tick** (whole minutes since 2000-01-01 UTC,
  as `_current_tick()` already does for scouts). Every stored time is a
  tick, not an ISO string.
- One background **ticker** owns time. Each tick, in this order:
  1. events due at this tick, oldest first (arrivals, route legs, ...);
  2. the economy for every active colony (one `apply_ticks(…, 1)` each).
  If the server was down, it replays the missed ticks in order.
- Player actions (colonize, upgrade, create route) run at the current tick
  against state the ticker has already brought up to date.
- Cost check: 500 players x ~50 colonies = 25,000 colonies a minute; the
  economy step is microseconds per colony, so well under a second.

Why tick everyone instead of today's catch-up-when-read: once players
interact, every change has to happen in one order. If your fleet arrives
at tick 100 and mine at 98, mine fights first, no matter who loads the
page first. It also fixes the "arrived while nobody was looking" bug.

## Tables

All amounts of resources are stored as integers in thousandths
(1.5 food = 1500), to stop float drift in a shared economy. The API still
shows decimals.

```
players        id, name, created_tick, homeworld_colony_id
               (accounts/logins come in the multiplayer step; a player row
               is enough for ownership now)

colonies       id, owner_id -> players, planet_id, name,
               UNIQUE (planet_id, owner_id): players can share a planet,
               one colony each
               cx, cy, star_index, founded_tick, status
               (in_transit | active | abandoned), size, dev_level,
               growth_progress, starvation_ticks, is_homeworld
               (yields are no longer frozen at founding: they come from
               the planet's current state, see planets)

stockpiles     colony_id, resource, amount        PK (colony_id, resource)

ships_in_transit
               id, owner_id, kind (colony_ship | scout | freighter),
               from_colony_id, to (colony or star id),
               departed_tick, arrival_tick, cargo (JSON, what is actually
               aboard)

routes         id, owner_id, name, ship_class, status (active | paused),
               current_leg, ship_id -> ships_in_transit
route_legs     route_id, idx, from_colony_id, to_colony_id, cargo (JSON:
               what to load)                      PK (route_id, idx)

events         id, due_tick, kind, ref_id, processed_tick
               index on (processed_tick IS NULL, due_tick)
               kinds now: colony_arrives, scout_arrives, leg_arrives

notifications  id, player_id, tick, message, read
               (replaces route['events'])

planets        planet_id PK, overrides (JSON), updated_tick
               Shared state of a planet that someone has touched: the
               generated planet + overrides = the planet everyone on it
               lives with. Homeworld fixes now (replaces
               data/homeworld.json); terraforming later.
terraform_projects
               id, planet_id, owner_id, target (JSON: e.g. pressure +0.2,
               temperature -15 K), rate, started_tick, status
               Several players can run projects on one planet, including
               opposing ones; their effects add up each tick. Built in
               the terraforming step, but the planet state is shared from
               the start so that step needs no redesign.

explored       player_id, chunk_key               PK (player_id, chunk_key)
               (fog of war moves from localStorage to the server)
```

Bug fixes that fall out of the schema:
- Freighters carry `cargo` = what was actually loaded, so a route can't
  deliver more than it took (strict xfail test today).
- Arrivals are events at their own tick (strict xfail test today).
- GET /api/colonies today rewrites the whole save and silently drops any
  colony whose planet it can't regenerate; with rows, reads never write.

## Owners and anti-cheat

- Every colony, ship, route and notification has an owner. Every action
  checks the caller owns what it spends from. Until logins exist, the
  caller is player 1.
- The server never trusts the client for amounts, positions, distances or
  timing; it already recomputes these, and the tests keep it that way.
- Later, for multiplayer: the galaxy seed should stay secret on the
  server (with the seed anyone can compute every planet), and the server
  should only send each player the chunks and colonies they can see.

## Stack

- FastAPI + Uvicorn (async; WebSockets for live updates later).
- SQLAlchemy 2 + Alembic migrations. SQLite in development and tests,
  Postgres on the hosted server; same code. A local Postgres test run
  before hosting.
- The ticker runs inside the server process for now (one asyncio task,
  one writer); it can become its own process when hosting.
- A one-time import turns an existing colonies.json/routes.json/scouts.json
  into player 1's rows.

## Order of work

1. DB models + migration + import script; repository functions the
   routes call. Tests: the import round-trips, ticker order.
2. Ticker + event queue; economy runs per tick. Flip the two xfails.
3. Move routes Flask -> FastAPI one group at a time (config/chunks/system,
   colonies, routes, scouts), the API tests running against both until
   Flask is removed.
4. Owners checks on every action (player 1 for now).

## Shared planets (Brent, 2026-10-31)

Players can share a planet, peacefully or not, and terraforming can be a
weapon: make a world hostile to a rival who lacks the tech to adapt or the
force to stop it. What that needs from the foundation:

- One colony per player per planet; the planet's state is shared.
- Yields and upkeep follow the planet's *current* habitability, recomputed
  when it changes, so a terraformed planet hurts (or helps) everyone on it.
- Per-player adaptation tech later offsets bad habitability for its owner
  only (a sealed-habitat player shrugs off a toxic sky; a rival starves).
- Notifications tell everyone on a planet when someone starts a project
  there, so it can be contested.

Not decided (game design, for later steps):
- Sharing deposits: how colonies on one planet split its resources
  (by colony size x dev? first come? each gets its own share?).
- Diplomacy: whether "peaceful" sharing is a formal agreement in the game.

## Where new players start (Brent, 2026-10-31: a decent-sized buffer)

Homeworld-grade planets (Terran, habitability >= 80) are not rare:
sampling 469 chunks found ~0.5 per 200 Ly chunk, ~1.5 near the core and
~0.1 at the rim, roughly 100,000 in the galaxy. Today's spiral search
would put every player on the same first one (it's in chunk 0,0), so
spacing has to be enforced:

- Each new player gets the nearest homeworld-grade planet to the core
  that is at least HOMEWORLD_BUFFER_LY from every other homeworld.
- HOMEWORLD_BUFFER_LY = 1500 to start (a tuning knob): more than the
  best colonization range (1200 Ly at dev 5), so nobody can settle next
  door from the start; scouts (up to 1800 Ly) can find neighbours
  mid-game. 500 players at that spacing use ~11% of the galaxy's area.
- Filling outward from the core means later players land farther out,
  where planets are sparser; whether to compensate is a later balance
  question.

## Measured (2026-10-31, SQLite, one core)

One tick of the economy for 25,000 colonies (500 players x 50) takes
about 2 s of the 60 s tick, after reading and writing in bulk; the
per-object version took ~7 s. Yields are cached per planet. Still to
watch: generation/chunk_generator.py's chunk cache never evicts.
