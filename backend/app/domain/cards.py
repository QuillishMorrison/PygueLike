from __future__ import annotations

from app.domain.entities import CardDefinition, CardType


def _card(
    card_id: str,
    name: str,
    card_type: CardType,
    cpu_cost: int,
    ram_cost: int,
    snippet: str,
    description: str,
    tags: list[str] | None = None,
    *,
    exhausts: bool = False,
    requires_target: bool = True,
) -> CardDefinition:
    return CardDefinition(
        card_id=card_id,
        name=name,
        card_type=card_type,
        cpu_cost=cpu_cost,
        ram_cost=ram_cost,
        snippet=snippet,
        description=description,
        synergy_tags=tags or [],
        exhausts=exhausts,
        requires_target=requires_target,
    )


CARD_LIBRARY: dict[str, CardDefinition] = {
    "print_debug": _card("print_debug", "print()", CardType.DATA, 1, 0, "print(target)", "Наносит 4 урона.", ["starter"]),
    "assign_var": _card("assign_var", "Присваивание", CardType.DATA, 0, 0, "x = value", "Дает 1 CPU.", ["starter"], requires_target=False),
    "append_list": _card("append_list", "append()", CardType.DATA, 1, 1, "items.append(x)", "Наносит 5 урона и добирает 1 карту.", ["list"]),
    "if_statement": _card("if_statement", "if", CardType.CONTROL, 1, 0, "if condition:\n    branch()", "Наносит 8 урона ослабленной цели, иначе 4.", ["conditional"]),
    "for_loop": _card("for_loop", "цикл for", CardType.CONTROL, 1, 0, "for _ in range(2):\n    next()", "Повторяет следующую сыгранную карту 1 раз.", ["combo"], requires_target=False),
    "while_loop": _card("while_loop", "цикл while", CardType.CONTROL, 1, 1, "while alive:\n    attack()", "Повторяет следующую карту дважды, затем вы теряете 1 Ошибку.", ["combo"], requires_target=False),
    "lambda_func": _card("lambda_func", "lambda", CardType.CONTROL, 0, 0, "boost = lambda x: x + 3", "Следующая сыгранная карта получает +3 силы.", ["combo"], exhausts=True, requires_target=False),
    "try_except": _card("try_except", "try/except", CardType.ERROR_HANDLING, 1, 0, "try:\n    risky()\nexcept Exception:\n    pass", "Блокирует следующий эффект ошибки врага.", ["defense"], requires_target=False),
    "finally_block": _card("finally_block", "finally", CardType.ERROR_HANDLING, 1, 0, "finally:\n    cleanup()", "Лечит 3 Ошибки и дает 1 RAM на следующий ход.", ["recovery"], requires_target=False),
    "list_comprehension": _card("list_comprehension", "генератор списка", CardType.DATA, 2, 1, "[hit(e) for e in enemies]", "Наносит 4 урона всем врагам.", ["aoe"]),
    "dict_lookup": _card("dict_lookup", "поиск в dict", CardType.DATA, 1, 0, "value = data[key]", "Наносит 4 урона и накладывает Ослабление на 1 ход.", ["debuff"]),
    "set_default": _card("set_default", "setdefault", CardType.ERROR_HANDLING, 1, 0, "cache.setdefault(key, value)", "Дает 2 щита Ошибок и добирает 1 карту.", ["shield"], requires_target=False),
    "import_module": _card("import_module", "import", CardType.DATA, 1, 0, "import tools", "Дает 1 CPU и 1 RAM.", ["setup"], requires_target=False),
    "class_def": _card("class_def", "class", CardType.CONTROL, 2, 1, "class Hero:\n    pass", "Дает 2 щита Ошибок и наносит 3 урона всем врагам.", ["aoe"], requires_target=False),
    "decorator": _card("decorator", "декоратор", CardType.CONTROL, 1, 0, "@optimize", "Следующая карта стоит на 1 CPU меньше и становится сильнее.", ["combo"], requires_target=False),
    "generator_expr": _card("generator_expr", "генератор", CardType.ASYNC, 1, 0, "(x for x in xs)", "Добирает 2 карты.", ["draw"], requires_target=False),
    "yield_value": _card("yield_value", "yield", CardType.ASYNC, 1, 0, "yield result", "Дает 2 CPU на следующий ход.", ["tempo"], requires_target=False),
    "map_call": _card("map_call", "map()", CardType.DATA, 1, 1, "map(hit, enemies)", "Наносит 6 урона цели и 2 урона другому случайному врагу.", ["aoe"]),
    "filter_call": _card("filter_call", "filter()", CardType.DATA, 1, 0, "filter(valid, enemies)", "Наносит 5 урона. Если цель ослаблена, наносит еще 5.", ["conditional"]),
    "async_def": _card("async_def", "async def", CardType.ASYNC, 1, 0, "async def task():\n    ...", "Ставит копию следующей карты в очередь на следующий ход.", ["async"], requires_target=False),
    "await_call": _card("await_call", "await", CardType.ASYNC, 1, 0, "await task()", "Мгновенно запускает отложенные async-эффекты и дает 1 карту.", ["async"], requires_target=False),
    "memory_view": _card("memory_view", "memoryview", CardType.DATA, 0, 0, "memoryview(buffer)", "Дает 2 RAM в этом ходу.", ["resource"], requires_target=False),
    "with_context": _card("with_context", "with", CardType.CONTROL, 1, 0, "with resource() as r:\n    use(r)", "Следующая карта стоит на 1 RAM меньше.", ["combo"], requires_target=False),
    "recursion": _card("recursion", "рекурсия", CardType.CONTROL, 2, 2, "def f():\n    return f()", "Наносит 12 урона и отнимает 2 Ошибки.", ["burst"]),
    "raise_exception": _card("raise_exception", "raise", CardType.ERROR_HANDLING, 1, 0, "raise Panic()", "Потратьте 2 Ошибки, чтобы нанести 14 урона.", ["burst"]),
    "assert_stmt": _card("assert_stmt", "assert", CardType.ERROR_HANDLING, 1, 0, "assert state_ok", "Наносит 7 урона. Если цель выжила, дает 1 щит.", ["pressure"]),
    "zip_iter": _card("zip_iter", "zip()", CardType.DATA, 1, 1, "for a, b in zip(xs, ys):", "Наносит 4 урона двум врагам.", ["aoe"]),
    "enumerate_iter": _card("enumerate_iter", "enumerate()", CardType.DATA, 1, 0, "for i, item in enumerate(xs):", "Наносит 3 урона и добирает 1 карту. Улучшенная версия добирает 2.", ["draw"]),
}


STARTER_DECK: list[str] = [
    "print_debug",
    "print_debug",
    "assign_var",
    "append_list",
    "if_statement",
    "for_loop",
    "lambda_func",
    "try_except",
    "import_module",
    "memory_view",
]
