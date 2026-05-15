// scene.js — Heather's Hollow village world.
//
// Builds the 3D village (ground, paths, buildings, trees, villagers) and
// exposes hooks to update lighting and villager positions from the server's
// world state.
//
// Codex (and future contributors) can enrich this freely — see CODEX-TASK-04
// in BLACKBOARD.md. The contract is:
//   - export `buildScene(canvas)` returns { scene, camera, renderer, player,
//     villagerMeshes, setSky(timeOfDay, intensity), step(dt) }
//   - keep `villagerMeshes` keyed by villager id so main.js can position them
//
// Palette is centralized in PALETTE for visual coherence.

import * as THREE from "three";

export const PALETTE = {
  cream:     0xf5efe0,
  warmIvory: 0xfaf3e3,
  sage:      0xa7c4a0,
  deepSage:  0x6f8e68,
  softBlue:  0xb6d0e2,
  dustyRose: 0xe8b4b8,
  marigold:  0xf2c57c,
  terracotta:0xc97b63,
  wisteria:  0xc9b6e4,
  butter:    0xffe8b0,
  charcoal:  0x3d3a38,
  driftwood: 0xa89c8a,
  stone:     0xc8c3b8,
  grassDark: 0x86a87c,
};

// Sky colors keyed by time-of-day (matches server/world/state.py _SKY_COLORS)
const SKY = {
  dawn:      0xf2c57c,
  morning:   0xb6d0e2,
  midday:    0xa8c8e0,
  afternoon: 0xc9e0e2,
  evening:   0xe8b4b8,
  night:     0x3d3a55,
};

const FOG = {
  dawn:      0xe8c89a,
  morning:   0xd8e2eb,
  midday:    0xc6d6e0,
  afternoon: 0xd6e1e0,
  evening:   0xd6b8b6,
  night:     0x2d2a40,
};

const AMBIENT_INTENSITY_BY_TOD = {
  dawn: 0.55, morning: 0.75, midday: 0.95,
  afternoon: 0.85, evening: 0.55, night: 0.25,
};


