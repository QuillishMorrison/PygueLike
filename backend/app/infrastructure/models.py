from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class GameSessionModel(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    level_index: Mapped[int] = mapped_column(Integer, default=1)
    turn_number: Mapped[int] = mapped_column(Integer, default=1)
    phase: Mapped[str] = mapped_column(String(32), default="battle")
    status: Mapped[str] = mapped_column(String(32), default="active")
    log: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player_state: Mapped["PlayerStateModel"] = relationship(back_populates="game_session", uselist=False, cascade="all, delete-orphan")
    level_state: Mapped["LevelStateModel"] = relationship(back_populates="game_session", uselist=False, cascade="all, delete-orphan")
    cards: Mapped[list["CardStateModel"]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    enemies: Mapped[list["EnemyStateModel"]] = relationship(back_populates="game_session", cascade="all, delete-orphan")


class PlayerStateModel(Base):
    __tablename__ = "player_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), unique=True, index=True)
    max_cpu: Mapped[int] = mapped_column(Integer, default=3)
    current_cpu: Mapped[int] = mapped_column(Integer, default=3)
    max_ram: Mapped[int] = mapped_column(Integer, default=3)
    current_ram: Mapped[int] = mapped_column(Integer, default=3)
    max_errors: Mapped[int] = mapped_column(Integer, default=30)
    current_errors: Mapped[int] = mapped_column(Integer, default=30)
    status_effects: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    passives: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    reward_state: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    game_session: Mapped[GameSessionModel] = relationship(back_populates="player_state")


class CardStateModel(Base):
    __tablename__ = "card_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    card_id: Mapped[str] = mapped_column(String(64), nullable=False)
    zone: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    upgraded: Mapped[bool] = mapped_column(Boolean, default=False)
    temporary: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_until_turn: Mapped[int] = mapped_column(Integer, default=0)

    game_session: Mapped[GameSessionModel] = relationship(back_populates="cards")


class EnemyStateModel(Base):
    __tablename__ = "enemy_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    enemy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    max_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    current_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status_effects: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)
    intent: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), default=dict)

    game_session: Mapped[GameSessionModel] = relationship(back_populates="enemies")


class LevelStateModel(Base):
    __tablename__ = "level_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_session_id: Mapped[str] = mapped_column(ForeignKey("game_sessions.id"), unique=True, index=True)
    level_type: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1)
    difficulty_scale: Mapped[float] = mapped_column(Float, default=1.0)
    modifiers: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    enemy_pool: Mapped[list] = mapped_column(MutableList.as_mutable(JSONB), default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

    game_session: Mapped[GameSessionModel] = relationship(back_populates="level_state")
