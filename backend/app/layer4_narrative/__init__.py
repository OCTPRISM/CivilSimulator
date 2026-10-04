"""Layer 4 — Narrative Runtime.

The "Director": picks the next scene, decides which agents speak, generates
narration, and packages a `Page` (one Flipbook page) for Layer 5.
"""
from .director import Director
from .scene import Scene, Page, Beat
from .wake_briefing import WakeBriefing, compose_wake_briefing, collect_missed_events, compose_proxy_return_briefing

__all__ = [
    "Director", "Scene", "Page", "Beat",
    "WakeBriefing", "compose_wake_briefing", "collect_missed_events",
    "compose_proxy_return_briefing",
]