export function buildScene(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(SKY.morning);
  scene.fog = new THREE.Fog(FOG.morning, 30, 90);

  const camera = new THREE.PerspectiveCamera(
    52, window.innerWidth / window.innerHeight, 0.1, 200
  );
  camera.position.set(0, 7, 12);
  camera.lookAt(0, 1, 0);

  // --- Lights ---------------------------------------------------------
  const ambient = new THREE.AmbientLight(0xffe8b0, 0.6);
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xffe6b0, 1.0);
  sun.position.set(15, 22, 10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.near = 1;
  sun.shadow.camera.far = 80;
  const SHADOW_SIZE = 35;
  sun.shadow.camera.left   = -SHADOW_SIZE;
  sun.shadow.camera.right  =  SHADOW_SIZE;
  sun.shadow.camera.top    =  SHADOW_SIZE;
  sun.shadow.camera.bottom = -SHADOW_SIZE;
  sun.shadow.bias = -0.0005;
  scene.add(sun);
  scene.add(sun.target);

  const hemi = new THREE.HemisphereLight(0xb6d0e2, 0x86a87c, 0.35);
  scene.add(hemi);

  // --- Ground ---------------------------------------------------------
  const groundGeom = new THREE.CircleGeometry(60, 64);
  const groundMat = new THREE.MeshToonMaterial({ color: PALETTE.sage });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // a slightly-darker grass patch under the village core to add depth
  const corePatch = new THREE.Mesh(
    new THREE.CircleGeometry(22, 48),
    new THREE.MeshToonMaterial({ color: PALETTE.grassDark }),
  );
  corePatch.rotation.x = -Math.PI / 2;
  corePatch.position.y = 0.01;
  corePatch.receiveShadow = true;
  scene.add(corePatch);

  // --- Paths (driftwood color, curving from each building to center) --
  addPath(scene, [0,0], [-8,-6]); // to garden
  addPath(scene, [0,0], [8,-2]);  // to shop
  addPath(scene, [0,0], [-2,10]); // to player house
  addPath(scene, [0,0], [2,-14]); // to Sage's hill

  // --- Buildings ------------------------------------------------------
  // Garden patch (Maple's domain)
  addGardenPatch(scene, -8, -6);

  // The Shop (Bramble)
  addCottage(scene, 8, -2, {
    width: 5, depth: 4, wallColor: PALETTE.cream, roofColor: PALETTE.terracotta,
    accentColor: PALETTE.deepSage, sign: "Shop",
  });

  // Player's House
  addCottage(scene, -2, 10, {
    width: 4, depth: 4, wallColor: PALETTE.warmIvory, roofColor: PALETTE.dustyRose,
    accentColor: PALETTE.sage,
  });

  // Sage's Hill (small mound + bench)
  addHill(scene, 2, -14);

  // --- Trees scattered around perimeter -------------------------------
  const treeSpots = [
    [-18, 4], [-14, -16], [-22, -2], [-20, 12], [-10, 18],
    [12, 18], [20, 8], [22, -6], [18, -18], [-2, -22], [10, -20],
    [-4, 22], [6, 22], [-26, 6], [26, 14], [-16, 20],
  ];
  for (const [x, z] of treeSpots) {
    addTree(scene, x, z, 0.85 + Math.random() * 0.5, Math.random() > 0.85);
  }

  // --- Town square fountain (simple — Codex may enhance) --------------
  addFountain(scene, 0, 0);

  // --- Player --------------------------------------------------------
  const player = makePlayerMesh();
  player.position.set(0, 0, 6);
  scene.add(player);

  // --- Villager meshes (populated by main.js with positions) ----------
  const villagerMeshes = {}; // id -> { group, body, label }

  // --- API ------------------------------------------------------------
  function setSky(timeOfDay, intensity) {
    const skyColor = SKY[timeOfDay] ?? SKY.midday;
    const fogColor = FOG[timeOfDay] ?? FOG.midday;
    scene.background = new THREE.Color(skyColor);
    if (scene.fog) scene.fog.color = new THREE.Color(fogColor);

    const amb = AMBIENT_INTENSITY_BY_TOD[timeOfDay] ?? 0.75;
    ambient.intensity = amb;
    sun.intensity = Math.max(0.05, (intensity ?? 1.0) * 0.9);

    // gently warm the sun at dawn/evening, cool at midday
    if (timeOfDay === "dawn" || timeOfDay === "evening") {
      sun.color.setHex(0xffc88a);
    } else if (timeOfDay === "night") {
      sun.color.setHex(0x9aa6cf);
    } else {
      sun.color.setHex(0xffe6b0);
    }
  }

  function spawnVillager(id, name, colorHex, x, z) {
    const group = makeVillagerMesh(colorHex);
    group.position.set(x, 0, z);
    scene.add(group);

    const label = makeFloatingLabel(name);
    label.position.set(0, 2.4, 0);
    group.add(label);

    const mesh = { group, label, name };
    villagerMeshes[id] = mesh;
    return mesh;
  }

  function step(dt, t) {
    // gentle idle motion on villagers
    for (const v of Object.values(villagerMeshes)) {
      v.group.position.y = Math.sin(t * 1.3 + v.group.position.x) * 0.04;
      // billboard the labels toward the camera
      v.label.quaternion.copy(camera.quaternion);
    }
    // breathe the player
    if (player) {
      player.scale.y = 1 + Math.sin(t * 4) * 0.012;
    }
  }

  // --- Resize handling ------------------------------------------------
  window.addEventListener("resize", () => {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
  });

  return { scene, camera, renderer, player, villagerMeshes,
           setSky, spawnVillager, step };
}


// --- Builders ---------------------------------------------------------

function addPath(scene, from, to) {
  const [x1, z1] = from;
  const [x2, z2] = to;
  const dx = x2 - x1;
  const dz = z2 - z1;
  const length = Math.sqrt(dx*dx + dz*dz);
  const angle = Math.atan2(dz, dx);
  const path = new THREE.Mesh(
    new THREE.PlaneGeometry(length, 1.6),
    new THREE.MeshToonMaterial({ color: PALETTE.driftwood }),
  );
  path.rotation.x = -Math.PI / 2;
  path.rotation.z = -angle;
  path.position.set((x1 + x2) / 2, 0.02, (z1 + z2) / 2);
  path.receiveShadow = true;
  scene.add(path);
}

