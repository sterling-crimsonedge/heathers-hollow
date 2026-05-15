import { createVillageScene } from "./scene.js";

const SERVER_HTTP = window.HOLLOW_SERVER_HTTP || "http://127.0.0.1:8765";
const SERVER_WS = window.HOLLOW_SERVER_WS || "ws://127.0.0.1:8765/ws/conversation";
const PLAYER_ID = "heather";
const CLIENT_ID = "web_demo";

const FALLBACK_VILLAGERS = [
  {
    id: "margot",
    display_name: "Margot",
    species: "rabbit",
    archetype: "gentle ceramicist",
    home_location: "town_square",
    likes: ["flowers", "porcelain", "soft colors"],
  },
  {
    id: "fern",
    display_name: "Fern",
    species: "deer",
    archetype: "shy herbalist",
    home_location: "garden",
    likes: ["tea", "quiet gardens", "pressed leaves"],
  },
  {
    id: "hugo",
    display_name: "Hugo",
    species: "bear",
    archetype: "gruff baker",
    home_location: "shop",
    likes: ["bread", "warm ovens", "reliable routines"],
  },
  {
    id: "clover",
    display_name: "Clover",
    species: "fox",
    archetype: "bright collector",
    home_location: "brook",
    likes: ["marigolds", "buttons", "small treasures"],
  },
];

// Mirrors `server/world/inventory.py:STARTER_INVENTORY` so the web demo's
// offline / server-offline fallback still surfaces every canonical starter
// gift, including the four HH-062 cast-specific items each canonical
// villager scores as "loved". Keep this list in sync with the server
// catalog; the gift picker hint copy below leans on `category` and
// `gift_prompt` to guide intentional picks.
const FALLBACK_INVENTORY = [
  {
    item_id: "dusty_rose",
    display_name: "Dusty Rose",
    category: "flower",
    tags: ["flower", "garden", "soft_color", "handmade"],
    gift_prompt: "A soft dusty rose picked from Heather's garden.",
  },
  {
    item_id: "chamomile_bundle",
    display_name: "Chamomile Bundle",
    category: "herb",
    tags: ["flower", "tea", "garden", "handmade"],
    gift_prompt: "A small bundle of chamomile tied with cotton thread.",
  },
  {
    item_id: "porcelain_button",
    display_name: "Porcelain Button",
    category: "keepsake",
    tags: ["porcelain", "handmade", "soft_color"],
    gift_prompt: "A tiny glazed porcelain button with a pale blue flower.",
  },
  {
    item_id: "smooth_pebble",
    display_name: "Smooth Pebble",
    category: "trinket",
    tags: ["stone", "smooth", "pocket"],
    gift_prompt: "A small smooth pebble from the path near the garden.",
  },
  {
    item_id: "lavender_sachet",
    display_name: "Lavender Sachet",
    category: "herb",
    tags: ["herb", "lavender", "handmade", "soft_color"],
    gift_prompt: "A small linen sachet of dried lavender, hand-stitched closed.",
  },
  {
    item_id: "honey_oat_crust",
    display_name: "Honey Oat Crust",
    category: "baked",
    tags: ["bread", "baked", "warm", "handmade"],
    gift_prompt: "A small heel of warm honey oat bread saved from this morning's bake.",
  },
  {
    item_id: "marigold_sprig",
    display_name: "Marigold Sprig",
    category: "flower",
    tags: ["flower", "marigold", "orange", "garden"],
    gift_prompt: "A bright orange marigold sprig with one slightly bent petal.",
  },
  {
    item_id: "sea_glass_shard",
    display_name: "Sea Glass Shard",
    category: "trinket",
    tags: ["shiny", "broken", "keepsake", "smooth", "sea"],
    gift_prompt: "A frosted shard of pale-green sea glass smoothed by saltwater.",
  },
];

const dom = {
  canvas: document.getElementById("village-canvas"),
  subtitle: document.getElementById("subtitle"),
  worldLine: document.getElementById("world-line"),
  statusDot: document.getElementById("status-dot"),
  serverLine: document.getElementById("server-line"),
  villagerList: document.getElementById("villager-list"),
  offlineNote: document.getElementById("offline-note"),
  contextContent: document.getElementById("context-content"),
  chatName: document.getElementById("chat-name"),
  chatMeta: document.getElementById("chat-meta"),
  chatLog: document.getElementById("chat-log"),
  memoryCue: document.getElementById("memory-cue"),
  giftRow: document.getElementById("gift-row"),
  interactionPrompt: document.getElementById("interaction-prompt"),
  composer: document.getElementById("composer"),
  messageInput: document.getElementById("message-input"),
  sendButton: document.getElementById("send-button"),
  refreshContext: document.getElementById("refresh-context"),
  welcomeOverlay: document.getElementById("welcome-overlay"),
  welcomeBegin: document.getElementById("welcome-begin"),
};

