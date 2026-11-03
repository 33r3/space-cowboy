"""Database tables (docs/foundation-design.md).

Times are integer ticks (whole minutes since 2000-01-01 UTC). Resource
amounts are integers in thousandths (1.5 food = 1500); see units.py.
"""
from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class World(Base):
    """One row: how far the ticker has advanced the universe."""
    __tablename__ = 'world'
    id:        Mapped[int] = mapped_column(Integer, primary_key=True)
    last_tick: Mapped[int] = mapped_column(Integer)


class Player(Base):
    __tablename__ = 'players'
    id:           Mapped[int] = mapped_column(Integer, primary_key=True)
    name:         Mapped[str] = mapped_column(String(64))
    created_tick: Mapped[int] = mapped_column(Integer)


class Planet(Base):
    """A planet someone has touched. Generated planet + overrides = the
    planet everyone on it lives with (homeworld fixes now, terraforming
    later)."""
    __tablename__ = 'planets'
    planet_id:    Mapped[str]  = mapped_column(String(64), primary_key=True)
    overrides:    Mapped[dict] = mapped_column(JSON, default=dict)
    updated_tick: Mapped[int]  = mapped_column(Integer)


class Colony(Base):
    __tablename__ = 'colonies'
    __table_args__ = (UniqueConstraint('planet_id', 'owner_id'),)
    id:               Mapped[int]  = mapped_column(Integer, primary_key=True)
    owner_id:         Mapped[int]  = mapped_column(ForeignKey('players.id'), index=True)
    planet_id:        Mapped[str]  = mapped_column(String(64), index=True)
    name:             Mapped[str]  = mapped_column(String(64))
    cx:               Mapped[int]  = mapped_column(Integer)
    cy:               Mapped[int]  = mapped_column(Integer)
    star_index:       Mapped[int]  = mapped_column(Integer)
    founded_tick:     Mapped[int]  = mapped_column(Integer)
    status:           Mapped[str]  = mapped_column(String(16))   # in_transit | active | abandoned
    size:             Mapped[int]  = mapped_column(Integer, default=1)
    dev_level:        Mapped[int]  = mapped_column(Integer, default=1)
    growth_progress:  Mapped[int]  = mapped_column(Integer, default=0)
    starvation_ticks: Mapped[int]  = mapped_column(Integer, default=0)
    is_homeworld:     Mapped[bool] = mapped_column(Boolean, default=False)
    over_cap_ticks:   Mapped[int]  = mapped_column(Integer, default=0, server_default='0')
    save_for_upgrade: Mapped[bool] = mapped_column(Boolean, default=False, server_default='0')

    stockpiles: Mapped[list['Stockpile']] = relationship(
        back_populates='colony', cascade='all, delete-orphan')


class Stockpile(Base):
    __tablename__ = 'stockpiles'
    colony_id: Mapped[int] = mapped_column(ForeignKey('colonies.id'), primary_key=True)
    resource:  Mapped[str] = mapped_column(String(32), primary_key=True)
    amount:    Mapped[int] = mapped_column(Integer, default=0)       # thousandths

    colony: Mapped[Colony] = relationship(back_populates='stockpiles')


class Ship(Base):
    """Anything travelling: colony ships, scouts, route freighters. `cargo`
    is what is actually aboard (thousandths), not what was ordered."""
    __tablename__ = 'ships'
    id:             Mapped[int]       = mapped_column(Integer, primary_key=True)
    uid:            Mapped[str]       = mapped_column(String(36), unique=True)  # API id
    owner_id:       Mapped[int]       = mapped_column(ForeignKey('players.id'), index=True)
    kind:           Mapped[str]       = mapped_column(String(16))   # colony_ship | scout | freighter | trader
    status:         Mapped[str]       = mapped_column(String(16))   # in_transit | arrived | idle (traders)
    from_colony_id: Mapped[int | None] = mapped_column(ForeignKey('colonies.id'))
    to_colony_id:   Mapped[int | None] = mapped_column(ForeignKey('colonies.id'))
    to_star_id:     Mapped[str | None] = mapped_column(String(64))
    departed_tick:  Mapped[int]       = mapped_column(Integer)
    arrival_tick:   Mapped[int]       = mapped_column(Integer)
    cargo:          Mapped[dict]      = mapped_column(JSON, default=dict)
    ship_class:     Mapped[str | None] = mapped_column(String(32))   # traders
    # traders: {'phase': 'pickup' | 'deliver', 'want': {...}, 'then': colony id,
    #           'retire': bool, 'trips': n, 'value': credits, 'last': {...}}
    trade:          Mapped[dict | None] = mapped_column(JSON)


