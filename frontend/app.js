const API_BASE = "http://localhost:8000";

const state = {
    sessionId: null,
    game: null,
    socket: null,
    selectedEnemyId: null,
    passiveChoices: [],
};

const elements = {
    startBtn: document.getElementById("start-game-btn"),
    endTurnBtn: document.getElementById("end-turn-btn"),
    cpu: document.getElementById("cpu-value"),
    ram: document.getElementById("ram-value"),
    errors: document.getElementById("errors-value"),
    shield: document.getElementById("shield-value"),
    runMeta: document.getElementById("run-meta"),
    levelMeta: document.getElementById("level-meta"),
    connectionStatus: document.getElementById("connection-status"),
    battleLog: document.getElementById("battle-log"),
    enemies: document.getElementById("enemies"),
    hand: document.getElementById("hand"),
    pileMeta: document.getElementById("pile-meta"),
    rewardSection: document.getElementById("reward-section"),
    deckCards: document.getElementById("deck-cards"),
    passives: document.getElementById("passives"),
    passiveChoices: document.getElementById("passive-choices"),
};

async function request(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "Request failed." }));
        throw new Error(error.detail || "Request failed.");
    }
    return response.json();
}

async function fetchPassives() {
    state.passiveChoices = await request("/game/passives");
    renderPassives();
}

async function startGame() {
    const game = await request("/game/start", {
        method: "POST",
        body: JSON.stringify({}),
    });
    setGameState(game);
    connectSocket();
}

async function endTurn() {
    if (!state.sessionId) return;
    await request("/game/end-turn", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId }),
    });
}

async function playCard(cardId) {
    if (!state.sessionId) return;
    const card = state.game.hand.find((entry) => entry.instance_id === cardId);
    if (!card) return;
    const targetEnemyId = card.requires_target ? (state.selectedEnemyId || state.game.enemies[0]?.instance_id || null) : null;
    await request("/game/play-card", {
        method: "POST",
        body: JSON.stringify({
            session_id: state.sessionId,
            card_instance_id: cardId,
            target_enemy_id: targetEnemyId,
        }),
    });
}

async function chooseReward(cardId) {
    await request("/game/reward/choose-card", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, reward_card_id: cardId }),
    });
}

async function removeDeckCard(cardInstanceId) {
    await request("/game/reward/remove-card", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, card_instance_id: cardInstanceId }),
    });
}

async function upgradeDeckCard(cardInstanceId) {
    await request("/game/reward/upgrade-card", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, card_instance_id: cardInstanceId }),
    });
}

async function choosePassive(passiveId) {
    await request("/game/reward/choose-passive", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, passive_id: passiveId }),
    });
}

function connectSocket() {
    if (!state.sessionId) return;
    if (state.socket) {
        state.socket.close();
    }
    const socket = new WebSocket(`ws://localhost:8000/game/ws?session_id=${state.sessionId}`);
    state.socket = socket;
    elements.connectionStatus.textContent = "connecting";
    socket.addEventListener("open", () => {
        elements.connectionStatus.textContent = "live";
    });
    socket.addEventListener("message", (event) => {
        setGameState(JSON.parse(event.data));
    });
    socket.addEventListener("close", () => {
        elements.connectionStatus.textContent = "offline";
    });
}

function setGameState(game) {
    state.game = game;
    state.sessionId = game.session_id;
    if (!game.enemies.some((enemy) => enemy.instance_id === state.selectedEnemyId)) {
        state.selectedEnemyId = game.enemies[0]?.instance_id || null;
    }
    render();
}

function render() {
    const game = state.game;
    if (!game) return;

    elements.cpu.textContent = `${game.player.cpu} / ${game.player.max_cpu}`;
    elements.ram.textContent = `${game.player.ram} / ${game.player.max_ram}`;
    elements.errors.textContent = `${game.player.errors} / ${game.player.max_errors}`;
    elements.shield.textContent = `${game.player.error_shield}`;
    elements.runMeta.textContent = `Turn ${game.turn_number} | ${game.phase} | ${game.status}`;
    const modifierCopy = game.level.modifiers.map((modifier) => `${modifier.name}: ${modifier.description}`).join(" | ");
    elements.levelMeta.textContent = `${game.level.level_type} | ${modifierCopy}`;
    elements.pileMeta.textContent = `Draw ${game.draw_pile} / Discard ${game.discard_pile} / Exhaust ${game.exhaust_pile}`;
    elements.endTurnBtn.disabled = game.phase !== "battle";

    elements.battleLog.innerHTML = game.log.map((entry) => `<div class="log-entry">${escapeHtml(entry)}</div>`).join("");
    elements.passives.innerHTML = game.player.passives.length
        ? game.player.passives.map((passive) => `<span class="pill">${escapeHtml(passive.name)}</span>`).join("")
        : `<span class="meta-copy">No passives installed yet.</span>`;

    elements.enemies.innerHTML = game.enemies.length
        ? game.enemies.map(renderEnemy).join("")
        : `<div class="meta-copy">No enemies remain.</div>`;
    elements.hand.innerHTML = game.hand.length
        ? game.hand.map((card) => renderCard(card, "play")).join("")
        : `<div class="meta-copy">Hand is empty.</div>`;
    elements.rewardSection.innerHTML = renderRewardSection(game);
    elements.deckCards.innerHTML = game.deck_cards.length
        ? game.deck_cards.map((card) => renderCard(card, "deck")).join("")
        : `<div class="meta-copy">Deck is empty.</div>`;

    attachHandlers();
    renderPassives();
}

