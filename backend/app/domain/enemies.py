from __future__ import annotations

from app.domain.entities import EnemyBlueprint


ENEMY_BLUEPRINTS: dict[str, EnemyBlueprint] = {
    "syntax_error": EnemyBlueprint(
        enemy_id="syntax_error",
        name="SyntaxError",
        max_hp=22,
        description="Ломает синтаксис и наказывает карты управления.",
        gimmick="Повышает стоимость control-карт.",
    ),
    "type_error": EnemyBlueprint(
        enemy_id="type_error",
        name="TypeError",
        max_hp=24,
        description="Несовместимые типы, которые клинят data-карты.",
        gimmick="Отключает одну data-карту на следующий ход.",
    ),
    "memory_error": EnemyBlueprint(
        enemy_id="memory_error",
        name="MemoryError",
        max_hp=28,
        description="Раздувает память и душит RAM.",
        gimmick="Уменьшает доступную RAM на следующий ход.",
    ),
    "timeout_error": EnemyBlueprint(
        enemy_id="timeout_error",
        name="TimeoutError",
        max_hp=23,
        description="Замедляет выполнение и высасывает CPU.",
        gimmick="Уменьшает доступный CPU на следующий ход.",
    ),
    "key_error": EnemyBlueprint(
        enemy_id="key_error",
        name="KeyError",
        max_hp=20,
        description="Разбирает незащищенное состояние по ключам.",
        gimmick="Сначала сжигает щиты, потом наносит урон.",
    ),
    "recursion_error": EnemyBlueprint(
        enemy_id="recursion_error",
        name="RecursionError",
        max_hp=26,
        description="Наращивает давление с каждым ходом.",
        gimmick="Урон растет вместе с номером хода.",
    ),
    "import_error": EnemyBlueprint(
        enemy_id="import_error",
        name="ImportError",
        max_hp=21,
        description="Ломает зависимости и async-подготовку.",
        gimmick="Повышает стоимость async-карт.",
    ),
}
