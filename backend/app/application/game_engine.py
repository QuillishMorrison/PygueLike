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
        "name": "JIT Compiler",
        "description": "Reduce CPU cost of your first card each turn by 1.",
    },
    "garbage_collector": {
        "id": "garbage_collector",
        "name": "Garbage Collector",
        "description": "Reduce RAM cost of heavy cards by 1.",
    },
    "caching": {
        "id": "caching",
        "name": "Caching",
        "description": "Repeated effects gain +2 power.",
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
            max_cpu=3,
            current_cpu=3,
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
            },
            passives=[],
            reward_state={"card_choice_used": False, "remove_used": False, "upgrade_used": False, "reward_options": []},
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
            notes=f"Seeded run for {level_type}",
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

        for index, enemy_id in enumerate(rng.sample(level_blueprint.enemy_pool, k=min(3, len(level_blueprint.enemy_pool)))):
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
                    status_effects={"weak": 0},
                    intent={},
                )
            )

        self.db.flush()
        self._log(session, f"Booted run with seed {seed} in {level_type}.")
        self._start_turn(session)
        self.db.commit()
        return session

    def load_full_session(self, session_id: str) -> GameSessionModel:
        session = self.db.query(GameSessionModel).filter(GameSessionModel.id == session_id).first()
        if not session:
            raise ValueError("Game session not found.")
        _ = session.player_state, session.level_state, session.cards, session.enemies
        return session

    def play_card(self, session_id: str, card_instance_id: int, target_enemy_id: int | None) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.BATTLE.value:
            raise ValueError("Cards can only be played during battle.")

        player = session.player_state
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.HAND.value), None)
        if not card_state:
            raise ValueError("Card is not in hand.")
        if card_state.disabled_until_turn >= session.turn_number:
            raise ValueError("This card is disabled this turn.")

        definition = CARD_LIBRARY[card_state.card_id]
        target = self._select_target(session, target_enemy_id) if definition.requires_target else None
        cpu_cost, ram_cost = self._effective_cost(session, card_state)
        if player.current_cpu < cpu_cost:
            raise ValueError("Not enough CPU.")
        if player.current_ram < ram_cost:
            raise ValueError("Not enough RAM.")

        player.current_cpu -= cpu_cost
        player.current_ram -= ram_cost
        repeat_count = player.status_effects.get("repeat_next", 0)
        bonus_power = player.status_effects.get("bonus_next", 0)
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
            self._log(session, f"{definition.name} was scheduled asynchronously.")

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
            raise ValueError("Battle is not active.")

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
            raise ValueError("Rewards are not available.")
        reward_state = session.player_state.reward_state
        if reward_state.get("card_choice_used"):
            raise ValueError("Card reward already chosen.")
        if reward_card_id not in reward_state.get("reward_options", []):
            raise ValueError("Reward card not offered.")
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
        self._log(session, f"Added {CARD_LIBRARY[reward_card_id].name} to the deck.")
        self.db.commit()
        return session

    def remove_deck_card(self, session_id: str, card_instance_id: int) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Card removal is only available after battle.")
        reward_state = session.player_state.reward_state
        if reward_state.get("remove_used"):
            raise ValueError("Removal already used.")
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.DECK.value), None)
        if not card_state:
            raise ValueError("Only deck cards can be removed.")
        self.db.delete(card_state)
        reward_state["remove_used"] = True
        self._log(session, "Removed a card from the deck.")
        self.db.commit()
        return session

    def upgrade_deck_card(self, session_id: str, card_instance_id: int) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Card upgrades are only available after battle.")
        reward_state = session.player_state.reward_state
        if reward_state.get("upgrade_used"):
            raise ValueError("Upgrade already used.")
        card_state = next((card for card in session.cards if card.id == card_instance_id and card.zone == CardZone.DECK.value), None)
        if not card_state:
            raise ValueError("Only deck cards can be upgraded.")
        card_state.upgraded = True
        reward_state["upgrade_used"] = True
        self._log(session, f"Upgraded {CARD_LIBRARY[card_state.card_id].name}.")
        self.db.commit()
        return session

    def choose_passive(self, session_id: str, passive_id: str) -> GameSessionModel:
        session = self.load_full_session(session_id)
        if session.phase != SessionPhase.REWARD.value:
            raise ValueError("Passives can only be chosen after battle.")
        passive = PASSIVE_LIBRARY.get(passive_id)
        if not passive:
            raise ValueError("Unknown passive.")
        if any(existing["id"] == passive_id for existing in session.player_state.passives):
            raise ValueError("Passive already owned.")
        session.player_state.passives.append(passive)
        self._log(session, f"Installed passive {passive['name']}.")
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
                    intent=EnemyIntentView(label=enemy.intent.get("label", "Idle"), details=enemy.intent.get("details", "")),
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
            ),
        )

    def _start_turn(self, session: GameSessionModel) -> None:
        player = session.player_state
        player.status_effects["first_card_tax_applied"] = False
        player.status_effects["first_data_ram_tax_applied"] = False
        player.current_cpu = max(0, player.max_cpu + player.status_effects.pop("turn_cpu_bonus", 0) - player.status_effects.pop("next_turn_cpu_penalty", 0))
        player.current_ram = max(0, player.max_ram + player.status_effects.pop("turn_ram_bonus", 0) - player.status_effects.pop("next_turn_ram_penalty", 0))
        if any(passive["id"] == "jit_compiler" for passive in player.passives):
            player.status_effects["cpu_discount_next"] = 1
        self._resolve_queued_actions(session)
        self._draw_cards(session, 5 + self._turn_draw_bonus(session))
        self._update_enemy_intents(session)
        self._log(session, f"Turn {session.turn_number} started.")

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
                self._deal_damage(session, target, 4 + bonus_power)
            case "assign_var":
                player.current_cpu += 1 + (1 if card_state.upgraded else 0)
            case "append_list":
                self._deal_damage(session, target, 5 + bonus_power)
                self._draw_cards(session, 1)
            case "if_statement":
                self._deal_damage(session, target, (8 if target and target.status_effects.get("weak", 0) else 4) + bonus_power)
            case "for_loop":
                player.status_effects["repeat_next"] = player.status_effects.get("repeat_next", 0) + 1
            case "while_loop":
                player.status_effects["repeat_next"] = player.status_effects.get("repeat_next", 0) + 2
                self._apply_error_damage(session, 1)
            case "lambda_func":
                player.status_effects["bonus_next"] = player.status_effects.get("bonus_next", 0) + 3
            case "try_except":
                player.status_effects["block_next_error"] = player.status_effects.get("block_next_error", 0) + 1
            case "finally_block":
                self._heal_player(session, 3)
                player.status_effects["turn_ram_bonus"] = player.status_effects.get("turn_ram_bonus", 0) + 1
            case "list_comprehension":
                for enemy in self._living_enemies(session):
                    self._deal_damage(session, enemy, 4 + bonus_power)
            case "dict_lookup":
                self._deal_damage(session, target, 4 + bonus_power)
                if target:
                    target.status_effects["weak"] = target.status_effects.get("weak", 0) + 1
            case "set_default":
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 2 + (1 if card_state.upgraded else 0)
                self._draw_cards(session, 1)
            case "import_module":
                player.current_cpu += 1
                player.current_ram += 1
            case "class_def":
                player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 2
                for enemy in self._living_enemies(session):
                    self._deal_damage(session, enemy, 3 + bonus_power)
            case "decorator":
                player.status_effects["cpu_discount_next"] = player.status_effects.get("cpu_discount_next", 0) + 1
                player.status_effects["bonus_next"] = player.status_effects.get("bonus_next", 0) + 2
            case "generator_expr":
                self._draw_cards(session, 2 + (1 if card_state.upgraded else 0))
            case "yield_value":
                player.status_effects["turn_cpu_bonus"] = player.status_effects.get("turn_cpu_bonus", 0) + 2
            case "map_call":
                self._deal_damage(session, target, 6 + bonus_power)
                splash = self._random_other_enemy(session, target.id if target else None)
                if splash:
                    self._deal_damage(session, splash, 2 + bonus_power)
            case "filter_call":
                damage = 10 if target and target.status_effects.get("weak", 0) else 5
                self._deal_damage(session, target, damage + bonus_power)
            case "async_def":
                player.status_effects["duplicate_next_async"] = player.status_effects.get("duplicate_next_async", 0) + 1
            case "await_call":
                self._resolve_queued_actions(session, immediate=True)
                self._draw_cards(session, 1)
            case "memory_view":
                player.current_ram += 2 + (1 if card_state.upgraded else 0)
            case "with_context":
                player.status_effects["ram_discount_next"] = player.status_effects.get("ram_discount_next", 0) + 1
            case "recursion":
                self._deal_damage(session, target, 12 + bonus_power + (2 if card_state.upgraded else 0))
                self._apply_error_damage(session, 2)
            case "raise_exception":
                self._apply_error_damage(session, 2)
                self._deal_damage(session, target, 14 + bonus_power)
            case "assert_stmt":
                self._deal_damage(session, target, 7 + bonus_power)
                if target and target.current_hp > 0:
                    player.status_effects["error_shield"] = player.status_effects.get("error_shield", 0) + 1
            case "zip_iter":
                targets = self._living_enemies(session)[:2]
                if target and target not in targets:
                    targets = [target] + targets[:1]
                for enemy in targets:
                    self._deal_damage(session, enemy, 4 + bonus_power)
            case "enumerate_iter":
                self._deal_damage(session, target, 3 + bonus_power)
                self._draw_cards(session, 2 if card_state.upgraded else 1)
            case _:
                raise ValueError(f"Unhandled card effect: {card_id}")
        self._log(session, f"Played {definition.name}.")

    def _enemy_turn(self, session: GameSessionModel) -> None:
        session.player_state.status_effects["type_tax"] = {}
        for enemy in self._living_enemies(session):
            self._apply_enemy_effect(session, enemy)
            enemy.status_effects["weak"] = max(0, enemy.status_effects.get("weak", 0) - 1)
        for card in self._sorted_cards(session, CardZone.HAND.value):
            card.zone = CardZone.DISCARD.value
        self._normalize_zone_positions(session)
        self._log(session, "Enemy turn resolved.")

    def _apply_enemy_effect(self, session: GameSessionModel, enemy: EnemyStateModel) -> None:
        player = session.player_state
        if player.status_effects.get("block_next_error", 0) > 0:
            player.status_effects["block_next_error"] -= 1
            self._log(session, f"{enemy.name} was blocked by try/except.")
            return
        match enemy.enemy_id:
            case "syntax_error":
                self._apply_error_damage(session, 4)
                self._add_type_tax(player, CardType.CONTROL.value, cpu=1)
            case "type_error":
                self._apply_error_damage(session, 5)
                self._disable_random_card(session, CardType.DATA.value)
            case "memory_error":
                self._apply_error_damage(session, 3)
                player.status_effects["next_turn_ram_penalty"] = player.status_effects.get("next_turn_ram_penalty", 0) + 1
            case "timeout_error":
                self._apply_error_damage(session, 2)
                player.status_effects["next_turn_cpu_penalty"] = player.status_effects.get("next_turn_cpu_penalty", 0) + 1
            case "key_error":
                if player.status_effects.get("error_shield", 0) > 0:
                    player.status_effects["error_shield"] -= 1
                    self._log(session, "KeyError consumed 1 shield.")
                else:
                    self._apply_error_damage(session, 4)
            case "recursion_error":
                self._apply_error_damage(session, 2 + session.turn_number)
            case "import_error":
                self._apply_error_damage(session, 3)
                self._add_type_tax(player, CardType.ASYNC.value, cpu=1)
            case _:
                self._apply_error_damage(session, 3)

    def _update_enemy_intents(self, session: GameSessionModel) -> None:
        for enemy in self._living_enemies(session):
            match enemy.enemy_id:
                case "syntax_error":
                    enemy.intent = {"label": "Parse Break", "details": "4 damage and control cards cost +1 CPU."}
                case "type_error":
                    enemy.intent = {"label": "Bad Cast", "details": "5 damage and disables a data card."}
                case "memory_error":
                    enemy.intent = {"label": "Heap Spike", "details": "3 damage and next turn RAM -1."}
                case "timeout_error":
                    enemy.intent = {"label": "Slow Request", "details": "2 damage and next turn CPU -1."}
                case "key_error":
                    enemy.intent = {"label": "Missing Key", "details": "Consumes a shield first, else 4 damage."}
                case "recursion_error":
                    enemy.intent = {"label": "Infinite Stack", "details": f"{2 + session.turn_number} scaling damage."}
                case "import_error":
                    enemy.intent = {"label": "Dependency Crash", "details": "3 damage and async cards cost +1 CPU."}

    def _check_battle_end(self, session: GameSessionModel) -> None:
        if session.player_state.current_errors <= 0:
            session.phase = SessionPhase.GAME_OVER.value
            session.status = "defeat"
            self._log(session, "The interpreter crashed.")
            return
        if not self._living_enemies(session) and session.phase == SessionPhase.BATTLE.value:
            session.phase = SessionPhase.REWARD.value
            session.status = "victory"
            reward_rng = random.Random(session.seed + session.turn_number)
            session.player_state.reward_state = {
                "card_choice_used": False,
                "remove_used": False,
                "upgrade_used": False,
                "reward_options": reward_rng.sample(list(CARD_LIBRARY.keys()), k=3),
            }
            self._log(session, "Battle cleared. Reward phase unlocked.")

    def _resolve_queued_actions(self, session: GameSessionModel, immediate: bool = False) -> None:
        queued = session.player_state.status_effects.get("queued_actions", [])
        remaining = []
        for action in queued:
            if immediate or action["turn"] <= session.turn_number:
                target = self._select_target(session, action.get("target_enemy_id"), allow_fallback=True)
                if target:
                    virtual_card = CardStateModel(card_id=action["card_id"], zone=CardZone.HAND.value, position=0, upgraded=False, temporary=True)
                    self._resolve_card_effect(session, virtual_card, action["card_id"], target, action.get("power", 0))
            else:
                remaining.append(action)
        session.player_state.status_effects["queued_actions"] = remaining

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
                self._log(session, f"Shield blocked {blocked} damage.")
        if amount > 0:
            player.current_errors = max(0, player.current_errors - amount)
            self._log(session, f"Took {amount} Error damage.")

    def _heal_player(self, session: GameSessionModel, amount: int) -> None:
        player = session.player_state
        player.current_errors = min(player.max_errors, player.current_errors + amount)

    def _deal_damage(self, session: GameSessionModel, enemy: EnemyStateModel | None, amount: int) -> None:
        if not enemy or enemy.current_hp <= 0:
            return
        effective_damage = amount + (1 if enemy.status_effects.get("weak", 0) and amount > 0 else 0)
        enemy.current_hp = max(0, enemy.current_hp - effective_damage)
        self._log(session, f"{enemy.name} took {effective_damage} damage.")

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
        raise ValueError("Select a target enemy.")

    def _random_other_enemy(self, session: GameSessionModel, excluded_enemy_id: int | None) -> EnemyStateModel | None:
        options = [enemy for enemy in self._living_enemies(session) if enemy.id != excluded_enemy_id]
        return random.choice(options) if options else None

    def _disable_random_card(self, session: GameSessionModel, card_type: str) -> None:
        candidates = [card for card in self._sorted_cards(session, CardZone.HAND.value) if CARD_LIBRARY[card.card_id].card_type.value == card_type]
        if candidates:
            candidates[0].disabled_until_turn = session.turn_number + 1
            self._log(session, f"{CARD_LIBRARY[candidates[0].card_id].name} was disabled.")

    def _add_type_tax(self, player: PlayerStateModel, card_type: str, cpu: int = 0, ram: int = 0) -> None:
        taxes = player.status_effects.get("type_tax", {})
        taxes.setdefault(card_type, {"cpu": 0, "ram": 0})
        taxes[card_type]["cpu"] += cpu
        taxes[card_type]["ram"] += ram
        player.status_effects["type_tax"] = taxes

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
