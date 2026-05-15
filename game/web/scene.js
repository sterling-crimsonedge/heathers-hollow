const LOCATION_POINTS = {
  town_square: { x: 0, z: 0 },
  garden: { x: -7, z: 3 },
  shop: { x: 7, z: -1 },
  player_house: { x: -1, z: 8 },
  // Brook is Clover's home base — chipped saucer found in the brook, marigold
  // bank, halfway between Margot and Hugo so the cast-doc triangles read.
  brook: { x: 4, z: 5 },
};

const DEFAULT_VILLAGER_POINTS = [
  { x: -1.8, z: -1.2 },
  { x: -7.4, z: 2.2 },
  { x: 7.6, z: -2.4 },
  { x: 1.8, z: 1.5 },
];

const VILLAGER_COLORS = {
  margot: "#c9838b",
  fern: "#6f8e68",
  hugo: "#b7785f",
  clover: "#d7b65d",
};

const TIME_SKIES = {
  dawn: ["#e9b98a", "#f7e6c6"],
  morning: ["#b9d6e5", "#f7ebd8"],
  midday: ["#a8cfe5", "#f8f0df"],
  afternoon: ["#c2d9d1", "#f6e4c5"],
  evening: ["#d9a7aa", "#f2d5bb"],
  night: ["#34395f", "#a5adc9"],
};

export function createVillageScene(canvas, hooks = {}) {
  return new VillageScene(canvas, hooks);
}

class VillageScene {
  constructor(canvas, hooks) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.hooks = hooks;
    this.pixelRatio = 1;
    this.width = 0;
    this.height = 0;
    this.scale = 34;
    this.player = { x: 0, z: 5.5, radius: 0.55 };
    this.input = { x: 0, z: 0 };
    this.velocity = { x: 0, z: 0 };
    this.facing = { x: 0, z: -1 };
    this.villagers = [];
    this.villagerStatusById = {};
    this.world = { time_label: "morning", season: "spring", weather: "clear" };
    this.activeVillagerId = "";
    this.nearbyVillagerId = "";
    this.lastTime = 0;
    this.running = false;

