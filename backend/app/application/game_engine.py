from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.application.schemas import (
    CardView,
    EnemyIntentView,
    EnemyView,
    GameStateResponse,
    LevelView,
    PlayerView,
    RewardStateView,
)
from app.domain.cards import CARD_LIBRARY, STARTER_DECK
from app.domain.entities import CardType, CardZone, SessionPhase
from app.domain.enemies import ENEMY_BLUEPRINTS
from app.domain.levels import LEVEL_BLUEPRINTS
from app.infrastructure.models import CardStateModel, EnemyStateModel, GameSessionModel, LevelStateModel, PlayerStateModel

PASSIVE_LIBRARY = {
    "jit_compiler": {
        "id": "jit_compiler",
        "name": "JIT-компилятор",
        "description": "Первая карта каждого хода стоит на 1 CPU меньше.",
    },
    "garbage_collector": {
        "id": "garbage_collector",
        "name": "Сборщик мусора",
        "description": "Тяжелые карты стоят на 1 RAM меньше.",
    },
    "caching": {
        "id": "caching",
        "name": "Кэширование",
        "description": "Повторяющиеся эффекты получают +2 силы.",
    },
}


class GameEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_game(self, seed: int | None = None) -> GameSessionModel:
        seed = seed if seed is not None else random.randint(1000, 999999)
        rng = random.Random(seed)
        level_type = rng.choice(list(LEVEL_BLUEPRINTS.keys()))
        level_blueprint = LEVEL_BLUEPRINTS[level_type]
        modifier = rng.choice(level_blueprint.modifier_pool)

        session = GameSessionModel(seed=seed, phase=SessionPhase.BATTLE.value, status="active", log=[])
        player = PlayerStateModel(
            max_cpu=4,
            current_cpu=4,
            max_ram=3,
            current_ram=3,
            max_errors=30,
            current_errors=30,
            status_effects={
                "error_shield": 0,
                "repeat_next": 0,
                "bonus_next": 0,
                "cpu_discount_next": 0,
                "ram_discount_next": 0,
                "duplicate_next_async": 0,
                "queued_actions": [],
                "turn_cpu_bonus": 0,
                "turn_ram_bonus": 0,
                "next_turn_cpu_penalty": 0,
                "next_turn_ram_penalty": 0,
                "type_tax": {},
                "first_card_tax_applied": False,
                "first_data_ram_tax_applied": False,
                "last_card_id": None,
                "block_next_error": 0,
                "cards_played_this_turn": 0,
                "synergy_chain": 0,
            },
            passives=[],
            reward_state={
                "card_choice_used": False,
                "remove_used": False,
                "upgrade_used": False,
                "passive_choice_used": False,
                "reward_options": [],
                "passive_options": [],
            },
        )
        if modifier["effect"] == "passive_cache":
            player.passives.append(PASSIVE_LIBRARY["caching"])
        if modifier["effect"] == "starting_shield":
            player.status_effects["error_shield"] = modifier["value"]

        level_state = LevelStateModel(
            level_type=level_type,
            seed=seed,
            depth=1,
            difficulty_scale=level_blueprint.difficulty_scale,
            modifiers=[modifier],
            enemy_pool=level_blueprint.enemy_pool,
            notes=f"Сидовый забег для {level_type}",
        )
        session.player_state = player
        session.level_state = level_state
        self.db.add(session)
        self.db.flush()

        for index, card_id in enumerate(STARTER_DECK):
            self.db.add(
                CardStateModel(
                    game_session_id=session.id,
                    card_id=card_id,
                    zone=CardZone.DECK.value,
                    position=index,
                    upgraded=False,
                    temporary=False,
                )
            )

        enemy_count = 2 if level_blueprint.difficulty_scale <= 1.0 else 3
        for index, enemy_id in enumerate(rng.sample(level_blueprint.enemy_pool, k=min(enemy_count, len(level_blueprint.enemy_pool)))):
            blueprint = ENEMY_BLUEPRINTS[enemy_id]
            hp = int(blueprint.max_hp * level_blueprint.difficulty_scale)
            self.db.add(
                EnemyStateModel(
                    game_session_id=session.id,
                    enemy_id=enemy_id,
                    name=blueprint.name,
                    max_hp=hp,
                    current_hp=hp,
                    position=index,
                    status_effects={"weak": 0, "marked": 0, "burn": 0},
                    intent={},
                )
            )

        self.db.flush()
        self._log(session, f"Запущен сид {seed} на уровне {level_type}.")
        self._start_turn(session)
        self.db.commit()
        return session

    def load_full_session(self, session_id: str) -> GameSessionModel:
        session = self.db.query(GameSessionModel).filter(GameSessionModel.id == session_id).first()
        if not session:
            raise ValueError("Игровая сессия не найдена.")
        _ = session.player_state, session.level_state, session.cards, session.enemies
        return session

    def play_card(self, session_id: str, card_instance_id: int, target_enemy_id: int | None) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.BATTLE.value:
            raise ValueError("Карты можно играть только во время боя.")

        player = session.player_state
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.HAND.value), None)
        if not card_state:
            raise ValueError("Эта карта не находится в руке.")
        if card_state.disabled_until_turn >= session.turn_number:
            raise ValueError("Эта карта отключена на текущий ход.")

        definition = CARD_LIBRARY[card_state.card_id]
        target = self._select_target(session, target_enemy_id) if definition.requires_target else None
        cpu_cost, ram_cost = self._effective_cost(session, card_state)
        if player.current_cpu < cpu_cost:
            raise ValueError("Недостаточно CPU.")
        if player.current_ram < ram_cost:
            raise ValueError("Недостаточно RAM.")

        player.current_cpu -= cpu_cost
        player.current_ram -= ram_cost
        player.status_effects["cards_played_this_turn"] = player.status_effects.get("cards_played_this_turn", 0) + 1
        repeat_count = player.status_effects.get("repeat_next", 0)
        bonus_power = player.status_effects.get("bonus_next", 0) + self._combo_bonus(session, definition.card_id)
        async_duplicate = player.status_effects.get("duplicate_next_async", 0)
        player.status_effects["repeat_next"] = 0
        player.status_effects["bonus_next"] = 0
        player.status_effects["duplicate_next_async"] = 0
        player.status_effects["cpu_discount_next"] = 0
        player.status_effects["ram_discount_next"] = 0

        for resolve_index in range(1 + repeat_count):
            self._resolve_card_effect(
                session,
                card_state,
                definition.card_id,
                target,
                bonus_power + self._caching_bonus(player, card_state.card_id, resolve_index),
            )

        if async_duplicate:
            queued_actions = list(player.status_effects.get("queued_actions", []))
            queued_actions.append(
                {
                    "turn": session.turn_number + 1,
                    "card_id": definition.card_id,
                    "target_enemy_id": target.id if target else None,
                    "power": max(2, bonus_power + 2),
                }
            )
            player.status_effects["queued_actions"] = queued_actions
            self._log(session, f"{definition.name} поставлена в async-очередь.")

        if player.status_effects["cards_played_this_turn"] % 3 == 0:
            player.current_cpu += 1
            self._log(session, "Three-card chain restored 1 CPU.")

        card_state.zone = CardZone.EXHAUST.value if definition.exhausts else CardZone.DISCARD.value
        player.status_effects["last_card_id"] = card_state.card_id
        self._normalize_zone_positions(session)
        self._update_enemy_intents(session)
        self._check_battle_end(session)
        self.db.commit()
        return session

    def end_turn(self, session_id: str) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.BATTLE.value:
            raise ValueError("Бой сейчас не активен.")

        self._enemy_turn(session)
        self._check_battle_end(session)
        if session.phase == SessionPhase.BATTLE.value:
            session.turn_number += 1
            self._start_turn(session)
        self.db.commit()
        return session

    def choose_reward_card(self, session_id: str, reward_card_id: str) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Награды сейчас недоступны.")
        reward_state = session.player_state.reward_state
        if reward_state.get("card_choice_used"):
            raise ValueError("Наградная карта уже выбрана.")
        if reward_card_id not in reward_state.get("reward_options", []):
            raise ValueError("Эта карта не предлагалась в награду.")
        deck_size = len([card for card in session.cards if card.zone == CardZone.DECK.value])
        self.db.add(
            CardStateModel(
                game_session_id=session.id,
                card_id=reward_card_id,
                zone=CardZone.DECK.value,
                position=deck_size,
                upgraded=False,
                temporary=False,
            )
        )
        reward_state["card_choice_used"] = True
        self._log(session, f"Карта {CARD_LIBRARY[reward_card_id].name} добавлена в колоду.")
        self.db.commit()
        return session

    def remove_deck_card(self, session_id: str, card_instance_id: int) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Удаление карты доступно только после боя.")
        reward_state = session.player_state.reward_state
        if reward_state.get("remove_used"):
            raise ValueError("Удаление уже использовано.")
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.DECK.value), None)
        if not card_state:
            raise ValueError("Удалять можно только карты из колоды.")
        self.db.delete(card_state)
        reward_state["remove_used"] = True
        self._log(session, "Карта удалена из колоды.")
        self.db.commit()
        return session

    def upgrade_deck_card(self, session_id: str, card_instance_id: int) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Улучшение карты доступно только после боя.")
        reward_state = session.player_state.reward_state
        if reward_state.get("upgrade_used"):
            raise ValueError("Улучшение уже использовано.")
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.DECK.value), None)
        if not card_state:
            raise ValueError("Улучшать можно только карты из колоды.")
        card_state.upgraded = True
        reward_state["upgrade_used"] = True
        self._log(session, f"Карта {CARD_LIBRARY[card_state.card_id].name} улучшена.")
        self.db.commit()
        return session

    def choose_passive(self, session_id: str, passive_id: str) -> GameSessionModel:
        session = self.load_full_session(session_id)
        reward_state = session.player_state.reward_state
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Пассивки можно выбирать только после боя.")
        if reward_state.get("passive_choice_used"):
            raise ValueError("Passive reward already chosen.")
        if passive_id not in reward_state.get("passive_options", []):
            raise ValueError("Passive not offered.")
        passive = PASSIVE_LIBRARY.get(passive_id)
        if not passive:
            raise ValueError("Неизвестная пассивка.")
        if any(existing["id"] == passive_id for existing in session.player_state.passives):
            raise ValueError("Эта пассивка уже выбрана.")
        session.player_state.passives.append(passive)
        reward_state["passive_choice_used"] = True
        self._log(session, f"Установлена пассивка {passive['name']}.")
        self.db.commit()
        return session

    def serialize(self, session: GameSessionModel) -> GameStateResponse:
        session = self.load_full_session(session.id)
        player = session.player_state
        reward_state = player.reward_state or {}
        return GameStateResponse(
            session_id=session.id,
            phase=session.phase,
            status=session.status,
            turn_number=session.turn_number,
            player=PlayerView(
                cpu=player.current_cpu,
                max_cpu=player.max_cpu,
                ram=player.current_ram,
                max_ram=player.max_ram,
                errors=player.current_errors,
                max_errors=player.max_errors,
                error_shield=player.status_effects.get("error_shield", 0),
                passives=player.passives,
                status_effects=player.status_effects,
            ),
            hand=[self._card_view(session, card) for card in self._sorted_cards(session, CardZone.HAND.value)],
            draw_pile=len([card for card in session.cards if card.zone == CardZone.DECK.value]),
            discard_pile=len([card for card in session.cards if card.zone == CardZone.DISCARD.value]),
            exhaust_pile=len([card for card in session.cards if card.zone == CardZone.EXHAUST.value]),
            deck_cards=[self._card_view(session, card) for card in self._sorted_cards(session, CardZone.DECK.value)],
            enemies=[
                EnemyView(
                    instance_id=enemy.id,
                    enemy_id=enemy.enemy_id,
                    name=enemy.name,
                    hp=max(0, enemy.current_hp),
                    max_hp=enemy.max_hp,
                    intent=EnemyIntentView(label=enemy.intent.get("label", "Ожидание"), details=enemy.intent.get("details", "")),
                    statuses=enemy.status_effects,
                )
                for enemy in self._living_enemies(session)
            ],
            level=LevelView(
                level_type=session.level_state.level_type,
                modifiers=session.level_state.modifiers,
                enemy_pool=session.level_state.enemy_pool,
                difficulty_scale=float(session.level_state.difficulty_scale),
            ),
            log=session.log[-8:],
            reward_state=RewardStateView(
                can_choose_card=not reward_state.get("card_choice_used", False),
                reward_options=[self._virtual_card_view(card_id) for card_id in reward_state.get("reward_options", [])],
                can_remove_card=not reward_state.get("remove_used", False),
                can_upgrade_card=not reward_state.get("upgrade_used", False),
                can_choose_passive=not reward_state.get("passive_choice_used", False),
                passive_options=[PASSIVE_LIBRARY[passive_id] for passive_id in reward_state.get("passive_options", []) if passive_id in PASSIVE_LIBRARY],
            ),
        )

    def _start_turn(self, session: GameSessionModel) -> None:
        player = session.player_state
        player.status_effects["first_card_tax_applied"] = False
        player.status_effects["first_data_ram_tax_applied"] = False
        player.status_effects["cards_played_this_turn"] = 0
        player.status_effects["synergy_chain"] = 0
        player.current_cpu = max(0, player.max_cpu + player.status_effects.pop("turn_cpu_bonus", 0) - player.status_effects.pop("next_turn_cpu_penalty", 0))
        player.current_ram = max(0, player.max_ram + player.status_effects.pop("turn_ram_bonus", 0) - player.status_effects.pop("next_turn_ram_penalty", 0))
        if any(passive["id"] == "jit_compiler" for passive in player.passives):
            player.status_effects["cpu_discount_next"] = 1
        self._resolve_queued_actions(session)
        self._draw_cards(session, 5 + self._turn_draw_bonus(session))
        self._update_enemy_intents(session)
        self._log(session, f"Начался ход {session.turn_number}.")

    def _draw_cards(self, session: GameSessionModel, count: int) -> None:
        for _ in range(count):
            self._draw_one(session)

    def _draw_one(self, session: GameSessionModel) -> None:
        draw_pile = self._sorted_cards(session, CardZone.DECK.value)
        if not draw_pile:
            discard_pile = self._sorted_cards(session, CardZone.DISCARD.value)
            for index, card in enumerate(discard_pile):
                card.zone = CardZone.DECK.value
                card.position = index
            draw_pile = self._sorted_cards(session, CardZone.DECK.value)
        if not draw_pile:
            return
        card = draw_pile[0]
        hand_size = len([entry for entry in session.cards if entry.zone == CardZone.HAND.value])
        card.zone = CardZone.HAND.value
        card.position = hand_size

    def _effective_cost(self, session: GameSessionModel, card_state: CardStateModel) -> tuple[int, int]:
        player = session.player_state
        definition = CARD_LIBRARY[card_state.card_id]
        cpu_cost = definition.cpu_cost - player.status_effects.get("cpu_discount_next", 0)
        ram_cost = definition.ram_cost - player.status_effects.get("ram_discount_next", 0)
        if card_state.upgraded and definition.cpu_cost > 0:
            cpu_cost -= 1
        if any(passive["id"] == "garbage_collector" for passive in player.passives) and definition.ram_cost > 0:
            ram_cost -= 1
        for modifier in session.level_state.modifiers:
            if modifier["effect"] == "cpu_tax" and not player.status_effects.get("first_card_tax_applied"):
                cpu_cost += modifier["value"]
            if modifier["effect"] == "ram_tax" and definition.card_type == CardType.DATA and not player.status_effects.get("first_data_ram_tax_applied"):
                ram_cost += modifier["value"]
            if modifier["effect"] == "async_tax" and definition.card_type == CardType.ASYNC:
                cpu_cost += modifier["value"]
        type_tax = player.status_effects.get("type_tax", {})
        if definition.card_type.value in type_tax:
            cpu_cost += type_tax[definition.card_type.value].get("cpu", 0)
            ram_cost += type_tax[definition.card_type.value].get("ram", 0)
        return max(0, cpu_cost), max(0, ram_cost)

    def _resolve_card_effect(
        self,
        session: GameSessionModel,
        card_state: CardStateModel,
        card_id: str,
        target: EnemyStateModel | None,
        bonus_power: int,
    ) -> None:
        player = session.player_state
        definition = CARD_LIBRARY[card_id]
        for modifier in session.level_state.modifiers:
            if modifier["effect"] == "cpu_tax":
                player.status_effects["first_card_tax_applied"] = True
            if modifier["effect"] == "ram_tax" and definition.card_type == CardType.DATA:
                player.status_effects["first_data_ram_tax_applied"] = True

        match card_id:
            case "print_debug":
                self._deal_damage(session, target, 5 + bonus_power)
            case "assign_var":
                player.current_cpu += 1 + (1 if card_state.upgraded else 0)
            case "append_list":
                self._deal_damage(session, target, 4 + bonus_power + (2 if target and target.status_effects.get("marked", 0) else 0))
                self._draw_cards(session, 1)
            case "if_statement":
                self._deal_damage(session, target, (9 if target and (target.status_effects.get("weak", 0) or target.status_effects.get("marked", 0)) else 4) + bonus_power)
            case "for_loop":
                player.status_effects["repeat_next"] = player.status_effects.get("repeat_next", 0) + 1
            case "while_loop":
                player.status_effects["repeat_next"] = player.status_effects.get("repeat_next", 0) + 1
                player.status_effects["bonus_next"] = player.status_effects.get("bonus_next", 0) + 2
                self._apply_error_damage(session, 1)
            case "lambda_func":
                player.status_effects["bonus_next"] = player.status_effects.get("bonus_next", 0) + 4
                if card_state.upgraded:
                    player.status_effects["cpu_discount_next"] = player.status_effects.get("cpu_discount_next", 0) + 1
            case "try_except":
                player.status_effects["block_next_error"] = player.status_effects.get("block_next_error", 0) + 1
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 1
            case "finally_block":
                self._heal_player(session, 3)
                player.status_effects["turn_ram_bonus"] = player.status_effects.get("turn_ram_bonus", 0) + 1
            case "list_comprehension":
                for enemy in self._living_enemies(session):
                    self._apply_status(enemy, "burn", 1)
                    self._deal_damage(session, enemy, 3 + bonus_power)
            case "dict_lookup":
                self._deal_damage(session, target, 4 + bonus_power)
                if target:
                    self._apply_status(target, "weak", 1)
                    self._apply_status(target, "marked", 1 + (1 if card_state.upgraded else 0))
            case "set_default":
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 3
                if card_state.upgraded:
                    player.current_cpu += 1
                self._draw_cards(session, 1)
            case "import_module":
                player.current_cpu += 1
                player.current_ram += 1
                if card_state.upgraded:
                    self._draw_cards(session, 1)
            case "class_def":
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 2
                for enemy in self._living_enemies(session):
                    self._apply_status(enemy, "marked", 1)
                    self._deal_damage(session, enemy, 4 + bonus_power)
            case "decorator":
                player.status_effects["cpu_discount_next"] = player.status_effects.get("cpu_discount_next", 0) + 1
                player.status_effects["bonus_next"] = player.status_effects.get("bonus_next", 0) + 2
            case "generator_expr":
                self._draw_cards(session, 2 + (1 if card_state.upgraded else 0))
            case "yield_value":
                player.status_effects["turn_cpu_bonus"] = player.status_effects.get("turn_cpu_bonus", 0) + 2
                if card_state.upgraded:
                    player.status_effects["turn_ram_bonus"] = player.status_effects.get("turn_ram_bonus", 0) + 1
            case "map_call":
                self._deal_damage(session, target, 6 + bonus_power)
                splash = self._random_other_enemy(session, target.id if target else None)
                if splash:
                    self._deal_damage(session, splash, 4 + bonus_power)
            case "filter_call":
                damage = 6 + (6 if target and (target.status_effects.get("weak", 0) or target.status_effects.get("marked", 0)) else 0)
                self._deal_damage(session, target, damage + bonus_power)
            case "async_def":
                player.status_effects["duplicate_next_async"] = player.status_effects.get("duplicate_next_async", 0) + 1
                player.status_effects["cpu_discount_next"] = player.status_effects.get("cpu_discount_next", 0) + 1
            case "await_call":
                resolved_now = self._resolve_queued_actions(session, immediate=True)
                if resolved_now:
                    player.current_cpu += 1
                self._draw_cards(session, 1)
            case "memory_view":
                player.current_ram += 2 + (1 if card_state.upgraded else 0)
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 1
            case "with_context":
                player.status_effects["ram_discount_next"] = player.status_effects.get("ram_discount_next", 0) + 1
                if card_state.upgraded:
                    player.status_effects["block_next_error"] = player.status_effects.get("block_next_error", 0) + 1
            case "recursion":
                self._deal_damage(session, target, 10 + bonus_power + (2 if card_state.upgraded else 0))
                if target:
                    self._apply_status(target, "marked", 1)
                self._apply_error_damage(session, 1)
            case "raise_exception":
                self._apply_error_damage(session, 1)
                self._deal_damage(session, target, 14 + bonus_power + (2 if card_state.upgraded else 0))
            case "assert_stmt":
                self._deal_damage(session, target, 7 + bonus_power + (4 if target and target.status_effects.get("marked", 0) else 0))
                if target and target.current_hp > 0:
                    player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 1
            case "zip_iter":
                targets = self._living_enemies(session)[:2]
                if target and target not in targets:
                    targets = [target] + targets[:1]
                for enemy in targets:
                    self._deal_damage(session, enemy, 5 + bonus_power)
            case "enumerate_iter":
                self._deal_damage(session, target, 4 + bonus_power)
                self._draw_cards(session, 2 if card_state.upgraded else 1)
            case _:
                raise ValueError(f"Необработанный эффект карты: {card_id}")
        self._log(session, f"Сыграна карта {definition.name}.")

    def _enemy_turn(self, session: GameSessionModel) -> None:
        session.player_state.status_effects["type_tax"] = {}
        self._tick_enemy_statuses(session)
        for enemy in self._living_enemies(session):
            self._apply_enemy_effect(session, enemy)
            enemy.status_effects["weak"] = max(0, enemy.status_effects.get("weak", 0) - 1)
        for card in self._sorted_cards(session, CardZone.HAND.value):
            card.zone = CardZone.DISCARD.value
        self._normalize_zone_positions(session)
        self._log(session, "Ход врагов завершен.")

    def _apply_enemy_effect(self, session: GameSessionModel, enemy: EnemyStateModel) -> None:
        player = session.player_state
        if enemy.current_hp <= 0:
            return
        turn_even = session.turn_number % 2 == 0
        if player.status_effects.get("block_next_error", 0) > 0:
            player.status_effects["block_next_error"] -= 1
            self._log(session, f"{enemy.name} заблокирован через try/except.")
            return
        match enemy.enemy_id:
            case "syntax_error":
                if turn_even:
                    self._apply_error_damage(session, 2)
                    self._disable_random_card(session, CardType.CONTROL.value)
                else:
                    self._apply_error_damage(session, 5)
                    self._add_type_tax(player, CardType.CONTROL.value, cpu=1)
            case "type_error":
                self._apply_error_damage(session, 4)
                self._disable_random_card(session, CardType.DATA.value)
                if turn_even:
                    self._add_type_tax(player, CardType.DATA.value, cpu=1)
            case "memory_error":
                self._apply_error_damage(session, 3)
                player.status_effects["next_turn_ram_penalty"] = player.status_effects.get("next_turn_ram_penalty", 0) + 1
                if turn_even:
                    player.status_effects["next_turn_cpu_penalty"] = player.status_effects.get("next_turn_cpu_penalty", 0) + 1
            case "timeout_error":
                self._apply_error_damage(session, 2)
                player.status_effects["next_turn_cpu_penalty"] = player.status_effects.get("next_turn_cpu_penalty", 0) + 1
                self._delay_queued_actions(player)
            case "key_error":
                if player.status_effects.get("error_shield", 0) > 0:
                    burn = min(2, player.status_effects.get("error_shield", 0))
                    player.status_effects["error_shield"] -= burn
                    self._log(session, f"KeyError burned {burn} shield.")
                    self._log(session, "KeyError сжег 1 щит.")
                else:
                    self._apply_error_damage(session, 4)
            case "recursion_error":
                self._apply_error_damage(session, 2 + session.turn_number)
                enemy.current_hp = min(enemy.max_hp, enemy.current_hp + 2)
                self._log(session, f"{enemy.name} regains 2 HP.")
            case "import_error":
                self._apply_error_damage(session, 3)
                self._add_type_tax(player, CardType.ASYNC.value, cpu=1)
                queued = list(player.status_effects.get("queued_actions", []))
                if queued:
                    queued.pop(0)
                    player.status_effects["queued_actions"] = queued
                    self._log(session, "ImportError dropped one queued action.")
            case _:
                self._apply_error_damage(session, 3)

    def _update_enemy_intents(self, session: GameSessionModel) -> None:
        for enemy in self._living_enemies(session):
            match enemy.enemy_id:
                case "syntax_error":
                    enemy.intent = {"label": "Сбой парсинга", "details": "4 урона и control-карты стоят на 1 CPU дороже."}
                case "type_error":
                    enemy.intent = {"label": "Плохое приведение", "details": "5 урона и отключение одной data-карты."}
                case "memory_error":
                    enemy.intent = {"label": "Пик кучи", "details": "3 урона и -1 RAM на следующий ход."}
                case "timeout_error":
                    enemy.intent = {"label": "Медленный запрос", "details": "2 урона и -1 CPU на следующий ход."}
                case "key_error":
                    enemy.intent = {"label": "Потерянный ключ", "details": "Сначала сжигает щит, иначе наносит 4 урона."}
                case "recursion_error":
                    enemy.intent = {"label": "Бесконечный стек", "details": f"{2 + session.turn_number} урона с ростом от хода."}
                case "import_error":
                    enemy.intent = {"label": "Сбой зависимости", "details": "3 урона и async-карты стоят на 1 CPU дороже."}

    def _check_battle_end(self, session: GameSessionModel) -> None:
        if session.player_state.current_errors <= 0:
            session.phase = SessionPhase.GAME_OVER.value
            session.status = "defeat"
            self._log(session, "Интерпретатор рухнул.")
            return
        if not self._living_enemies(session) and session.phase == SessionPhase.BATTLE.value:
            session.phase = SessionPhase.REWARD.value
            session.status = "victory"
            reward_rng = random.Random(session.seed + session.turn_number)
            session.player_state.reward_state = {
                "card_choice_used": False,
                "remove_used": False,
                "upgrade_used": False,
                "passive_choice_used": False,
                "reward_options": self._build_reward_options(session, reward_rng),
                "passive_options": self._build_passive_options(session, reward_rng),
            }
            self._log(session, "Бой завершен. Открыта фаза наград.")

    def _resolve_queued_actions(self, session: GameSessionModel, immediate: bool = False) -> int:
        queued = session.player_state.status_effects.get("queued_actions", [])
        remaining = []
        resolved = 0
        for action in queued:
            if immediate or action["turn"] <= session.turn_number:
                target = self._select_target(session, action.get("target_enemy_id"), allow_fallback=True)
                if target:
                    virtual_card = CardStateModel(card_id=action["card_id"], zone=CardZone.HAND.value, position=0, upgraded=False, temporary=True)
                    self._resolve_card_effect(session, virtual_card, action["card_id"], target, action.get("power", 0))
                    resolved += 1
            else:
                remaining.append(action)
        session.player_state.status_effects["queued_actions"] = remaining
        return resolved

    def _turn_draw_bonus(self, session: GameSessionModel) -> int:
        bonus = 0
        if session.turn_number == 1:
            for modifier in session.level_state.modifiers:
                if modifier["effect"] == "draw_bonus":
                    bonus += modifier["value"]
        return bonus

    def _apply_error_damage(self, session: GameSessionModel, amount: int) -> None:
        player = session.player_state
        shield = player.status_effects.get("error_shield", 0)
        if shield > 0:
            blocked = min(shield, amount)
            player.status_effects["error_shield"] = shield - blocked
            amount -= blocked
            if blocked:
                self._log(session, f"Щит заблокировал {blocked} урона.")
        if amount > 0:
            player.current_errors = max(0, player.current_errors - amount)
            self._log(session, f"Получено {amount} урона по Ошибкам.")

    def _heal_player(self, session: GameSessionModel, amount: int) -> None:
        player = session.player_state
        player.current_errors = min(player.max_errors, player.current_errors + amount)

    def _deal_damage(self, session: GameSessionModel, enemy: EnemyStateModel | None, amount: int) -> None:
        if not enemy or enemy.current_hp <= 0:
            return
        effective_damage = amount + (1 if enemy.status_effects.get("weak", 0) and amount > 0 else 0)
        if enemy.status_effects.get("marked", 0) and amount > 0:
            effective_damage += 3
            enemy.status_effects["marked"] = max(0, enemy.status_effects.get("marked", 0) - 1)
        enemy.current_hp = max(0, enemy.current_hp - effective_damage)
        self._log(session, f"{enemy.name} получает {effective_damage} урона.")

    def _sorted_cards(self, session: GameSessionModel, zone: str) -> list[CardStateModel]:
        return sorted([card for card in session.cards if card.zone == zone], key=lambda card: card.position)

    def _normalize_zone_positions(self, session: GameSessionModel) -> None:
        for zone in [CardZone.DECK.value, CardZone.HAND.value, CardZone.DISCARD.value, CardZone.EXHAUST.value]:
            for index, card in enumerate(self._sorted_cards(session, zone)):
                card.position = index

    def _living_enemies(self, session: GameSessionModel) -> list[EnemyStateModel]:
        return [enemy for enemy in sorted(session.enemies, key=lambda item: item.position) if enemy.current_hp > 0]

    def _select_target(self, session: GameSessionModel, target_enemy_id: int | None, allow_fallback: bool = False) -> EnemyStateModel | None:
        living = self._living_enemies(session)
        if not living:
            return None
        if target_enemy_id is not None:
            for enemy in living:
                if enemy.id == target_enemy_id:
                    return enemy
        if allow_fallback or len(living) == 1:
            return living[0]
        raise ValueError("Выберите цель среди врагов.")

    def _random_other_enemy(self, session: GameSessionModel, excluded_enemy_id: int | None) -> EnemyStateModel | None:
        options = [enemy for enemy in self._living_enemies(session) if enemy.id != excluded_enemy_id]
        return random.choice(options) if options else None

    def _disable_random_card(self, session: GameSessionModel, card_type: str) -> None:
        candidates = [card for card in self._sorted_cards(session, CardZone.HAND.value) if CARD_LIBRARY[card.card_id].card_type.value == card_type]
        if candidates:
            candidates[0].disabled_until_turn = session.turn_number + 1
            self._log(session, f"Карта {CARD_LIBRARY[candidates[0].card_id].name} отключена.")

    def _add_type_tax(self, player: PlayerStateModel, card_type: str, cpu: int = 0, ram: int = 0) -> None:
        taxes = player.status_effects.get("type_tax", {})
        taxes.setdefault(card_type, {"cpu": 0, "ram": 0})
        taxes[card_type]["cpu"] += cpu
        taxes[card_type]["ram"] += ram
        player.status_effects["type_tax"] = taxes

    def _apply_status(self, enemy: EnemyStateModel, status_name: str, amount: int) -> None:
        enemy.status_effects[status_name] = enemy.status_effects.get(status_name, 0) + amount

    def _tick_enemy_statuses(self, session: GameSessionModel) -> None:
        for enemy in self._living_enemies(session):
            burn = enemy.status_effects.get("burn", 0)
            if burn > 0:
                enemy.current_hp = max(0, enemy.current_hp - burn)
                enemy.status_effects["burn"] = max(0, burn - 1)
                self._log(session, f"{enemy.name} burns for {burn}.")

    def _delay_queued_actions(self, player: PlayerStateModel) -> None:
        queued = list(player.status_effects.get("queued_actions", []))
        for action in queued:
            action["turn"] += 1
        player.status_effects["queued_actions"] = queued

    def _combo_bonus(self, session: GameSessionModel, card_id: str) -> int:
        player = session.player_state
        last_card_id = player.status_effects.get("last_card_id")
        if not last_card_id:
            player.status_effects["synergy_chain"] = 0
            return 0
        current_tags = set(CARD_LIBRARY[card_id].synergy_tags)
        previous_tags = set(CARD_LIBRARY[last_card_id].synergy_tags)
        if current_tags & previous_tags:
            player.status_effects["synergy_chain"] = player.status_effects.get("synergy_chain", 0) + 1
            bonus = 2 + min(2, player.status_effects["synergy_chain"])
            self._log(session, f"Combo online: +{bonus} power.")
            return bonus
        player.status_effects["synergy_chain"] = 0
        return 0

    def _build_reward_options(self, session: GameSessionModel, rng: random.Random) -> list[str]:
        deck_card_ids = [card.card_id for card in session.cards if card.zone in {CardZone.DECK.value, CardZone.HAND.value, CardZone.DISCARD.value}]
        tag_weights: dict[str, int] = {}
        for card_id in deck_card_ids:
            for tag in CARD_LIBRARY[card_id].synergy_tags:
                tag_weights[tag] = tag_weights.get(tag, 0) + 1
        weighted_pool: list[str] = []
        for card_id, definition in CARD_LIBRARY.items():
            weight = 1 + sum(tag_weights.get(tag, 0) for tag in definition.synergy_tags)
            weighted_pool.extend([card_id] * max(1, weight))
        options: list[str] = []
        while weighted_pool and len(options) < 3:
            candidate = rng.choice(weighted_pool)
            if candidate not in options:
                options.append(candidate)
        return options

    def _build_passive_options(self, session: GameSessionModel, rng: random.Random) -> list[str]:
        owned = {passive["id"] for passive in session.player_state.passives}
        available = [passive_id for passive_id in PASSIVE_LIBRARY if passive_id not in owned]
        rng.shuffle(available)
        return available[:2]

    def _caching_bonus(self, player: PlayerStateModel, card_id: str, resolve_index: int) -> int:
        if not any(passive["id"] == "caching" for passive in player.passives):
            return 0
        if resolve_index > 0 or player.status_effects.get("last_card_id") == card_id:
            return 2
        return 0

    def _virtual_card_view(self, card_id: str) -> CardView:
        definition = CARD_LIBRARY[card_id]
        return CardView(
            instance_id=0,
            card_id=card_id,
            name=definition.name,
            card_type=definition.card_type.value,
            cpu_cost=definition.cpu_cost,
            ram_cost=definition.ram_cost,
            snippet=definition.snippet,
            description=definition.description,
            synergy_tags=definition.synergy_tags,
            upgraded=False,
            disabled=False,
            zone="reward",
            requires_target=definition.requires_target,
        )

    def _card_view(self, session: GameSessionModel, card_state: CardStateModel) -> CardView:
        definition = CARD_LIBRARY[card_state.card_id]
        cpu_cost, ram_cost = self._effective_cost(session, card_state)
        return CardView(
            instance_id=card_state.id,
            card_id=card_state.card_id,
            name=definition.name,
            card_type=definition.card_type.value,
            cpu_cost=cpu_cost,
            ram_cost=ram_cost,
            snippet=definition.snippet,
            description=definition.description,
            synergy_tags=definition.synergy_tags,
            upgraded=card_state.upgraded,
            disabled=card_state.disabled_until_turn >= session.turn_number,
            zone=card_state.zone,
            requires_target=definition.requires_target,
        )

    def _log(self, session: GameSessionModel, message: str) -> None:
        session.log = (session.log or [])[-29:] + [message]
