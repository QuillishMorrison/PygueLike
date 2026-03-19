from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.infrastructure.models import GameSessionModel


class GameSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, session_id: str) -> GameSessionModel | None:
        return (
            self.db.query(GameSessionModel)
            .options(
                joinedload(GameSessionModel.player_state),
                joinedload(GameSessionModel.level_state),
                joinedload(GameSessionModel.cards),
                joinedload(GameSessionModel.enemies),
            )
            .filter(GameSessionModel.id == session_id)
            .first()
        )

    def add(self, game_session: GameSessionModel) -> GameSessionModel:
        self.db.add(game_session)
        return game_session

    def save(self) -> None:
        self.db.commit()

    def refresh(self, game_session: GameSessionModel) -> None:
        self.db.refresh(game_session)
