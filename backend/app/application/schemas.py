from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StartGameRequest(BaseModel):
    seed: int | None = None


class PlayCardRequest(BaseModel):
    session_id: str
    card_instance_id: int
    target_enemy_id: int | None = None


class SessionRequest(BaseModel):
    session_id: str


class RewardChoiceRequest(BaseModel):
    session_id: str
    reward_card_id: str


class DeckCardActionRequest(BaseModel):
    session_id: str
    card_instance_id: int


class PassiveChoiceRequest(BaseModel):
    session_id: str
    passive_id: str


class CardView(BaseModel):
    instance_id: int
    card_id: str
    name: str
    card_type: str
    cpu_cost: int
    ram_cost: int
    snippet: str
    description: str
    synergy_tags: list[str]
    upgraded: bool
    disabled: bool
    zone: str
    requires_target: bool


class EnemyIntentView(BaseModel):
    label: str
    details: str


class EnemyView(BaseModel):
    instance_id: int
    enemy_id: str
    name: str
    hp: int
    max_hp: int
    intent: EnemyIntentView
    statuses: dict[str, Any] = Field(default_factory=dict)


class PlayerView(BaseModel):
    cpu: int
    max_cpu: int
    ram: int
    max_ram: int
    errors: int
    max_errors: int
    error_shield: int
    passives: list[dict[str, Any]]
    status_effects: dict[str, Any]


class LevelView(BaseModel):
    level_type: str
    modifiers: list[dict[str, Any]]
    enemy_pool: list[str]
    difficulty_scale: float


class RewardStateView(BaseModel):
    can_choose_card: bool = False
    reward_options: list[CardView] = Field(default_factory=list)
    can_remove_card: bool = False
    can_upgrade_card: bool = False
    can_choose_passive: bool = False
    passive_options: list[dict[str, Any]] = Field(default_factory=list)


class GameStateResponse(BaseModel):
    session_id: str
    phase: str
    status: str
    turn_number: int
    player: PlayerView
    hand: list[CardView]
    draw_pile: int
    discard_pile: int
    exhaust_pile: int
    deck_cards: list[CardView]
    enemies: list[EnemyView]
    level: LevelView
    log: list[str]
    reward_state: RewardStateView