const state = {
  world: { day: 1, clock: "08:00", time_label: "morning", season: "spring", weather: "clear" },
  villagers: [],
  villagersById: {},
  inventory: FALLBACK_INVENTORY,
  contextsByVillagerId: {},
  activeVillagerId: "",
  nearbyVillagerId: "",
  serverOnline: false,
  socketOnline: false,
  socket: null,
  reconnectTimer: 0,
  pendingReply: false,
  chatHistoryByVillagerId: {},
  keys: new Set(),
  welcomeDismissed: false,
};

// Keys that count as a "first move" — pressing any of these auto-dismisses
// the welcome overlay so a confident player never has to read it twice.
const WELCOME_DISMISS_KEYS = new Set([
  "w", "a", "s", "d",
  "arrowup", "arrowdown", "arrowleft", "arrowright",
]);

const scene = createVillageScene(dom.canvas, {
  onVillagerClick: (villagerId) => selectVillager(villagerId, { refreshContext: true }),
  onNearbyChange: (villagerId) => {
    state.nearbyVillagerId = villagerId;
    if (villagerId && !state.activeVillagerId) {
      selectVillager(villagerId, { refreshContext: true, focusInput: false });
    }
    renderVillagers();
    renderChatChrome();
    renderInteractionPrompt();
  },
});

init();

async function init() {
  installWelcomeOverlay();
  installInputHandlers();
  scene.setWorld(state.world);
  scene.setVillagers(FALLBACK_VILLAGERS);
  scene.start();
  renderAll();
  await loadBootstrap();
  connectSocket();
  requestAnimationFrame(inputLoop);
}

function installWelcomeOverlay() {
  if (!dom.welcomeOverlay) return;
  if (new URLSearchParams(window.location.search).get("skip_welcome") === "1") {
    dismissWelcome();
    return;
  }
  if (dom.welcomeBegin) {
    dom.welcomeBegin.addEventListener("click", () => {
      dismissWelcome();
      dom.messageInput.focus({ preventScroll: true });
    });
    // Land focus on the Begin button so keyboard-first and screen-reader
    // visitors hear the dialog announcement and can press Enter to step
    // inside without hunting. requestAnimationFrame waits past the
    // initial layout so the focus actually takes; we re-check
    // welcomeDismissed in case the player has already moved.
    requestAnimationFrame(() => {
      if (!state.welcomeDismissed && dom.welcomeBegin) {
        dom.welcomeBegin.focus({ preventScroll: true });
      }
    });
  }
  // Don't dismiss on a stray canvas click while the player is still
  // reading; the Begin button is intentional and the movement/select
  // dismiss paths cover players who skip the overlay.
}

function dismissWelcome() {
  if (state.welcomeDismissed) return;
  state.welcomeDismissed = true;
  if (dom.welcomeOverlay) {
    dom.welcomeOverlay.classList.add("hidden");
    dom.welcomeOverlay.setAttribute("aria-hidden", "true");
  }
}

async function loadBootstrap() {
  try {
    setServerStatus(false, "Loading server state");
    const bootstrap = await fetchJson(
      `${SERVER_HTTP}/client/bootstrap?client_id=${encodeURIComponent(CLIENT_ID)}&player_id=${encodeURIComponent(PLAYER_ID)}&notification_limit=5`
    );
    state.serverOnline = true;
    state.world = bootstrap.world || state.world;
    state.villagers = Array.isArray(bootstrap.villagers) ? bootstrap.villagers : [];
    state.inventory = Array.isArray(bootstrap.inventory?.items) ? bootstrap.inventory.items : FALLBACK_INVENTORY;
    state.villagersById = indexById(state.villagers);
    scene.setWorld(state.world);
    scene.setVillagers(state.villagers);
    setServerStatus(true, "Root server connected");
    renderAll();
  } catch (error) {
    state.serverOnline = false;
    state.villagers = FALLBACK_VILLAGERS;
    state.villagersById = indexById(state.villagers);
    state.inventory = FALLBACK_INVENTORY;
    scene.setVillagers(state.villagers);
    setServerStatus(false, "Server offline");
    dom.offlineNote.hidden = false;
    dom.offlineNote.textContent = "The village view is local. Conversations need the root server on port 8765.";
    renderAll();
  }
}

