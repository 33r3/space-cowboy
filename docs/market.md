# Markets and free traders (v1, 2026-11-02)

Decisions (Brent): manual routes got tedious; trade should be organic and
market based. v1 covers one player's own empire, and the hauling is done
by the player's own freighters, put to "free trade" instead of a route.
Every colony uses smart defaults, which the player can override. Prices
are in credits from the start, so markets between players can plug in
later. There is no credit balance yet, because nothing would spend it.

## A colony's market

Each colony wants to keep a **target** of every resource:

- automatic: `RESERVE_TICKS` (60, an hour) of what it uses per tick
  (life support included), plus its next upgrade's cost if the colony is
  set to **save for the next upgrade** (off by default, so colonies don't
  all hoard metals at once);
- or a figure the owner sets ("keep 200 metals here").

Above the target is **surplus**, which traders may take away. Below it is a
**shortfall**, which traders may fill. Per resource, the owner can stop
goods going **out** (never export food from here) or coming **in**.

The local **price** is the base price × (target + 1) / (stock + 1), kept
between 0.25× and 4× the base:

| resource | base price (credits) |
|---|---|
| food, water | 1 |
| minerals | 2 |
| organic fuels | 3 |
| metals | 4 |
| chemical feedstocks | 6 |
| fusion fuel | 8 |
| radioactives | 12 |

A colony's market counts what traders already under way will bring or
take, so two traders don't chase the same shortfall.

## Free traders

Build one at any active colony from the Trade panel (T). It costs the
same as a route freighter of that class, and has the same capacity, speed
and range.

Each tick (after the economy), every idle trader takes the job that earns
the most **credits per tick of flying**. A job:

- carries goods from a colony with surplus to one that is short, only
  what the seller can spare and the buyer wants, biggest price gap first,
  filling the hold;
- is worth the price gap × amount, taken at the midpoint of the move;
- may start with an empty leg to the seller; every leg is within range.

When nobody is short, traders wait where they are, so goods never shuffle
in circles. A trader that arrives to find the surplus gone (a route or
the colony used it) waits there and picks again.

Scrapping a trader: an idle one goes at once; one under way finishes its
delivery first, so no cargo is lost. If a buyer is abandoned while goods
are on the way, the trader takes them back to the seller.

Fixed routes still work as before, and traders see the stock routes leave
behind.

## Cost

Measured on a deliberately dense case (50 colonies, all of which both
sell and buy most things, 20 traders), traders add ~65 ms per tick; at
20 colonies and 5 traders it's ~11 ms (economy included). That's fine
live, at one tick a minute, and for catching up a few hours. A
hundreds-of-players universe will want planning cut down: only replan
traders when their markets change, and vectorize the pair search.

## Not yet

- trading with other players (credits balance, buy/sell orders, taxes or
  fees), NPC merchants
- ship upkeep or fuel for traders
- auto-upgrade when a saving colony reaches its cost
- a "where's everything going" overview of the whole empire's market

# Outlook (2026-11-02)

The Outlook panel (E) projects at today's rates (`/api/outlook`,
generation/outlook.py). Each resource is in one of four states:

- **ok**: growing
- **tight**: growing, but by less than 10% of what is used, so one more
  colony or one bad turn tips it over
- **falling**: shrinking, shown as the time until the stock runs out
- **critical**: shrinking and gone within an hour

Only resources that something uses can be tight, falling or critical.

- **Civilization:** stocks, including goods aboard ships, and production,
  use and net across all active colonies. Colony ships under way add a
  **landed** column: the net once they arrive as outposts.
- **Room for outposts:** the net surplus divided by what a new outpost eats
  (0.25 food and 0.25 water per tick on a world that makes neither).
- **Colonies:** sorted most at risk first. Each shows every resource that
  isn't ok, with goods on the way and whether the rest of the empire can
  cover it: has spare (with a note when no trader or route will move it),
  barely covers it, or is short too.
- **Colonization preview:** shows the outpost's own net for food and water,
  and the empire's net before and after.