function renderEnemy(enemy) {
    const width = Math.max(0, (enemy.hp / enemy.max_hp) * 100);
    const selectedClass = enemy.instance_id === state.selectedEnemyId ? "selected" : "";
    return `
        <button class="enemy-card ${selectedClass}" data-enemy-id="${enemy.instance_id}">
            <h3>${escapeHtml(enemy.name)}</h3>
            <div>${enemy.hp} / ${enemy.max_hp} HP</div>
            <div class="hp-bar"><span style="width: ${width}%"></span></div>
            <div class="intent">${escapeHtml(enemy.intent.label)}: ${escapeHtml(enemy.intent.details)}</div>
        </button>
    `;
}

function renderCard(card, mode) {
    const disabled = card.disabled || (mode === "play" && state.game.phase !== "battle");
    const tags = card.synergy_tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
    const actions = mode === "play"
        ? `<button data-play-card="${card.instance_id}" ${disabled ? "disabled" : ""}>Play</button>`
        : `
            <div class="inline-actions">
                <button class="danger" data-remove-card="${card.instance_id}" ${!state.game.reward_state.can_remove_card || state.game.phase !== "reward" ? "disabled" : ""}>Remove</button>
                <button data-upgrade-card="${card.instance_id}" ${!state.game.reward_state.can_upgrade_card || state.game.phase !== "reward" ? "disabled" : ""}>Upgrade</button>
            </div>
        `;
    return `
        <article class="code-card ${disabled ? "disabled" : ""}">
            <div>
                <h3>${escapeHtml(card.name)} ${card.upgraded ? "+" : ""}</h3>
                <div class="card-meta">
                    <span>${escapeHtml(card.card_type)}</span>
                    <span>CPU ${card.cpu_cost}</span>
                    <span>RAM ${card.ram_cost}</span>
                </div>
            </div>
            <pre>${escapeHtml(card.snippet)}</pre>
            <p class="meta-copy">${escapeHtml(card.description)}</p>
            <div class="tags">${tags}</div>
            ${actions}
        </article>
    `;
}

function renderRewardSection(game) {
    if (game.phase !== "reward") {
        return `<div class="meta-copy">Rewards unlock after you clear the battle.</div>`;
    }
    return game.reward_state.reward_options.map((card) => `
        <article class="code-card">
            <div>
                <h3>${escapeHtml(card.name)}</h3>
                <div class="card-meta">
                    <span>${escapeHtml(card.card_type)}</span>
                    <span>CPU ${card.cpu_cost}</span>
                    <span>RAM ${card.ram_cost}</span>
                </div>
            </div>
            <pre>${escapeHtml(card.snippet)}</pre>
            <p class="meta-copy">${escapeHtml(card.description)}</p>
            <button data-reward-card="${card.card_id}" ${!game.reward_state.can_choose_card ? "disabled" : ""}>Add To Deck</button>
        </article>
    `).join("");
}

function renderPassives() {
    if (!state.game || state.game.phase !== "reward") {
        elements.passiveChoices.innerHTML = "";
        return;
    }
    elements.passiveChoices.innerHTML = state.passiveChoices.map((passive) => `
        <button class="pill" data-passive-id="${passive.id}" ${state.game.player.passives.some((owned) => owned.id === passive.id) ? "disabled" : ""}>
            ${escapeHtml(passive.name)}
        </button>
    `).join("");
}

function attachHandlers() {
    document.querySelectorAll("[data-enemy-id]").forEach((button) => {
        button.addEventListener("click", () => {
            state.selectedEnemyId = Number(button.dataset.enemyId);
            render();
        });
    });
    document.querySelectorAll("[data-play-card]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await playCard(Number(button.dataset.playCard));
            } catch (error) {
                alert(error.message);
            }
        });
    });
    document.querySelectorAll("[data-reward-card]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await chooseReward(button.dataset.rewardCard);
            } catch (error) {
                alert(error.message);
            }
        });
    });
    document.querySelectorAll("[data-remove-card]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await removeDeckCard(Number(button.dataset.removeCard));
            } catch (error) {
                alert(error.message);
            }
        });
    });
    document.querySelectorAll("[data-upgrade-card]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await upgradeDeckCard(Number(button.dataset.upgradeCard));
            } catch (error) {
                alert(error.message);
            }
        });
    });
    document.querySelectorAll("[data-passive-id]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                await choosePassive(button.dataset.passiveId);
            } catch (error) {
                alert(error.message);
            }
        });
    });
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

elements.startBtn.addEventListener("click", async () => {
    try {
        await startGame();
    } catch (error) {
        alert(error.message);
    }
});

elements.endTurnBtn.addEventListener("click", async () => {
    try {
        await endTurn();
    } catch (error) {
        alert(error.message);
    }
});

fetchPassives().catch(() => {
    elements.connectionStatus.textContent = "backend unavailable";
});
