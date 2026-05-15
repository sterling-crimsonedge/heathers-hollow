// main.js — input, networking, chat UI, time-of-day driving.
//
// Loads the world from scene.js, connects to the Python AI server over
// WebSocket, runs the player around with WASD/mouse/gamepad, opens chat
// when near a villager, and pipes streamed dialogue back to the screen.

import * as THREE from "three";
import { buildScene } from "./scene.js";

// --- Config -----------------------------------------------------------

const SERVER_HTTP = "http://localhost:8765";
const SERVER_WS   = "ws://localhost:8765/ws";

const TALK_RADIUS = 2.4;
const PLAYER_SPEED = 4.5;
const PLAYER_RUN_MULTIPLIER = 1.8;
const CAMERA_FOLLOW_HEIGHT = 6.5;
const CAMERA_FOLLOW_DISTANCE = 8.5;

const GIFT_OPTIONS = [
  "sunflower", "marigold", "tomato", "book", "tea leaves",
  "lavender", "pebble", "fresh bread", "ribbon",
];


// --- DOM refs ---------------------------------------------------------

const canvas         = document.getElementById("canvas");
const hudClock       = document.getElementById("hud-clock");
const hudClockDot    = document.getElementById("hud-clock-dot");
const hudSubtitle    = document.getElementById("hud-subtitle");
const promptBar      = document.getElementById("hud-bottom-center");
const promptText     = document.getElementById("prompt-text");
const connDot        = document.getElementById("conn-dot");
const connText       = document.getElementById("conn-text");
const chatPanel      = document.getElementById("chat-panel");
const chatLog        = document.getElementById("chat-log");
const chatNameEl     = document.getElementById("chat-name");
const chatInput      = document.getElementById("chat-input");
const chatSendBtn    = document.getElementById("chat-send");
const chatGiftBtn    = document.getElementById("chat-gift");
const chatCloseBtn   = document.getElementById("chat-close");
const giftMenu       = document.getElementById("gift-menu");
const nameModal      = document.getElementById("name-modal");
const nameForm       = document.getElementById("name-form");
const nameInput      = document.getElementById("name-input");
const nameSkip       = document.getElementById("name-skip");

// --- Scene -----------------------------------------------------------

const world = buildScene(canvas);
const { scene, camera, renderer, player, villagerMeshes,
        setSky, spawnVillager, step } = world;

// Reusable vectors to avoid GC
const _v3a = new THREE.Vector3();
const _v3b = new THREE.Vector3();


// --- App state -------------------------------------------------------

const state = {
  villagers: {},          // id -> { name, color, spawn, mesh }
  nearbyVillager: null,   // id or null
  chatOpen: false,
  chatVillagerId: null,
  awaitingReplyEnd: false,
  inputHasFocus: false,
  playerName: null,
  worldTOD: "morning",
  worldLight: 1.0,
  ws: null,
  wsConnected: false,
  cameraYaw: 0,           // radians, mouse-driven
  cameraPitch: -0.25,
};


// --- WebSocket -------------------------------------------------------

function connect() {
  setConn(false, "connecting…");
  const ws = new WebSocket(SERVER_WS);
  state.ws = ws;

  ws.addEventListener("open", () => {
    setConn(true, "connected");
  });

  ws.addEventListener("close", () => {
    setConn(false, "disconnected — retrying…");
    state.wsConnected = false;
    setTimeout(connect, 2000);
  });

  ws.addEventListener("error", () => {
    setConn(false, "server offline");
  });

  ws.addEventListener("message", (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    handleServerMessage(msg);
  });
}

function send(obj) {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(obj));
  }
}

function setConn(ok, text) {
  state.wsConnected = ok;
  connDot.classList.toggle("ok", ok);
  connText.textContent = text;
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case "ready":
      if (msg.world) applyWorldState(msg.world);
      if (msg.villagers) ingestVillagers(msg.villagers);
      if (msg.player_name) {
        state.playerName = msg.player_name;
        nameModal.style.display = "none";
      } else if (state.playerName === null) {
        nameModal.style.display = "flex";
        setTimeout(() => nameInput.focus(), 50);
      }
      if (msg.claude_live === false) {
        appendSystemLine("(note: claude CLI not on the server's PATH — villagers will give canned responses. Install Claude Code to enable real chats.)");
      }
      break;

    case "world_tick":
      if (msg.world) applyWorldState(msg.world);
      break;

    case "greeting_chunk":
    case "reply_chunk":
      streamIntoLog(msg.villager, msg.text);
      break;

    case "greeting_end":
    case "reply_end":
      finishStreamingLine();
      state.awaitingReplyEnd = false;
      break;

    case "summary":
      // optional: could show as fade-in toast. Skip for MVP.
      break;

    case "name_set":
      state.playerName = msg.name;
      nameModal.style.display = "none";
      break;

    case "error":
      appendSystemLine(`error: ${msg.message}`);
      break;
  }
}


