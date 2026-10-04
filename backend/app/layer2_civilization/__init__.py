"""Layer 2 — Civilization Engine.

Owns the *world state*: timeline, locations, factions, resources, rules.
Knows nothing about LLMs or UI. Pure data + tick.
"""
from .world import World, Location, Faction, WorldClock
from .seed import CivilizationSeed, load_seed, list_seeds
from .stats import WorldStats
from .background import WorldEvent, background_tick
from .finance import MarketState, FinanceShock
from .injections import InjectionQueue, ScheduledInjection, apply_injections
from .player_catalog import get_player_catalog, resolve_variant, spawn_player_from_variant

__all__ = [
    "World", "Location", "Faction", "WorldClock",
    "CivilizationSeed", "load_seed", "list_seeds",
    "WorldStats",
    "WorldEvent", "background_tick",
    "MarketState", "FinanceShock",
    "InjectionQueue", "ScheduledInjection", "apply_injections",
    "get_player_catalog", "resolve_variant", "spawn_player_from_variant",
]
