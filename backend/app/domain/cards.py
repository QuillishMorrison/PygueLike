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
    "print_debug": _card("print_debug", "print()", CardType.DATA, 1, 0, "print(target)", "Deal 4 damage.", ["starter"]),
    "assign_var": _card("assign_var", "Assignment", CardType.DATA, 0, 0, "x = value", "Gain 1 CPU.", ["starter"], requires_target=False),
    "append_list": _card("append_list", "append()", CardType.DATA, 1, 1, "items.append(x)", "Deal 5 damage and draw 1 card.", ["list"]),
    "if_statement": _card("if_statement", "if", CardType.CONTROL, 1, 0, "if condition:\n    branch()", "Deal 8 damage if the target is weakened, otherwise deal 4.", ["conditional"]),
    "for_loop": _card("for_loop", "for loop", CardType.CONTROL, 1, 0, "for _ in range(2):\n    next()", "Repeat the next played card once.", ["combo"], requires_target=False),
    "while_loop": _card("while_loop", "while loop", CardType.CONTROL, 1, 1, "while alive:\n    attack()", "Repeat the next played card twice, then lose 1 Error.", ["combo"], requires_target=False),
    "lambda_func": _card("lambda_func", "lambda", CardType.CONTROL, 0, 0, "boost = lambda x: x + 3", "The next played card gains +3 power.", ["combo"], exhausts=True, requires_target=False),
    "try_except": _card("try_except", "try/except", CardType.ERROR_HANDLING, 1, 0, "try:\n    risky()\nexcept Exception:\n    pass", "Block the next enemy error effect.", ["defense"], requires_target=False),
    "finally_block": _card("finally_block", "finally", CardType.ERROR_HANDLING, 1, 0, "finally:\n    cleanup()", "Heal 3 Errors and gain 1 RAM next turn.", ["recovery"], requires_target=False),
    "list_comprehension": _card("list_comprehension", "list comprehension", CardType.DATA, 2, 1, "[hit(e) for e in enemies]", "Deal 4 damage to all enemies.", ["aoe"]),
    "dict_lookup": _card("dict_lookup", "dict lookup", CardType.DATA, 1, 0, "value = data[key]", "Deal 4 damage and apply Weak for 1 turn.", ["debuff"]),
    "set_default": _card("set_default", "setdefault", CardType.ERROR_HANDLING, 1, 0, "cache.setdefault(key, value)", "Gain 2 Error shield and draw 1.", ["shield"], requires_target=False),
    "import_module": _card("import_module", "import", CardType.DATA, 1, 0, "import tools", "Gain 1 CPU and 1 RAM.", ["setup"], requires_target=False),
    "class_def": _card("class_def", "class", CardType.CONTROL, 2, 1, "class Hero:\n    pass", "Gain 2 Error shield and deal 3 damage to all enemies.", ["aoe"], requires_target=False),
    "decorator": _card("decorator", "decorator", CardType.CONTROL, 1, 0, "@optimize", "The next played card costs 1 less CPU and becomes stronger.", ["combo"], requires_target=False),
    "generator_expr": _card("generator_expr", "generator", CardType.ASYNC, 1, 0, "(x for x in xs)", "Draw 2 cards.", ["draw"], requires_target=False),
    "yield_value": _card("yield_value", "yield", CardType.ASYNC, 1, 0, "yield result", "Gain 2 CPU next turn.", ["tempo"], requires_target=False),
    "map_call": _card("map_call", "map()", CardType.DATA, 1, 1, "map(hit, enemies)", "Deal 6 damage to a target and 2 to another random enemy.", ["aoe"]),
    "filter_call": _card("filter_call", "filter()", CardType.DATA, 1, 0, "filter(valid, enemies)", "Deal 5 damage. If the target is weak, deal 5 more.", ["conditional"]),
    "async_def": _card("async_def", "async def", CardType.ASYNC, 1, 0, "async def task():\n    ...", "Queue a copy of the next card for next turn.", ["async"], requires_target=False),
    "await_call": _card("await_call", "await", CardType.ASYNC, 1, 0, "await task()", "Trigger queued async effects immediately and gain 1 card.", ["async"], requires_target=False),
    "memory_view": _card("memory_view", "memoryview", CardType.DATA, 0, 0, "memoryview(buffer)", "Gain 2 RAM this turn.", ["resource"], requires_target=False),
    "with_context": _card("with_context", "with", CardType.CONTROL, 1, 0, "with resource() as r:\n    use(r)", "The next card costs 1 less RAM.", ["combo"], requires_target=False),
    "recursion": _card("recursion", "recursion", CardType.CONTROL, 2, 2, "def f():\n    return f()", "Deal 12 damage and lose 2 Errors.", ["burst"]),
    "raise_exception": _card("raise_exception", "raise", CardType.ERROR_HANDLING, 1, 0, "raise Panic()", "Lose 2 Errors to deal 14 damage.", ["burst"]),
    "assert_stmt": _card("assert_stmt", "assert", CardType.ERROR_HANDLING, 1, 0, "assert state_ok", "Deal 7 damage. If the target survives, gain 1 shield.", ["pressure"]),
    "zip_iter": _card("zip_iter", "zip()", CardType.DATA, 1, 1, "for a, b in zip(xs, ys):", "Deal 4 damage to two enemies.", ["aoe"]),
    "enumerate_iter": _card("enumerate_iter", "enumerate()", CardType.DATA, 1, 0, "for i, item in enumerate(xs):", "Deal 3 damage and draw 1. If upgraded, draw 2.", ["draw"]),
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