function connectSocket() {
  clearTimeout(state.reconnectTimer);
  if (state.socket) {
    state.socket.onopen = null;
    state.socket.onclose = null;
    state.socket.onerror = null;
    state.socket.onmessage = null;
    state.socket.close();
  }

  const socket = new WebSocket(SERVER_WS);
  state.socket = socket;
  setSocketStatus(false, state.serverOnline ? "Connecting conversation" : "Server offline");

  socket.onopen = () => {
    state.socketOnline = true;
    setSocketStatus(true, "Conversation ready");
    renderChatChrome();
  };

  socket.onmessage = (event) => {
    try {
      handleServerMessage(JSON.parse(event.data));
    } catch (error) {
      appendSystemMessage("Received an unreadable server message.");
    }
  };

  socket.onerror = () => {
    setSocketStatus(false, "Conversation offline");
  };

  socket.onclose = () => {
    state.socketOnline = false;
    setSocketStatus(false, state.serverOnline ? "Conversation offline" : "Server offline");
    renderChatChrome();
    state.reconnectTimer = window.setTimeout(connectSocket, 2500);
  };
}

function handleServerMessage(message) {
  if (message.type === "server_status") {
    if (message.world) {
      state.world = message.world;
      scene.setWorld(state.world);
      renderWorld();
    }
    return;
  }

  if (message.type === "villager_reply") {
    state.pendingReply = false;
    const villagerId = String(message.villager_id || state.activeVillagerId);
    if (message.world) {
      state.world = message.world;
      scene.setWorld(state.world);
      renderWorld();
    }
    appendMessage(villagerId, "villager", String(message.text || ""));
    renderMemoryCue(message.memories_used);
    if (villagerId) {
      loadVillagerContext(villagerId, { quiet: true });
    }
    renderChatChrome();
    return;
  }

  if (message.type === "error") {
    state.pendingReply = false;
    appendSystemMessage(message.message || "The server could not answer.");
    renderChatChrome();
  }
}

async function loadVillagerContext(villagerId, options = {}) {
  if (!villagerId) return;
  if (!state.serverOnline) {
    if (!options.quiet) renderContext(villagerId);
    return;
  }

  if (!options.quiet) {
    dom.contextContent.className = "empty";
    dom.contextContent.textContent = "Loading context...";
  }

  try {
    const context = await fetchJson(
      `${SERVER_HTTP}/client/villagers/${encodeURIComponent(villagerId)}/context?subject_id=${encodeURIComponent(PLAYER_ID)}&memory_limit=5&event_limit=5`
    );
    state.contextsByVillagerId[villagerId] = context;
    scene.setVillagerStatus(villagerId, contextStatusLine(context));
    if (state.activeVillagerId === villagerId) {
      renderContext(villagerId);
      renderChatChrome();
    }
  } catch (error) {
    if (!options.quiet) {
      dom.contextContent.className = "empty";
      dom.contextContent.textContent = "Context is unavailable while the server is offline.";
    }
  }
}

function selectVillager(villagerId, options = {}) {
  if (!state.villagersById[villagerId]) return;
  // Selecting a villager is a clear "I'm playing now" signal — dismiss
  // the welcome overlay so the chat input is reachable.
  dismissWelcome();
  state.activeVillagerId = villagerId;
  scene.setActiveVillager(villagerId);
  if (!state.chatHistoryByVillagerId[villagerId]) {
    state.chatHistoryByVillagerId[villagerId] = [];
  }
  renderAll();
  if (options.refreshContext !== false) {
    loadVillagerContext(villagerId);
  }
  if (options.focusInput !== false) {
    dom.messageInput.focus();
  }
}

function renderAll() {
  renderWorld();
  renderVillagers();
  renderChatChrome();
  renderInteractionPrompt();
  renderGiftRow();
  renderMessages();
  renderContext(state.activeVillagerId);
}

function renderWorld() {
  const world = state.world || {};
  const day = world.day || 1;
  const clock = world.clock || "";
  const timeLabel = world.time_label || "morning";
  const season = world.season || "spring";
  const weather = world.weather || "clear";
  dom.worldLine.textContent = `Day ${day} | ${clock || timeLabel} | ${season} | ${weather}`;
  dom.subtitle.textContent = state.activeVillagerId
    ? activeVillagerLabel()
    : "The hollow is listening";
}