// --- Villagers -------------------------------------------------------

function ingestVillagers(list) {
  for (const v of list) {
    state.villagers[v.id] = v;
    if (!villagerMeshes[v.id]) {
      spawnVillager(v.id, v.name, v.color, v.spawn[0], v.spawn[1]);
    }
  }
}


// --- World tick (time of day) ----------------------------------------

function applyWorldState(w) {
  if (w.in_game_time) hudClock.textContent = w.in_game_time;
  if (w.time_of_day) {
    state.worldTOD = w.time_of_day;
    hudSubtitle.textContent = phraseFor(w.time_of_day);
  }
  if (w.light_intensity !== undefined) state.worldLight = w.light_intensity;
  if (w.sky_color) hudClockDot.style.background = w.sky_color;
  setSky(state.worldTOD, state.worldLight);
}

function phraseFor(tod) {
  return {
    dawn:      "first light",
    morning:   "a quiet morning",
    midday:    "warm midday",
    afternoon: "lazy afternoon",
    evening:   "golden hour",
    night:     "lantern-lit night",
  }[tod] || "a quiet day";
}


// --- Input -----------------------------------------------------------

const keys = new Set();
window.addEventListener("keydown", (e) => {
  if (e.repeat) return;

  // Esc closes chat or unfocuses input
  if (e.key === "Escape") {
    if (state.chatOpen) closeChat();
    return;
  }

  // While chat input has focus, only forward send/exit
  if (state.inputHasFocus) {
    if (e.key === "Enter") { sendChat(); }
    return;
  }

  keys.add(e.key.toLowerCase());

  if ((e.key === "e" || e.key === " ") && state.nearbyVillager && !state.chatOpen) {
    openChat(state.nearbyVillager);
  }
});
window.addEventListener("keyup", (e) => { keys.delete(e.key.toLowerCase()); });

// Mouse look — click-drag rotates the camera around player
let dragging = false;
let lastMouseX = 0, lastMouseY = 0;
canvas.addEventListener("mousedown", (e) => {
  dragging = true; lastMouseX = e.clientX; lastMouseY = e.clientY;
});
window.addEventListener("mouseup", () => { dragging = false; });
window.addEventListener("mousemove", (e) => {
  if (!dragging) return;
  const dx = e.clientX - lastMouseX;
  const dy = e.clientY - lastMouseY;
  lastMouseX = e.clientX; lastMouseY = e.clientY;
  state.cameraYaw   -= dx * 0.005;
  state.cameraPitch -= dy * 0.003;
  state.cameraPitch  = Math.max(-1.0, Math.min(0.4, state.cameraPitch));
});

// Gamepad polling
function pollGamepad(dt) {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  for (const pad of pads) {
    if (!pad) continue;
    // Left stick → movement
    const lx = deadzone(pad.axes[0]);
    const lz = deadzone(pad.axes[1]);
    // Right stick → camera
    const rx = deadzone(pad.axes[2] ?? 0);
    const ry = deadzone(pad.axes[3] ?? 0);
    if (rx) state.cameraYaw   -= rx * 2.5 * dt;
    if (ry) state.cameraPitch -= ry * 1.5 * dt;
    state.cameraPitch = Math.max(-1.0, Math.min(0.4, state.cameraPitch));

    // Movement gets injected into a synthetic input vector
    state._padMove = { x: lx, z: lz };

    // Buttons: Nintendo layout — 0:B, 1:A, 2:Y, 3:X (in Chrome via Switch Pro)
    const prev = state._padButtons || [];
    pad.buttons.forEach((b, i) => {
      const wasDown = prev[i] === true;
      if (b.pressed && !wasDown) {
        onGamepadButtonDown(i);
      }
    });
    state._padButtons = pad.buttons.map(b => b.pressed);
    return; // first gamepad only
  }
  state._padMove = null;
}

function deadzone(v, t = 0.15) {
  return Math.abs(v) < t ? 0 : v;
}

