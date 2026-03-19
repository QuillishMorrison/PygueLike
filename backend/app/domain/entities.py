from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CardType(str, Enum):
    CONTROL = "control"
    DATA = "data"
    ASYNC = "async"
    ERROR_HANDLING = "error-handling"


class CardZone(str, Enum):
    DECK = "deck"
    HAND = "hand"
    DISCARD = "discard"
    EXHAUST = "exhaust"


class SessionPhase(str, Enum):
    BATTLE = "battle"
    REWARD = "reward"
    GAME_OVER = "game_over"
    VICTORY = "victory"


@dataclass(slots=True)
class CardDefinition:
    card_id: str
    name: str
    card_type: CardType
    cpu_cost: int
    ram_cost: int
    snippet: str
    description: str
    synergy_tags: list[str] = field(default_factory=list)
    exhausts: bool = False
    requires_target: bool = True


@dataclass(slots=True)
class EnemyBlueprint:
    enemy_id: str
    name: str
    max_hp: int
    description: str
    gimmick: str


@dataclass(slots=True)
class LevelBlueprint:
    level_type: str
    enemy_pool: list[str]
    modifier_pool: list[dict]
    difficulty_scale: float