function addCottage(scene, x, z, opts) {
  const { width = 4, depth = 4, wallColor, roofColor, accentColor } = opts;
  const group = new THREE.Group();

  // walls
  const walls = new THREE.Mesh(
    new THREE.BoxGeometry(width, 2.6, depth),
    new THREE.MeshToonMaterial({ color: wallColor }),
  );
  walls.position.y = 1.3;
  walls.castShadow = true;
  walls.receiveShadow = true;
  group.add(walls);

  // roof — a cone scaled to a pyramid feel
  const roof = new THREE.Mesh(
    new THREE.ConeGeometry(width * 0.85, 1.8, 4),
    new THREE.MeshToonMaterial({ color: roofColor }),
  );
  roof.position.y = 2.6 + 0.9;
  roof.rotation.y = Math.PI / 4;
  roof.castShadow = true;
  group.add(roof);

  // door
  const door = new THREE.Mesh(
    new THREE.BoxGeometry(0.8, 1.4, 0.1),
    new THREE.MeshToonMaterial({ color: accentColor }),
  );
  door.position.set(0, 0.7, depth / 2 + 0.06);
  group.add(door);

  // window squares
  const winMat = new THREE.MeshToonMaterial({ color: PALETTE.butter });
  for (const sx of [-1, 1]) {
    const win = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.6, 0.1), winMat);
    win.position.set(sx * (width/2 - 0.6), 1.6, depth/2 + 0.06);
    group.add(win);
  }

  group.position.set(x, 0, z);
  scene.add(group);
}

function addGardenPatch(scene, x, z) {
  const group = new THREE.Group();
  // dirt patch
  const dirt = new THREE.Mesh(
    new THREE.CircleGeometry(3.2, 32),
    new THREE.MeshToonMaterial({ color: 0x9b7e62 }),
  );
  dirt.rotation.x = -Math.PI / 2;
  dirt.position.y = 0.02;
  dirt.receiveShadow = true;
  group.add(dirt);

  // a few "flowers" as tiny colored cylinders
  const flowerColors = [PALETTE.dustyRose, PALETTE.marigold, PALETTE.wisteria];
  for (let i = 0; i < 14; i++) {
    const c = flowerColors[i % flowerColors.length];
    const stem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.04, 0.35),
      new THREE.MeshToonMaterial({ color: PALETTE.deepSage }),
    );
    const bloom = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 12, 12),
      new THREE.MeshToonMaterial({ color: c }),
    );
    const angle = Math.random() * Math.PI * 2;
    const radius = Math.random() * 2.6;
    const fx = Math.cos(angle) * radius;
    const fz = Math.sin(angle) * radius;
    stem.position.set(fx, 0.2, fz);
    bloom.position.set(fx, 0.42, fz);
    stem.castShadow = true;
    bloom.castShadow = true;
    group.add(stem);
    group.add(bloom);
  }
  group.position.set(x, 0, z);
  scene.add(group);
}

function addTree(scene, x, z, scale = 1, cherry = false) {
  const group = new THREE.Group();
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.25, 0.32, 1.4),
    new THREE.MeshToonMaterial({ color: 0x8a6a4f }),
  );
  trunk.position.y = 0.7;
  trunk.castShadow = true;
  group.add(trunk);

  const canopyColor = cherry ? PALETTE.dustyRose : PALETTE.deepSage;
  // Layered spheres for that puffy AC look
  for (let i = 0; i < 3; i++) {
    const r = 1.0 - i * 0.15;
    const ball = new THREE.Mesh(
      new THREE.SphereGeometry(r, 16, 16),
      new THREE.MeshToonMaterial({ color: canopyColor }),
    );
    ball.position.set(
      (Math.random() - 0.5) * 0.4,
      1.7 + i * 0.55,
      (Math.random() - 0.5) * 0.4,
    );
    ball.castShadow = true;
    group.add(ball);
  }

  group.scale.setScalar(scale);
  group.rotation.y = Math.random() * Math.PI * 2;
  group.position.set(x, 0, z);
  scene.add(group);
}