function onGamepadButtonDown(idx) {
  // Standard mapping (with Switch Pro on Chrome these match Nintendo positions)
  switch (idx) {
    case 1: // A — interact
      if (state.nearbyVillager && !state.chatOpen) openChat(state.nearbyVillager);
      break;
    case 0: // B — close chat / back
      if (state.chatOpen) closeChat();
      break;
    case 3: // X — quick gift
      if (state.chatOpen) toggleGiftMenu();
      break;
    case 2: // Y — inventory (placeholder)
      break;
  }
}


// --- Chat ------------------------------------------------------------

function openChat(villagerId) {
  state.chatOpen = true;
  state.chatVillagerId = villagerId;
  state.awaitingReplyEnd = true;
  chatLog.replaceChildren();
  chatNameEl.textContent = state.villagers[villagerId]?.name ?? villagerId;
  chatPanel.classList.add("open");
  setTimeout(() => chatInput.focus(), 80);
  send({ type: "begin", villager: villagerId });
}

function closeChat() {
  if (!state.chatOpen) return;
  send({ type: "end", villager: state.chatVillagerId });
  chatPanel.classList.remove("open");
  giftMenu.classList.remove("open");
  state.chatOpen = false;
  state.chatVillagerId = null;
  state.awaitingReplyEnd = false;
  chatInput.blur();
}

function sendChat() {
  const text = chatInput.value.trim();
  if (!text || !state.chatVillagerId || state.awaitingReplyEnd) return;
  appendPlayerLine(text);
  chatInput.value = "";
  state.awaitingReplyEnd = true;
  send({ type: "say", villager: state.chatVillagerId, text });
}

chatInput.addEventListener("focus", () => { state.inputHasFocus = true; });
chatInput.addEventListener("blur",  () => { state.inputHasFocus = false; });
chatSendBtn.addEventListener("click", sendChat);
chatCloseBtn.addEventListener("click", closeChat);
chatGiftBtn.addEventListener("click", toggleGiftMenu);

function toggleGiftMenu() {
  if (!state.chatOpen) return;
  giftMenu.classList.toggle("open");
}

// Build gift menu
for (const item of GIFT_OPTIONS) {
  const btn = document.createElement("div");
  btn.className = "gift-item";
  btn.textContent = item;
  btn.addEventListener("click", () => {
    if (!state.chatVillagerId || state.awaitingReplyEnd) return;
    appendSystemLine(`you offer a ${item}.`);
    state.awaitingReplyEnd = true;
    giftMenu.classList.remove("open");
    send({ type: "gift", villager: state.chatVillagerId, item });
  });
  giftMenu.appendChild(btn);
}

// --- Chat log helpers ------------------------------------------------

let _currentVillagerLine = null;

function appendPlayerLine(text) {
  const div = document.createElement("div");
  div.className = "chat-line player";
  div.textContent = "you: " + text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function appendSystemLine(text) {
  const div = document.createElement("div");
  div.className = "chat-line system";
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function streamIntoLog(villagerId, chunk) {
  if (!_currentVillagerLine) {
    _currentVillagerLine = document.createElement("div");
    _currentVillagerLine.className = "chat-line villager";
    const name = state.villagers[villagerId]?.name ?? villagerId;
    _currentVillagerLine.textContent = `${name}: `;
    chatLog.appendChild(_currentVillagerLine);
  }
  _currentVillagerLine.textContent += chunk;
  chatLog.scrollTop = chatLog.scrollHeight;
}

function finishStreamingLine() {
  _currentVillagerLine = null;
}


// --- Name modal ------------------------------------------------------

nameForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = nameInput.value.trim();
  if (!name) return;
  await submitName(name);
});
nameSkip.addEventListener("click", () => { nameModal.style.display = "none"; });