    this.canvas.addEventListener("click", (event) => this.handleClick(event));
    window.addEventListener("resize", () => this.resize());
    this.resize();
  }

  start() {
    if (this.running) return;
    this.running = true;
    requestAnimationFrame((time) => this.frame(time));
  }

  setWorld(world) {
    this.world = { ...this.world, ...(world || {}) };
  }

  setVillagers(villagers) {
    const list = Array.isArray(villagers) ? villagers : [];
    this.villagers = list.map((villager, index) => {
      const location = villager.home_location || "town_square";
      const anchor = LOCATION_POINTS[location] || DEFAULT_VILLAGER_POINTS[index % DEFAULT_VILLAGER_POINTS.length];
      const offset = DEFAULT_VILLAGER_POINTS[index % DEFAULT_VILLAGER_POINTS.length];
      return {
        id: String(villager.id || `villager_${index}`),
        display_name: String(villager.display_name || villager.name || "Villager"),
        species: String(villager.species || ""),
        archetype: String(villager.archetype || ""),
        home_location: location,
        color: VILLAGER_COLORS[villager.id] || colorFromId(String(villager.id || index)),
        status: this.villagerStatusById[villager.id] || "",
        x: anchor.x + offset.x * 0.18,
        z: anchor.z + offset.z * 0.18,
      };
    });
  }

  setVillagerStatus(villagerId, status) {
    const id = String(villagerId || "");
    if (!id) return;
    this.villagerStatusById[id] = String(status || "");
    const villager = this.villagers.find((item) => item.id === id);
    if (villager) {
      villager.status = this.villagerStatusById[id];
    }
  }

  setActiveVillager(villagerId) {
    this.activeVillagerId = villagerId || "";
  }

  setInputVector(vector) {
    const x = Number(vector?.x || 0);
    const z = Number(vector?.z || 0);
    const length = Math.hypot(x, z);
    if (length > 1) {
      this.input = { x: x / length, z: z / length };
    } else {
      this.input = { x, z };
    }
  }

  getNearbyVillagerId(radius = 2.35) {
    let best = null;
    let bestDistance = radius;
    for (const villager of this.villagers) {
      const distance = Math.hypot(villager.x - this.player.x, villager.z - this.player.z);
      if (distance < bestDistance) {
        best = villager.id;
        bestDistance = distance;
      }
    }
    return best || "";
  }

  resize() {
    this.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = Math.floor(this.width * this.pixelRatio);
    this.canvas.height = Math.floor(this.height * this.pixelRatio);
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
    this.scale = Math.max(26, Math.min(42, Math.min(this.width, this.height) / 18));
  }

  frame(time) {
    const dt = Math.min(0.05, (time - this.lastTime) / 1000 || 0.016);
    this.lastTime = time;
    this.update(dt);
    this.draw(time / 1000);
    requestAnimationFrame((nextTime) => this.frame(nextTime));
  }

  update(dt) {
    const speed = 4.2;
    const smoothing = Math.min(1, dt * 9);
    const targetX = this.input.x * speed;
    const targetZ = this.input.z * speed;
    this.velocity.x = lerp(this.velocity.x, targetX, smoothing);
    this.velocity.z = lerp(this.velocity.z, targetZ, smoothing);
    this.player.x = clamp(this.player.x + this.velocity.x * dt, -13, 13);
    this.player.z = clamp(this.player.z + this.velocity.z * dt, -10, 12);
    if (Math.hypot(this.velocity.x, this.velocity.z) > 0.05) {
      this.facing = normalize({ x: this.velocity.x, z: this.velocity.z });
    }

    const nearby = this.getNearbyVillagerId();
    if (nearby !== this.nearbyVillagerId) {
      this.nearbyVillagerId = nearby;
      if (typeof this.hooks.onNearbyChange === "function") {
        this.hooks.onNearbyChange(nearby);
      }
    }
  }

  handleClick(event) {
    const rect = this.canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    for (const villager of this.villagers) {
      const screen = this.toScreen(villager.x, villager.z);
      if (Math.hypot(screen.x - x, screen.y - y) <= 32 && typeof this.hooks.onVillagerClick === "function") {
        this.hooks.onVillagerClick(villager.id);
        return;
      }
    }
  }

  draw(time) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);
    this.drawSky(ctx);
    this.drawGround(ctx);
    this.drawVillage(ctx, time);
  }

  drawSky(ctx) {
    const sky = TIME_SKIES[this.world.time_label] || TIME_SKIES.morning;
    const gradient = ctx.createLinearGradient(0, 0, 0, this.height);
    gradient.addColorStop(0, sky[0]);
    gradient.addColorStop(0.58, sky[1]);
    gradient.addColorStop(1, "#d5c69f");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, this.width, this.height);

    const night = this.world.time_label === "night";
    ctx.save();
    ctx.globalAlpha = night ? 0.9 : 0.78;
    ctx.fillStyle = night ? "#fff5cf" : "#f2c57c";
    ctx.beginPath();
    ctx.arc(this.width * 0.78, this.height * 0.16, night ? 20 : 30, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    this.drawCloud(ctx, this.width * 0.18, this.height * 0.17, 1.05);
    this.drawCloud(ctx, this.width * 0.44, this.height * 0.11, 0.72);
  }

  drawGround(ctx) {
    const center = this.toScreen(0, 0);
    ctx.save();
    ctx.translate(center.x, center.y + this.scale * 0.8);
    ctx.scale(1.25, 0.58);
    ctx.fillStyle = "#93ad84";
    ctx.beginPath();
    ctx.arc(0, 0, this.scale * 12.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255, 250, 240, 0.55)";
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
  }

  drawVillage(ctx, time) {
    this.drawPath(ctx, -1, 8, 0, 0);
    this.drawPath(ctx, -7, 3, 0, 0);
    this.drawPath(ctx, 7, -1, 0, 0);

    // Brook is drawn before the village structures so the bank flowers and
    // ripples sit under any villager standing on top of Clover's home tile.
    this.drawBrook(ctx, 4, 5, time);

    this.drawGarden(ctx, -7, 3);
    this.drawHouse(ctx, -1, 8, "#fffaf0", "#c9838b", "Home");
    this.drawHouse(ctx, 7, -1, "#f7ead0", "#b7785f", "Shop");
    this.drawFountain(ctx, 0, 0, time);
    this.drawFlowerBed(ctx, -3.8, 5.8, "#c9838b");
    this.drawFlowerBed(ctx, 4.2, 2.8, "#f0c672");
    this.drawLantern(ctx, -2.3, 0.9, time);
    this.drawLantern(ctx, 2.2, -0.7, time);

    const treePoints = [
      [-10, -6], [-12, 2], [-10, 9], [-5, 11], [5, 10], [11, 5],
      [11, -5], [4, -8], [-5, -8], [0, 12], [13, 1], [-13, -2],
    ];
    for (const [x, z] of treePoints) {
      this.drawTree(ctx, x, z);
    }

    const actors = [
      ...this.villagers.map((villager) => ({ type: "villager", z: villager.z, data: villager })),
      { type: "player", z: this.player.z, data: this.player },
    ].sort((a, b) => a.z - b.z);

    for (const actor of actors) {
      if (actor.type === "player") this.drawPlayer(ctx, actor.data, time);
      else this.drawVillager(ctx, actor.data, time);
    }
  }

  drawPath(ctx, x1, z1, x2, z2) {
    const start = this.toScreen(x1, z1);
    const end = this.toScreen(x2, z2);
    ctx.save();
    ctx.strokeStyle = "rgba(184, 143, 99, 0.66)";
    ctx.lineWidth = Math.max(18, this.scale * 0.48);
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
    ctx.strokeStyle = "rgba(255, 250, 240, 0.28)";
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.restore();
  }

  drawGarden(ctx, x, z) {
    const p = this.toScreen(x, z);
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.fillStyle = "#7f9d70";
    roundedRect(ctx, -54, -28, 108, 56, 8);
    ctx.fill();
    for (let row = 0; row < 3; row += 1) {
      for (let col = 0; col < 5; col += 1) {
        ctx.fillStyle = row % 2 === 0 ? "#c9838b" : "#f0c672";
        ctx.beginPath();
        ctx.arc(-36 + col * 18, -12 + row * 13, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }

  drawFlowerBed(ctx, x, z, color) {
    const p = this.toScreen(x, z);
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.fillStyle = "rgba(95, 127, 93, 0.45)";
    ctx.beginPath();
    ctx.ellipse(0, 4, 36, 12, 0, 0, Math.PI * 2);
    ctx.fill();
    for (let index = 0; index < 8; index += 1) {
      const px = -24 + index * 7;
      const py = index % 2 === 0 ? -2 : 5;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 3.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffe8b0";
      ctx.beginPath();
      ctx.arc(px, py, 1.3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  drawHouse(ctx, x, z, wallColor, roofColor, label) {
    const p = this.toScreen(x, z);
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.fillStyle = "rgba(70, 61, 53, 0.14)";
    ctx.beginPath();
    ctx.ellipse(0, 32, 58, 17, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = wallColor;
    roundedRect(ctx, -42, -18, 84, 58, 8);
    ctx.fill();
    ctx.fillStyle = roofColor;
    ctx.beginPath();
    ctx.moveTo(-50, -16);
    ctx.lineTo(0, -58);
    ctx.lineTo(50, -16);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#6f5747";
    roundedRect(ctx, -10, 10, 20, 30, 5);
    ctx.fill();
    ctx.fillStyle = "#ffe8b0";
    roundedRect(ctx, -31, 0, 14, 13, 3);
    roundedRect(ctx, 17, 0, 14, 13, 3);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 250, 240, 0.94)";
    ctx.font = "700 11px Avenir Next, Arial";
    ctx.textAlign = "center";
    ctx.fillText(label, 0, 57);
    ctx.restore();
  }

  drawFountain(ctx, x, z, time) {
    const p = this.toScreen(x, z);
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.fillStyle = "#c8c3b8";
    ctx.beginPath();
    ctx.ellipse(0, 8, 38, 18, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#88a9bf";
    ctx.beginPath();
    ctx.ellipse(0, 5, 28, 11, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255, 250, 240, 0.7)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(Math.sin(time) * 5, -10, 9, Math.PI * 0.15, Math.PI * 0.85);
    ctx.stroke();
    ctx.restore();
  }

  drawBrook(ctx, x, z, time) {
    // Clover's home — a soft blue meander between Margot's plaza and Hugo's
    // shop with marigold sprites on the bank. Matches the (4, 5) LOCATION
    // point so Heather can read the cast-doc chipped-saucer beat at a glance.
    const center = this.toScreen(x, z);
    ctx.save();
    ctx.translate(center.x, center.y);

    // Wet earth bank — a darker ellipse that grounds the water and gives
    // the marigolds something to sit on without floating mid-grass.
    ctx.fillStyle = "rgba(112, 92, 70, 0.32)";
    ctx.beginPath();
    ctx.ellipse(0, 4, 78, 30, 0, 0, Math.PI * 2);
    ctx.fill();

    // Brook body — soft S-curve. Two stroked paths in different blues so the
    // brook reads as flowing water and not a flat puddle.
    ctx.strokeStyle = "#88a9bf";
    ctx.lineCap = "round";
    ctx.lineWidth = 16;
    ctx.beginPath();
    ctx.moveTo(-58, 14);
    ctx.bezierCurveTo(-22, -4, -4, 18, 28, -2);
    ctx.bezierCurveTo(44, -10, 56, 6, 70, -6);
    ctx.stroke();

    ctx.strokeStyle = "rgba(255, 250, 240, 0.55)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(-54, 12);
    ctx.bezierCurveTo(-20, -2, -2, 16, 26, -2);
    ctx.bezierCurveTo(42, -10, 54, 4, 66, -6);
    ctx.stroke();

    // A handful of moving ripples so the brook is visibly alive when the
    // demo loop is running. Anchored to `time` like the fountain ripple.
    ctx.strokeStyle = "rgba(255, 250, 240, 0.45)";
    ctx.lineWidth = 1.4;
    const rippleOffset = Math.sin(time * 1.7) * 4;
    for (const [rx, ry, radius] of [
      [-32 + rippleOffset, 8, 7],
      [4 + rippleOffset * 0.6, 4, 6],
      [40 - rippleOffset * 0.4, -2, 7],
    ]) {
      ctx.beginPath();
      ctx.arc(rx, ry, radius, Math.PI * 0.15, Math.PI * 0.85);
      ctx.stroke();
    }

    // Marigold cluster on each bank — the cast doc anchors Clover to a
    // marigold/orange palette, so the brook should echo it. Soft green
    // tufts underneath ground each cluster.
    for (const [bx, by] of [
      [-46, -10],
      [-30, 18],
      [14, -14],
      [34, 16],
      [58, -10],
    ]) {
      ctx.fillStyle = "rgba(95, 127, 93, 0.55)";
      ctx.beginPath();
      ctx.ellipse(bx, by + 3, 9, 3, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#f0a35a";
      ctx.beginPath();
      ctx.arc(bx, by, 3.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffe8b0";
      ctx.beginPath();
      ctx.arc(bx, by, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  drawLantern(ctx, x, z, time) {
    const p = this.toScreen(x, z);
    const glow = this.world.time_label === "night" || this.world.time_label === "evening";
    ctx.save();
    ctx.translate(p.x, p.y);
    if (glow) {
      const gradient = ctx.createRadialGradient(0, -19, 2, 0, -19, 32 + Math.sin(time * 2) * 3);
      gradient.addColorStop(0, "rgba(255, 232, 176, 0.75)");
      gradient.addColorStop(1, "rgba(255, 232, 176, 0)");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(0, -19, 36, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.strokeStyle = "#6b5748";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, -34);
    ctx.lineTo(0, 20);
    ctx.stroke();
    ctx.fillStyle = "#ffe8b0";
    roundedRect(ctx, -8, -34, 16, 19, 4);
    ctx.fill();
    ctx.restore();
  }

  drawTree(ctx, x, z) {
    const p = this.toScreen(x, z);
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.fillStyle = "#7a583c";
    roundedRect(ctx, -5, 5, 10, 27, 4);
    ctx.fill();
    ctx.fillStyle = "#6f8e68";
    ctx.beginPath();
    ctx.arc(0, -13, 26, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 250, 240, 0.25)";
    ctx.beginPath();
    ctx.arc(-8, -22, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  drawPlayer(ctx, player, time) {
    const p = this.toScreen(player.x, player.z);
    const bob = Math.sin(time * 6) * 2;
    ctx.save();
    ctx.translate(p.x, p.y + bob);
    ctx.fillStyle = "rgba(70, 61, 53, 0.18)";
    ctx.beginPath();
    ctx.ellipse(0, 21 - bob, 20, 7, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#88a9bf";
    roundedRect(ctx, -14, -5, 28, 34, 8);
    ctx.fill();
    ctx.fillStyle = "#f5d4bd";
    ctx.beginPath();
    ctx.arc(0, -17, 15, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#6b5748";
    ctx.beginPath();
    ctx.arc(-5, -19, 2, 0, Math.PI * 2);
    ctx.arc(5, -19, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(70, 61, 53, 0.28)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(this.facing.x * 4, -10 + this.facing.z * 2);
    ctx.lineTo(this.facing.x * 14, -10 + this.facing.z * 6);
    ctx.stroke();
    ctx.restore();
  }

  drawVillager(ctx, villager, time) {
    const p = this.toScreen(villager.x, villager.z);
    const active = villager.id === this.activeVillagerId;
    const nearby = villager.id === this.nearbyVillagerId;
    const bob = Math.sin(time * 2.3 + villager.x) * 2;
    ctx.save();
    ctx.translate(p.x, p.y + bob);
    ctx.fillStyle = "rgba(70, 61, 53, 0.18)";
    ctx.beginPath();
    ctx.ellipse(0, 22 - bob, 20, 7, 0, 0, Math.PI * 2);
    ctx.fill();
    if (active || nearby) {
      ctx.strokeStyle = active ? "#c9838b" : "#fffaf0";
      ctx.lineWidth = active ? 4 : 3;
      ctx.beginPath();
      ctx.ellipse(0, 16, 27, 12, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.fillStyle = villager.color;
    roundedRect(ctx, -13, -1, 26, 31, 8);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, -18, 17, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 250, 240, 0.78)";
    ctx.beginPath();
    ctx.arc(-6, -14, 4, 0, Math.PI * 2);
    ctx.arc(6, -14, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#463d35";
    ctx.beginPath();
    ctx.arc(-5, -20, 2, 0, Math.PI * 2);
    ctx.arc(5, -20, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(255, 250, 240, 0.94)";
    ctx.strokeStyle = "rgba(70, 61, 53, 0.22)";
    ctx.lineWidth = 1;
    roundedRect(ctx, -44, -58, 88, 20, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#463d35";
    ctx.font = "700 11px Avenir Next, Arial";
    ctx.textAlign = "center";
    ctx.fillText(villager.display_name, 0, -44);
    if (villager.status) {
      ctx.fillStyle = "rgba(70, 61, 53, 0.84)";
      roundedRect(ctx, -40, -35, 80, 16, 7);
      ctx.fill();
      ctx.fillStyle = "#fffaf0";
      ctx.font = "700 9px Avenir Next, Arial";
      ctx.fillText(truncate(villager.status, 16), 0, -24);
    }
    ctx.restore();
  }

  drawCloud(ctx, x, y, scale) {
    const width = 74 * scale;
    ctx.save();
    ctx.translate(x, y);
    ctx.globalAlpha = 0.38;
    ctx.fillStyle = "#fffaf0";
    ctx.beginPath();
    ctx.ellipse(-width * 0.26, 0, width * 0.25, width * 0.11, 0, 0, Math.PI * 2);
    ctx.ellipse(0, -width * 0.04, width * 0.32, width * 0.14, 0, 0, Math.PI * 2);
    ctx.ellipse(width * 0.28, 0, width * 0.24, width * 0.1, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  toScreen(x, z) {
    const centerX = this.width * 0.52;
    const centerY = this.height * 0.43;
    return {
      x: centerX + (x - z) * this.scale * 0.72,
      y: centerY + (x + z) * this.scale * 0.36,
    };
  }
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function colorFromId(id) {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1) {
    hash = (hash * 31 + id.charCodeAt(index)) >>> 0;
  }
  const palette = ["#c9838b", "#6f8e68", "#88a9bf", "#b7785f", "#d7b65d", "#9c8ac1"];
  return palette[hash % palette.length];
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function lerp(start, end, amount) {
  return start + (end - start) * amount;
}

function normalize(vector) {
  const length = Math.hypot(vector.x, vector.z);
  if (!length) return { x: 0, z: -1 };
  return { x: vector.x / length, z: vector.z / length };
}

function truncate(value, maxLength) {
  const text = String(value || "");
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}.` : text;
}
