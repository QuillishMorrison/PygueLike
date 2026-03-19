from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self._connections:
            self._connections[session_id].discard(websocket)
            if not self._connections[session_id]:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict) -> None:
        dead_connections: list[WebSocket] = []
        for websocket in list(self._connections.get(session_id, set())):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead_connections.append(websocket)
        for websocket in dead_connections:
            self.disconnect(session_id, websocket)


manager = ConnectionManager()