async function submitName(name) {
  try {
    await fetch(`${SERVER_HTTP}/player/name`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    state.playerName = name;
    nameModal.style.display = "none";
  } catch (e) {
    console.warn("Could not save name to server:", e);
    state.playerName = name;
    nameModal.style.display = "none";
  }
}


// --- Game loop -------------------------------------------------------

const clock = new THREE.Clock();

function loop() {
  const dt = Math.min(0.05, clock.getDelta());
  const t  = clock.elapsedTime;

  pollGamepad(dt);

  if (!state.chatOpen) updatePlayer(dt);

  updateCamera();
  updateNearbyPrompt();
  step(dt, t);

  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}


function updatePlayer(dt) {
  // build movement vector in world space, relative to camera yaw
  let mx = 0, mz = 0;

  // keyboard
  if (keys.has("w") || keys.has("arrowup"))    mz -= 1;
  if (keys.has("s") || keys.has("arrowdown"))  mz += 1;
  if (keys.has("a") || keys.has("arrowleft"))  mx -= 1;
  if (keys.has("d") || keys.has("arrowright")) mx += 1;

  // gamepad
  if (state._padMove) {
    mx += state._padMove.x;
    mz += state._padMove.z;
  }

  const mag = Math.hypot(mx, mz);
  if (mag < 0.01) return;
  mx /= mag; mz /= mag;

  // rotate by camera yaw so forward = away from camera
  const cosY = Math.cos(state.cameraYaw);
  const sinY = Math.sin(state.cameraYaw);
  const worldX = mx * cosY + mz * sinY;
  const worldZ = -mx * sinY + mz * cosY;

  const running = keys.has("shift");
  const speed = PLAYER_SPEED * (running ? PLAYER_RUN_MULTIPLIER : 1);
  player.position.x += worldX * speed * dt;
  player.position.z += worldZ * speed * dt;

  // face direction of movement
  player.rotation.y = Math.atan2(worldX, worldZ);

  // clamp to disk
  const r = Math.hypot(player.position.x, player.position.z);
  const MAX_R = 55;
  if (r > MAX_R) {
    player.position.x *= MAX_R / r;
    player.position.z *= MAX_R / r;
  }
}


function updateCamera() {
  const px = player.position.x;
  const pz = player.position.z;
  const distance = CAMERA_FOLLOW_DISTANCE;
  const height = CAMERA_FOLLOW_HEIGHT + state.cameraPitch * 4;

  const offX = Math.sin(state.cameraYaw) * distance;
  const offZ = Math.cos(state.cameraYaw) * distance;

  const targetX = px + offX;
  const targetZ = pz + offZ;
  camera.position.x += (targetX - camera.position.x) * 0.12;
  camera.position.z += (targetZ - camera.position.z) * 0.12;
  camera.position.y += (height  - camera.position.y) * 0.12;

  _v3a.set(px, 1.2, pz);
  camera.lookAt(_v3a);
}


function updateNearbyPrompt() {
  let nearest = null;
  let nearestDist = Infinity;
  _v3a.copy(player.position);

  for (const [id, m] of Object.entries(villagerMeshes)) {
    _v3b.copy(m.group.position);
    const d = _v3a.distanceTo(_v3b);
    if (d < nearestDist) {
      nearestDist = d;
      nearest = id;
    }
  }

  if (nearest && nearestDist < TALK_RADIUS) {
    if (state.nearbyVillager !== nearest) {
      state.nearbyVillager = nearest;
      const name = state.villagers[nearest]?.name ?? nearest;
      promptText.textContent = `Talk to ${name}`;
    }
    if (!state.chatOpen) promptBar.classList.add("visible");
    else promptBar.classList.remove("visible");
  } else {
    state.nearbyVillager = null;
    promptBar.classList.remove("visible");
  }
}


// --- Boot ------------------------------------------------------------

(async function boot() {
  // try a REST hit first to fetch villagers if WS isn't up yet
  try {
    const res = await fetch(`${SERVER_HTTP}/villagers`);
    if (res.ok) {
      const data = await res.json();
      ingestVillagers(data.villagers || []);
    }
  } catch {
    seedPlaceholderVillagers();
  }

  try {
    const res = await fetch(`${SERVER_HTTP}/player`);
    if (res.ok) {
      const data = await res.json();
      if (data.name) {
        state.playerName = data.name;
        nameModal.style.display = "none";
      } else {
        nameModal.style.display = "flex";
        setTimeout(() => nameInput.focus(), 50);
      }
    } else {
      nameModal.style.display = "flex";
    }
  } catch {
    nameModal.style.display = "flex";
  }

  connect();
  loop();
})();


function seedPlaceholderVillagers() {
  // Hardcoded fallback so the village isn't empty if the server is offline.
  // Matches the spawn positions in personalities.py.
  ingestVillagers([
    { id: "maple",   name: "Maple",   color: "#E8B4B8", spawn: [-8, -6] },
    { id: "bramble", name: "Bramble", color: "#6F8E68", spawn: [8, -2] },
    { id: "clover",  name: "Clover",  color: "#F2C57C", spawn: [0, 4] },
    { id: "sage",    name: "Sage",    color: "#C9B6E4", spawn: [2, -14] },
  ]);
}
