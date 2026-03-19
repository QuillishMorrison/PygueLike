from __future__ import annotations

from app.domain.entities import EnemyBlueprint


ENEMY_BLUEPRINTS: dict[str, EnemyBlueprint] = {
    "syntax_error": EnemyBlueprint(
        enemy_id="syntax_error",
        name="SyntaxError",
        max_hp=22,
        description="Broken syntax that punishes control flow.",
        gimmick="Taxes control cards.",
    ),
    "type_error": EnemyBlueprint(
        enemy_id="type_error",
        name="TypeError",
        max_hp=24,
        description="Mismatched types that jam data cards.",
        gimmick="Disables one data card next turn.",
    ),
    "memory_error": EnemyBlueprint(
        enemy_id="memory_error",
        name="MemoryError",
        max_hp=28,
        description="Bloats memory and squeezes RAM.",
        gimmick="Reduces available RAM next turn.",
    ),
    "timeout_error": EnemyBlueprint(
        enemy_id="timeout_error",
        name="TimeoutError",
        max_hp=23,
        description="Slows execution and drains CPU.",
        gimmick="Reduces available CPU next turn.",
    ),
    "key_error": EnemyBlueprint(
        enemy_id="key_error",
        name="KeyError",
        max_hp=20,
        description="Picks apart unguarded state.",
        gimmick="Consumes shields before damaging.",
    ),
    "recursion_error": EnemyBlueprint(
        enemy_id="recursion_error",
        name="RecursionError",
        max_hp=26,
        description="Stacks pressure every turn.",
        gimmick="Damage scales with turn count.",
    ),
    "import_error": EnemyBlueprint(
        enemy_id="import_error",
        name="ImportError",
        max_hp=21,
        description="Breaks dependencies and async setup.",
        gimmick="Taxes async cards.",
    ),
}