function addHill(scene, x, z) {
  const hill = new THREE.Mesh(
    new THREE.SphereGeometry(5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2.6),
    new THREE.MeshToonMaterial({ color: PALETTE.grassDark }),
  );
  hill.position.set(x, 0, z);
  hill.castShadow = true;
  hill.receiveShadow = true;
  scene.add(hill);

  // a lone tree on top
  addTree(scene, x, z, 1.2, false);

  // tiny bench
  const bench = new THREE.Mesh(
    new THREE.BoxGeometry(1.6, 0.18, 0.5),
    new THREE.MeshToonMaterial({ color: PALETTE.driftwood }),
  );
  bench.position.set(x + 1.4, 1.4, z);
  bench.castShadow = true;
  scene.add(bench);
}

function addFountain(scene, x, z) {
  const group = new THREE.Group();
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(1.4, 1.6, 0.4, 24),
    new THREE.MeshToonMaterial({ color: PALETTE.stone }),
  );
  base.position.y = 0.2;
  base.castShadow = true;
  base.receiveShadow = true;
  group.add(base);

  const water = new THREE.Mesh(
    new THREE.CylinderGeometry(1.25, 1.25, 0.1, 24),
    new THREE.MeshToonMaterial({ color: PALETTE.softBlue }),
  );
  water.position.y = 0.42;
  group.add(water);

  const center = new THREE.Mesh(
    new THREE.CylinderGeometry(0.15, 0.2, 0.9, 12),
    new THREE.MeshToonMaterial({ color: PALETTE.cream }),
  );
  center.position.y = 0.85;
  group.add(center);

  group.position.set(x, 0, z);
  scene.add(group);
}


// --- Characters -------------------------------------------------------

function makePlayerMesh() {
  const group = new THREE.Group();
  // body (a cream pinafore-feel cylinder)
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.36, 0.42, 1.1, 16),
    new THREE.MeshToonMaterial({ color: PALETTE.warmIvory }),
  );
  body.position.y = 0.55;
  body.castShadow = true;
  group.add(body);
  // head
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.45, 24, 24),
    new THREE.MeshToonMaterial({ color: 0xf4d6b8 }), // skin tone (placeholder)
  );
  head.position.y = 1.4;
  head.castShadow = true;
  group.add(head);
  // hair tuft
  const hair = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 24, 24, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshToonMaterial({ color: 0x6b4f3a }),
  );
  hair.position.y = 1.55;
  group.add(hair);

  return group;
}

function makeVillagerMesh(colorHex) {
  const group = new THREE.Group();
  const color = parseInt(colorHex.replace("#", "0x"), 16);

  // body — colored
  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(0.42, 0.48, 1.05, 16),
    new THREE.MeshToonMaterial({ color }),
  );
  body.position.y = 0.55;
  body.castShadow = true;
  group.add(body);

  // head — cream
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 24, 24),
    new THREE.MeshToonMaterial({ color: PALETTE.warmIvory }),
  );
  head.position.y = 1.45;
  head.castShadow = true;
  group.add(head);

  // tiny dot eyes (charcoal, just for charm)
  const eyeGeom = new THREE.SphereGeometry(0.05, 10, 10);
  const eyeMat = new THREE.MeshBasicMaterial({ color: PALETTE.charcoal });
  for (const sx of [-0.16, 0.16]) {
    const eye = new THREE.Mesh(eyeGeom, eyeMat);
    eye.position.set(sx, 1.5, 0.45);
    group.add(eye);
  }

  // blush spots
  const blushMat = new THREE.MeshBasicMaterial({ color: PALETTE.dustyRose });
  for (const sx of [-0.28, 0.28]) {
    const blush = new THREE.Mesh(new THREE.SphereGeometry(0.08, 10, 10), blushMat);
    blush.position.set(sx, 1.42, 0.42);
    group.add(blush);
  }

  // signature accent (a little hat-bobble in their color)
  const accent = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 16, 16),
    new THREE.MeshToonMaterial({ color }),
  );
  accent.position.y = 1.92;
  group.add(accent);

  return group;
}

function makeFloatingLabel(text) {
  // Build a canvas texture for the label
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 80;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgba(245, 239, 224, 0.92)";
  roundRect(ctx, 4, 12, canvas.width - 8, 56, 28);
  ctx.fill();
  ctx.fillStyle = "#3d3a38";
  ctx.font = "600 28px 'Iowan Old Style', Georgia, serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, canvas.width / 2, 40);

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(2.2, 0.7, 1);
  return sprite;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}
