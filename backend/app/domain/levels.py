from __future__ import annotations

from app.domain.entities import LevelBlueprint


LEVEL_BLUEPRINTS: dict[str, LevelBlueprint] = {
    "web_app": LevelBlueprint(
        level_type="web_app",
        enemy_pool=["syntax_error", "timeout_error", "import_error", "key_error"],
        modifier_pool=[
            {"name": "Cold Start", "effect": "async_tax", "value": 1, "description": "Async cards cost +1 CPU."},
            {"name": "Hot Reload", "effect": "draw_bonus", "value": 1, "description": "Draw +1 card on turn 1."},
        ],
        difficulty_scale=1.0,
    ),
    "data_pipeline": LevelBlueprint(
        level_type="data_pipeline",
        enemy_pool=["memory_error", "type_error", "key_error", "timeout_error"],
        modifier_pool=[
            {"name": "Large Batch", "effect": "ram_tax", "value": 1, "description": "The first data card each turn costs +1 RAM."},
            {"name": "Cached Dataset", "effect": "starting_shield", "value": 1, "description": "Start with 1 shield."},
        ],
        difficulty_scale=1.1,
    ),
    "api_service": LevelBlueprint(
        level_type="api_service",
        enemy_pool=["timeout_error", "key_error", "import_error", "syntax_error"],
        modifier_pool=[
            {"name": "Rate Limit", "effect": "cpu_tax", "value": 1, "description": "The first card each turn costs +1 CPU."},
            {"name": "Observability", "effect": "reward_draw", "value": 1, "description": "Rewards include one upgraded card."},
        ],
        difficulty_scale=1.05,
    ),
    "game_server": LevelBlueprint(
        level_type="game_server",
        enemy_pool=["timeout_error", "memory_error", "recursion_error", "type_error"],
        modifier_pool=[
            {"name": "Tick Pressure", "effect": "enemy_damage", "value": 1, "description": "Enemies hit harder."},
            {"name": "Warm Cache", "effect": "passive_cache", "value": 1, "description": "Start with Caching."},
        ],
        difficulty_scale=1.2,
    ),
}
