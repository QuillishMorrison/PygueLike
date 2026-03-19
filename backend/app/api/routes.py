from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.websocket_manager import manager
from app.application.game_engine import PASSIVE_LIBRARY, GameEngine
from app.application.schemas import (
    DeckCardActionRequest,
    GameStateResponse,
    PassiveChoiceRequest,
    PlayCardRequest,
    RewardChoiceRequest,
    SessionRequest,
    StartGameRequest,
)
from app.infrastructure.database import get_db

router = APIRouter(prefix="/game", tags=["game"])


async def _broadcast_state(engine: GameEngine, session_id: str) -> GameStateResponse:
    state = engine.serialize(engine.load_full_session(session_id))
    await manager.broadcast(session_id, state.model_dump())
    return state


@router.post("/start", response_model=GameStateResponse)
async def start_game(payload: StartGameRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    session = engine.start_game(payload.seed)
    state = engine.serialize(session)
    await manager.broadcast(session.id, state.model_dump())
    return state


@router.get("/state", response_model=GameStateResponse)
def get_state(session_id: str, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        return engine.serialize(engine.load_full_session(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/play-card", response_model=GameStateResponse)
async def play_card(payload: PlayCardRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.play_card(payload.session_id, payload.card_instance_id, payload.target_enemy_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/end-turn", response_model=GameStateResponse)
async def end_turn(payload: SessionRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.end_turn(payload.session_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reward/choose-card", response_model=GameStateResponse)
async def choose_reward(payload: RewardChoiceRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.choose_reward_card(payload.session_id, payload.reward_card_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reward/remove-card", response_model=GameStateResponse)
async def remove_card(payload: DeckCardActionRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.remove_deck_card(payload.session_id, payload.card_instance_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reward/upgrade-card", response_model=GameStateResponse)
async def upgrade_card(payload: DeckCardActionRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.upgrade_deck_card(payload.session_id, payload.card_instance_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reward/choose-passive", response_model=GameStateResponse)
async def choose_passive(payload: PassiveChoiceRequest, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.choose_passive(payload.session_id, payload.passive_id)
        return await _broadcast_state(engine, session.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/passives")
def list_passives():
    return list(PASSIVE_LIBRARY.values())


@router.websocket("/ws")
async def game_ws(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    engine = GameEngine(db)
    try:
        session = engine.load_full_session(session_id)
    except ValueError:
        await websocket.close(code=4404)
        return

    await manager.connect(session_id, websocket)
    await websocket.send_json(engine.serialize(session).model_dump())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