class MarketSetting(Base):
    """An owner's override of one resource's market at one colony
    (generation/market.py; no row = automatic)."""
    __tablename__ = 'market_settings'
    colony_id: Mapped[int]        = mapped_column(ForeignKey('colonies.id'), primary_key=True)
    resource:  Mapped[str]        = mapped_column(String(32), primary_key=True)
    keep:      Mapped[int | None] = mapped_column(Integer)                  # thousandths; None = auto
    export:    Mapped[bool]       = mapped_column(Boolean, default=True)
    import_:   Mapped[bool]       = mapped_column('import', Boolean, default=True)


class Route(Base):
    __tablename__ = 'routes'
    id:          Mapped[str]       = mapped_column(String(16), primary_key=True)   # API routeId
    owner_id:    Mapped[int]       = mapped_column(ForeignKey('players.id'), index=True)
    name:        Mapped[str]       = mapped_column(String(128))
    ship_class:  Mapped[str]       = mapped_column(String(32))
    status:      Mapped[str]       = mapped_column(String(16))      # active | paused
    current_leg: Mapped[int]       = mapped_column(Integer, default=0)
    ship_id:     Mapped[int | None] = mapped_column(ForeignKey('ships.id'))

    legs: Mapped[list['RouteLeg']] = relationship(
        back_populates='route', cascade='all, delete-orphan', order_by='RouteLeg.idx')


class RouteLeg(Base):
    __tablename__ = 'route_legs'
    route_id:       Mapped[str]  = mapped_column(ForeignKey('routes.id'), primary_key=True)
    idx:            Mapped[int]  = mapped_column(Integer, primary_key=True)
    from_colony_id: Mapped[int]  = mapped_column(ForeignKey('colonies.id'))
    to_colony_id:   Mapped[int]  = mapped_column(ForeignKey('colonies.id'))
    cargo:          Mapped[dict] = mapped_column(JSON, default=dict)   # ordered, thousandths

    route: Mapped[Route] = relationship(back_populates='legs')


class Event(Base):
    """Something due at a tick: the ticker runs these, oldest first, before
    the economy."""
    __tablename__ = 'events'
    __table_args__ = (Index('ix_events_pending', 'processed_tick', 'due_tick'),)
    id:             Mapped[int]       = mapped_column(Integer, primary_key=True)
    due_tick:       Mapped[int]       = mapped_column(Integer)
    kind:           Mapped[str]       = mapped_column(String(32))   # ship_arrives
    ref_id:         Mapped[int]       = mapped_column(Integer)
    processed_tick: Mapped[int | None] = mapped_column(Integer)


class Notification(Base):
    __tablename__ = 'notifications'
    id:        Mapped[int]       = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int]       = mapped_column(ForeignKey('players.id'), index=True)
    tick:      Mapped[int]       = mapped_column(Integer)
    message:   Mapped[str]       = mapped_column(String(512))
    read:      Mapped[bool]      = mapped_column(Boolean, default=False)
    route_id:  Mapped[str | None] = mapped_column(ForeignKey('routes.id', ondelete='SET NULL'))


class TerraformProject(Base):
    """One player pushing one lever of one planet toward a target offset,
    paid every tick by one of their colonies (generation/terraform.py)."""
    __tablename__ = 'terraform_projects'
    id:           Mapped[int]       = mapped_column(Integer, primary_key=True)
    planet_id:    Mapped[str]       = mapped_column(String(64), index=True)
    owner_id:     Mapped[int]       = mapped_column(ForeignKey('players.id'), index=True)
    colony_id:    Mapped[int]       = mapped_column(ForeignKey('colonies.id'))   # who pays
    lever:        Mapped[str]       = mapped_column(String(16))   # temperature | pressure
    target:       Mapped[float]     = mapped_column(Float)        # offset to reach (K or atm)
    status:       Mapped[str]       = mapped_column(String(16))   # active | stalled | done | stopped
    started_tick: Mapped[int]       = mapped_column(Integer)
    ended_tick:   Mapped[int | None] = mapped_column(Integer)


class Survey(Base):
    """A star system whose planets a player knows in detail, because a
    probe surveyed it (vision.py; colonies' sensors aren't stored)."""
    __tablename__ = 'surveys'
    player_id:     Mapped[int] = mapped_column(ForeignKey('players.id'), primary_key=True)
    star_id:       Mapped[str] = mapped_column(String(32), primary_key=True)
    surveyed_tick: Mapped[int] = mapped_column(Integer)
