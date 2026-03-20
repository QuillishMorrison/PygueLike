from __future__ import annotations

from app.domain.entities import LevelBlueprint


LEVEL_BLUEPRINTS: dict[str, LevelBlueprint] = {
    "web_app": LevelBlueprint(
        level_type="web_app",
        enemy_pool=["syntax_error", "timeout_error", "import_error", "key_error"],
        modifier_pool=[
            {"name": "Холодный старт", "effect": "async_tax", "value": 1, "description": "Async-карты стоят на 1 CPU больше."},
            {"name": "Горячая перезагрузка", "effect": "draw_bonus", "value": 1, "description": "В 1-й ход добирается на 1 карту больше."},
        ],
        difficulty_scale=1.0,
    ),
    "data_pipeline": LevelBlueprint(
        level_type="data_pipeline",
        enemy_pool=["memory_error", "type_error", "key_error", "timeout_error"],
        modifier_pool=[
            {"name": "Большой батч", "effect": "ram_tax", "value": 1, "description": "Первая data-карта каждого хода стоит на 1 RAM больше."},
            {"name": "Кэшированный датасет", "effect": "starting_shield", "value": 1, "description": "Начните бой с 1 щитом."},
        ],
        difficulty_scale=1.1,
    ),
    "api_service": LevelBlueprint(
        level_type="api_service",
        enemy_pool=["timeout_error", "key_error", "import_error", "syntax_error"],
        modifier_pool=[
            {"name": "Лимит запросов", "effect": "cpu_tax", "value": 1, "description": "Первая карта каждого хода стоит на 1 CPU больше."},
            {"name": "Наблюдаемость", "effect": "reward_draw", "value": 1, "description": "Среди наград может попасться улучшенная карта."},
        ],
        difficulty_scale=1.05,
    ),
    "game_server": LevelBlueprint(
        level_type="game_server",
        enemy_pool=["timeout_error", "memory_error", "recursion_error", "type_error"],
        modifier_pool=[
            {"name": "Давление тиков", "effect": "enemy_damage", "value": 1, "description": "Враги бьют сильнее."},
            {"name": "Теплый кэш", "effect": "passive_cache", "value": 1, "description": "Начните с пассивки Кэширование."},
        ],
        difficulty_scale=1.2,
    ),
}