function renderVillagers() {
  dom.villagerList.replaceChildren();
  for (const villager of state.villagers) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `villager-card${villager.id === state.activeVillagerId ? " active" : ""}`;
    button.addEventListener("click", () => selectVillager(villager.id, { refreshContext: true }));

    const swatch = document.createElement("span");
    swatch.className = "villager-swatch";
    swatch.style.background = villagerColor(villager.id);

    const body = document.createElement("span");
    const name = document.createElement("span");
    name.className = "villager-name";
    name.textContent = villager.display_name || villager.id;
    const meta = document.createElement("span");
    meta.className = "villager-meta";
    meta.textContent = [villager.species, villager.archetype, villager.home_location].filter(Boolean).join(" | ");
    body.append(name, meta);
    if (villager.id === state.nearbyVillagerId) {
      const nearby = document.createElement("span");
      nearby.className = "nearby-chip";
      nearby.textContent = "Nearby";
      body.appendChild(nearby);
    }
    button.append(swatch, body);
    dom.villagerList.appendChild(button);
  }
}

function renderChatChrome() {
  const villager = activeVillager();
  const canSend = Boolean(villager && state.socketOnline && !state.pendingReply);
  dom.chatName.textContent = villager ? villager.display_name : "No villager selected";
  dom.chatMeta.textContent = villager
    ? [villager.species, villager.archetype, relationLine(villager.id)].filter(Boolean).join(" | ")
    : "Conversation will appear here.";
  dom.messageInput.placeholder = villager ? `Say something to ${villager.display_name}` : "Select a villager first";
  dom.messageInput.disabled = !villager || !state.socketOnline;
  dom.sendButton.disabled = !canSend;
  dom.refreshContext.disabled = !villager || !state.serverOnline;
  for (const button of dom.giftRow.querySelectorAll("button")) {
    button.disabled = !canSend;
  }
}

function renderInteractionPrompt() {
  const nearby = state.villagersById[state.nearbyVillagerId];
  if (!nearby || state.activeVillagerId === nearby.id) {
    dom.interactionPrompt.classList.remove("visible");
    dom.interactionPrompt.textContent = "Move near a villager";
    return;
  }
  dom.interactionPrompt.textContent = `Press E, Enter, or controller A to talk with ${nearby.display_name}`;
  dom.interactionPrompt.classList.add("visible");
}

function renderGiftRow() {
  dom.giftRow.replaceChildren();
  for (const item of state.inventory) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "gift-button";
    button.dataset.itemId = item.item_id || "";
    button.dataset.category = item.category || "";

    const name = document.createElement("span");
    name.className = "gift-name";
    name.textContent = item.display_name || item.item_id || "Gift";

    const caption = document.createElement("span");
    caption.className = "gift-caption";
    caption.textContent = item.category || "gift";

    button.append(name, caption);

    // The hover tooltip leans on the server's `gift_prompt`, giving the
    // player a one-line sensory hint so the picker reads as personality
    // rather than a flat list of names.
    const promptHint = String(item.gift_prompt || "").trim();
    if (promptHint) {
      button.title = promptHint;
      button.setAttribute("aria-label", `${name.textContent} - ${promptHint}`);
    } else {
      button.setAttribute("aria-label", name.textContent);
    }

    button.addEventListener("click", () => sendGift(item));
    dom.giftRow.appendChild(button);
  }
}

function renderMessages() {
  dom.chatLog.replaceChildren();
  const history = state.chatHistoryByVillagerId[state.activeVillagerId] || [];
  if (!state.activeVillagerId) {
    appendMessageElement("system", "Select a villager to begin.");
    return;
  }
  if (history.length === 0) {
    appendMessageElement("system", `${activeVillagerLabel()} is nearby.`);
    return;
  }
  for (const message of history) {
    appendMessageElement(message.role, message.text);
  }
}

