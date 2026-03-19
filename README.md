# PygueLike

A playable MVP of a turn-based roguelike deckbuilder where cards are Python constructs and enemies are Python runtime errors.

## Project Structure

```text
backend/
  app/
    api/
      routes.py
      websocket_manager.py
    application/
      game_engine.py
      schemas.py
    domain/
      cards.py
      enemies.py
      entities.py
      levels.py
    infrastructure/
      database.py
      models.py
      repositories.py
    main.py
  requirements.txt
  .env.example
frontend/
  index.html
  styles.css
  app.js
docker-compose.yml
README.md
```

## Features

- FastAPI backend with REST and WebSocket state updates
- PostgreSQL persistence for sessions, player state, cards, enemies, and levels
- Clean architecture split into `domain`, `application`, `infrastructure`, and `api`
- 28 cards across control, data, async, and error-handling archetypes
- 7 error enemies with distinct turn behavior
- Seed-based procedural level selection and modifiers
- Reward phase with card draft, deck removal, deck upgrade, and passive pickup
- Vanilla HTML/CSS/JS frontend with Python-code-styled cards

## Database Setup

1. Start PostgreSQL:

   ```bash
   docker compose up -d
   ```

2. Copy the backend environment file:

   ```bash
   copy backend\.env.example backend\.env
   ```

3. The backend creates tables automatically on startup.

## Run Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`

## Run Frontend

Serve the `frontend` folder with a static server:

```bash
cd frontend
python -m http.server 8080
```

Frontend URL: `http://localhost:8080`

## API Endpoints

- `POST /game/start`
- `GET /game/state?session_id=...`
- `POST /game/play-card`
- `POST /game/end-turn`
- `POST /game/reward/choose-card`
- `POST /game/reward/remove-card`
- `POST /game/reward/upgrade-card`
- `POST /game/reward/choose-passive`
- `GET /game/passives`
- `WS /game/ws?session_id=...`

## Gameplay Flow

1. Start a run from the frontend.
2. Click an enemy to target it.
3. Play cards from hand while CPU and RAM allow.
4. End the turn and let Python errors retaliate.
5. Clear the battle to enter the reward phase.
6. Draft a new card, optionally remove one, optionally upgrade one, and pick a passive.