function renderContext(villagerId) {
  const villager = state.villagersById[villagerId];
  if (!villager) {
    dom.contextContent.className = "empty";
    dom.contextContent.textContent = "Select a villager.";
    return;
  }

  const context = state.contextsByVillagerId[villagerId] || {};
  const relationship = context.relationship || {};
  const memories = Array.isArray(context.memories) ? context.memories : [];
  const events = Array.isArray(context.events) ? context.events : [];
  const sourceVillager = context.villager || villager;

  const blocks = [];
  blocks.push(contextBlock("Profile", [
    sourceVillager.archetype || villager.archetype || "Villager",
    listLine("Traits", sourceVillager.core_traits),
    listLine("Likes", sourceVillager.likes || villager.likes),
  ].filter(Boolean)));

  blocks.push(contextBlock("Relationship", [
    scoreLine("Affection", relationship.affection),
    scoreLine("Trust", relationship.trust),
    scoreLine("Familiarity", relationship.familiarity),
    scoreLine("Tension", relationship.tension),
  ].filter(Boolean)));

  blocks.push(contextListBlock("Recent Memories", memories.map((memory) => memory.text).slice(0, 5)));
  blocks.push(contextListBlock("Recent Events", events.map((event) => event.summary).slice(0, 5)));

  dom.contextContent.className = "";
  dom.contextContent.innerHTML = blocks.join("");
}

function renderMemoryCue(memoriesUsed) {
  const count = Array.isArray(memoriesUsed) ? memoriesUsed.length : 0;
  if (!count) {
    dom.memoryCue.classList.remove("visible");
    dom.memoryCue.textContent = "";
    return;
  }
  dom.memoryCue.textContent = `Remembered ${count} ${count === 1 ? "thing" : "things"}`;
  dom.memoryCue.classList.add("visible");
}

function appendMessage(villagerId, role, text) {
  if (!villagerId) return;
  if (!state.chatHistoryByVillagerId[villagerId]) {
    state.chatHistoryByVillagerId[villagerId] = [];
  }
  state.chatHistoryByVillagerId[villagerId].push({ role, text });
  if (state.activeVillagerId === villagerId) {
    appendMessageElement(role, text);
  }
}

function appendSystemMessage(text) {
  appendMessageElement("system", text);
}

function appendMessageElement(role, text) {
  const line = document.createElement("div");
  line.className = `message ${role}`;
  line.textContent = text;
  dom.chatLog.appendChild(line);
  dom.chatLog.scrollTop = dom.chatLog.scrollHeight;
}

function installInputHandlers() {
  window.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    // ESC dismisses the welcome overlay even before the player moves.
    if (key === "escape" && !state.welcomeDismissed) {
      dismissWelcome();
      return;
    }
    // The very first walk-around keypress auto-dismisses the welcome
    // overlay so a confident player never has to click the button.
    if (!state.welcomeDismissed && WELCOME_DISMISS_KEYS.has(key)) {
      dismissWelcome();
    }
    const typing = document.activeElement === dom.messageInput;
    if (typing) return;
    state.keys.add(key);
    if ((event.key === "e" || event.key === " " || event.key === "Enter") && state.nearbyVillagerId) {
      event.preventDefault();
      selectVillager(state.nearbyVillagerId, { refreshContext: true });
    }
  });

  window.addEventListener("keyup", (event) => {
    state.keys.delete(event.key.toLowerCase());
  });

  dom.composer.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage();
  });

  dom.refreshContext.addEventListener("click", () => {
    if (state.activeVillagerId) {
      loadVillagerContext(state.activeVillagerId);
    }
  });
}

function inputLoop() {
  const vector = keyboardVector();
  const padVector = gamepadVector();
  if (padVector) {
    vector.x = padVector.x;
    vector.z = padVector.z;
  }
  scene.setInputVector(vector);
  requestAnimationFrame(inputLoop);
}

function keyboardVector() {
  let x = 0;
  let z = 0;
  if (state.keys.has("a") || state.keys.has("arrowleft")) x -= 1;
  if (state.keys.has("d") || state.keys.has("arrowright")) x += 1;
  if (state.keys.has("w") || state.keys.has("arrowup")) z -= 1;
  if (state.keys.has("s") || state.keys.has("arrowdown")) z += 1;
  return normalizeVector({ x, z });
}

function gamepadVector() {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  for (const pad of pads) {
    if (!pad) continue;
    const x = deadzone(pad.axes[0] || 0);
    const z = deadzone(pad.axes[1] || 0);
    const previous = state.padButtons || [];
    const pressed = pad.buttons.map((button) => button.pressed);
    if (pressed[1] && !previous[1] && state.nearbyVillagerId) {
      selectVillager(state.nearbyVillagerId, { refreshContext: true });
    }
    state.padButtons = pressed;
    return normalizeVector({ x, z });
  }
  state.padButtons = [];
  return null;
}

function sendMessage() {
  const text = dom.messageInput.value.trim();
  const villager = activeVillager();
  if (!text || !villager || !state.socketOnline || state.pendingReply) return;

  dom.messageInput.value = "";
  dom.memoryCue.classList.remove("visible");
  appendMessage(villager.id, "player", text);
  state.pendingReply = true;
  renderChatChrome();

  sendSocket({
    type: "player_message",
    player_id: PLAYER_ID,
    villager_id: villager.id,
    text,
    context: interactionContext(villager, { interaction: "talk" }),
  });
}

function sendGift(item) {
  const villager = activeVillager();
  if (!villager || !state.socketOnline || state.pendingReply) return;

  const displayName = item.display_name || item.item_id || "gift";
  dom.memoryCue.classList.remove("visible");
  appendMessage(villager.id, "player", `Gave ${displayName}`);
  state.pendingReply = true;
  renderChatChrome();

  sendSocket({
    type: "gift_item",
    player_id: PLAYER_ID,
    villager_id: villager.id,
    item,
    context: interactionContext(villager, { gift_source: "starter_inventory" }),
  });
}

function sendSocket(payload) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    state.pendingReply = false;
    appendSystemMessage("Conversation is offline.");
    renderChatChrome();
    return;
  }
  state.socket.send(JSON.stringify(payload));
}

function interactionContext(villager, extra = {}) {
  return {
    location: villager.home_location || "town_square",
    client_time: state.world.time_label || "morning",
    world: {
      day: state.world.day,
      clock: state.world.clock,
      time_label: state.world.time_label,
      season: state.world.season,
      weather: state.world.weather,
    },
    ...extra,
  };
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function setServerStatus(ok, text) {
  state.serverOnline = ok;
  dom.statusDot.classList.toggle("ok", ok && state.socketOnline);
  dom.serverLine.textContent = text;
}

function setSocketStatus(ok, text) {
  state.socketOnline = ok;
  dom.statusDot.classList.toggle("ok", ok);
  dom.serverLine.textContent = text;
}

function activeVillager() {
  return state.villagersById[state.activeVillagerId] || null;
}

function activeVillagerLabel() {
  const villager = activeVillager();
  return villager ? `${villager.display_name} near ${villager.home_location || "town square"}` : "The hollow is listening";
}

function relationLine(villagerId) {
  const relationship = state.contextsByVillagerId[villagerId]?.relationship;
  if (!relationship) return "";
  const tone = relationshipTone(relationship);
  return `${tone} | affection ${safeNumber(relationship.affection)} trust ${safeNumber(relationship.trust)}`;
}

function contextStatusLine(context) {
  const relationship = context?.relationship || {};
  const mood = relationship.metadata?.current_mood || context?.villager?.mood || "";
  const tone = relationshipTone(relationship);
  return mood ? `${tone}, ${mood}` : tone;
}

function relationshipTone(relationship) {
  const affection = Number(relationship.affection || 0);
  const trust = Number(relationship.trust || 0);
  const tension = Number(relationship.tension || 0);
  if (tension >= 6) return "strained";
  if (affection >= 18 && trust >= 14) return "close";
  if (affection >= 9 || trust >= 9) return "warm";
  if (affection <= -3) return "distant";
  return "new";
}

function contextBlock(title, lines) {
  const body = lines.length
    ? lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("")
    : `<p class="empty">No public context yet.</p>`;
  return `<section class="context-block"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function contextListBlock(title, rows) {
  const cleanRows = rows.filter(Boolean);
  const body = cleanRows.length
    ? `<ul>${cleanRows.map((row) => `<li>${escapeHtml(row)}</li>`).join("")}</ul>`
    : `<p class="empty">Nothing recorded yet.</p>`;
  return `<section class="context-block"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function listLine(label, values) {
  if (!Array.isArray(values) || values.length === 0) return "";
  return `${label}: ${values.join(", ")}`;
}

function scoreLine(label, value) {
  if (value === undefined || value === null) return "";
  return `${label}: ${safeNumber(value)}`;
}

function safeNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? String(number) : "?";
}

function indexById(list) {
  const indexed = {};
  for (const item of list) {
    if (item?.id) indexed[item.id] = item;
  }
  return indexed;
}

function normalizeVector(vector) {
  const length = Math.hypot(vector.x, vector.z);
  if (length > 1) {
    return { x: vector.x / length, z: vector.z / length };
  }
  return vector;
}

function deadzone(value, threshold = 0.18) {
  return Math.abs(value) < threshold ? 0 : value;
}

function villagerColor(id) {
  return {
    margot: "#c9838b",
    fern: "#6f8e68",
    hugo: "#b7785f",
    clover: "#d7b65d",
  }[id] || "#88a9bf";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
