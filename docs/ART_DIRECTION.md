# Art Direction — Heather's Hollow

## North star

**Cottagecore kawaii.** A handmade, sun-warmed village that feels like a porcelain music box you could live inside. Soft, rounded, a little storybook, never garish, never edgy.

If a screenshot looks like it could be the cover of a tin of butter cookies, we are on track.

## Inspirations

- **Animal Crossing** — silhouette language (chunky heads, tiny features), scale, friendliness, the way light loves the world.
- **Neko Atsume** — flat-but-charming forms, generous negative space, restraint with detail.
- **Bamboletta dolls** — handmade textile warmth, soft faces with dot-and-blush features, the feeling that someone *made* this with their hands.
- **Porcelain dishware** — floral motifs, glaze, the gentle shine of glazed ceramic, blue-and-cream patterns.
- **Studio Ghibli (especially Totoro & Kiki)** — the way a world feels lived-in and breathing without overwhelming detail.

## Palette

### Primaries (the world)
| Name           | Hex      | Use                                    |
|----------------|----------|----------------------------------------|
| Cream          | `#F5EFE0`| Building walls, paper, default light   |
| Warm Ivory     | `#FAF3E3`| Highlights, sun-touched surfaces       |
| Sage           | `#A7C4A0`| Grass, foliage base, accents           |
| Deep Sage      | `#6F8E68`| Shadowed foliage, trim                 |
| Soft Blue      | `#B6D0E2`| Sky midday, water, calm UI             |

### Accents (the warmth)
| Name           | Hex      | Use                                    |
|----------------|----------|----------------------------------------|
| Dusty Rose     | `#E8B4B8`| Flower petals, fabric, signage         |
| Marigold       | `#F2C57C`| Sunlight, lanterns, ripe vegetables    |
| Terracotta     | `#C97B63`| Roof tiles, pots, baked-clay surfaces  |
| Wisteria       | `#C9B6E4`| Twilight skies, magical accents        |
| Butter         | `#FFE8B0`| Window glow, candlelight               |

### Neutrals & lines
| Name           | Hex      | Use                                    |
|----------------|----------|----------------------------------------|
| Soft Charcoal  | `#3D3A38`| Linework, eyes, deep shadow            |
| Driftwood      | `#A89C8A`| Wood structures, paths, fences         |
| Stone          | `#C8C3B8`| Cobblestone, fountain                  |

### Rules
- **Never pure black, never pure white.** Use Soft Charcoal and Warm Ivory.
- **Saturation cap.** Nothing more saturated than the accent swatches above. Keep the world *gentle*.
- **Always warm.** Even cool colors (Soft Blue, Wisteria) lean slightly warm — no clinical blues or surgical whites.

## Form language

### Silhouettes
- **Rounded everything.** Round buildings, round shoulders, round leaves. Sharp corners only for emphasis (window panes, gable peaks).
- **Bottom-heavy.** Characters and buildings sit firmly on the ground. Wide bases, tapered tops. They feel rooted.
- **Generous proportions.** Heads roughly 1/3 of character height (Animal Crossing scale). Doors a hair too small for the house — like a dollhouse.

### Detail philosophy
- **Coarse detail far, fine detail near.** From a distance, every villager is a colored silhouette. Up close, you see embroidery on their sleeve, freckles, the dirt under Maple's nails.
- **Texture > geometry.** A building wall isn't 47 polygons of plaster — it's a clean form with a soft, hand-painted texture suggesting plaster.
- **Visible "made-ness."** Slight imperfections — a slightly wonky shutter, a hand-painted-feel decal on a planter — make the world feel made-by-hand.

## Character design

### Villagers
- **Body type:** small, soft, with stub limbs. Think felt doll, not action figure.
- **Heads:** large and rounded. Faces use the **dot-and-blush** convention: small black/charcoal dots for eyes, a small mouth, two pink blush ovals on the cheeks. No nose unless it's a tiny suggestion.
- **Hair:** simple silhouettes — Maple has a flowery braid, Bramble has a tuft and round glasses, Clover has wild curls, Sage has a soft bun.
- **Clothing:** layered, textile-feeling. Pinafores, vests, knitwear, simple boots. Tiny patterns are okay if readable.
- **Animation:** light and bouncy. They breathe, they sway, they tilt when they listen. No idle pose is fully still.

### Player
- **Customizable but constrained.** Choose hair color, skin tone, top color, bottom color from a curated palette. Everyone is in the same gentle visual family.

## Environment design

### Buildings
- **Cottage forms.** Pitched roofs, wide eaves, simple geometry. Walls in Cream with a Terracotta roof, optionally Sage or Dusty Rose accents.
- **Windows glow Butter** at night. Lanterns line the path.
- **Plants on every porch.** Window boxes with Marigold and Dusty Rose flowers.
- **Shop:** Bramble's shop has a wooden sign hanging from a wrought-iron bracket — a small book illustrated on it.
- **Player's house:** smallest of the buildings, sage shutters, a porch swing with cream cushions.

### Landscape
- **Ground:** layered sage-greens with marigold flowers and white daisies dotted in. Mowed-but-not-too-mowed feel.
- **Trees:** Sage canopies (oversized round masses), Driftwood trunks. A few "feature" trees with Dusty Rose blossoms (cherry).
- **Paths:** soft Driftwood-colored, slightly winding. Never a straight grid.
- **Fountain:** cream stone basin in the town square, Soft Blue water. Slight bubble animation.

### Sky & lighting
- **Dawn:** Wisteria → Marigold gradient. Long golden shadows.
- **Midday:** Soft Blue overhead, Warm Ivory at the horizon. Sun is gentle, not high-contrast.
- **Golden hour:** Marigold and Dusty Rose flood the world. Everyone looks beautiful.
- **Dusk:** Wisteria with one star. Lanterns ignite.
- **Night:** Wisteria-into-Soft-Charcoal sky, butter-glow windows, lantern pools on the path.

### Weather (post-MVP)
- **Rain:** soft, no thunder. Puddles reflect Wisteria sky. Umbrellas appear.
- **Snow:** Warm Ivory accumulation. Everything quiet. Smoke from chimneys.

## Godot 4 / Three.js shader approach

The same look needs to work in both the eventual Godot client and the Three.js web demo. Both engines support custom shaders; the approach is identical conceptually.

### Core look
1. **Cel-shaded lighting** — flat shading with 2–3 light bands, not smooth gradient. Soft Charcoal in the deepest band, never crushed to black.
2. **Hand-painted textures** — every surface gets a subtly-varying texture, not a flat color. Paint-stroke noise overlay, very low frequency.
3. **No specular on most surfaces** — matte everything. Exception: porcelain accents (fountain, dishware, eyes) get a small specular highlight to suggest glaze.
4. **Soft rim light** — a thin warm rim on the sun-side edge of objects. Sells the cozy-light feel.
5. **Slight palette compression** — global LUT that nudges anything too saturated back into the chosen palette. Keeps the world unified even if asset colors drift.

### Three.js MVP shader plan
- `MeshToonMaterial` with a custom 3-step gradient ramp.
- Vertex displacement noise on foliage for "breathing" motion.
- Skybox: gradient mesh rather than HDRI — pure-color cottagecore.
- Post-processing pass: subtle bloom on bright pixels (lanterns, sun), gentle vignette, slight saturation desaturation.

### Godot MVP shader plan
- Custom `spatial_shader` with cel ramp via texture.
- `WorldEnvironment` with a gradient sky, soft glow, mild SSAO.
- Toon outline on characters via inverted hull (cheap, classic).

## UI

### Dialogue box
- Soft cream rounded rectangle, Soft Charcoal text.
- Villager name in a small Dusty Rose pill above the box.
- Text appears character-by-character with a subtle bounce.
- Player input field at the bottom, sage outline when focused.

### Inventory
- A grid of cream tiles with soft drop shadow.
- Each item is a small hand-drawn icon on a circle of its category color.
- Selecting an item shows a small flavor-text card in the lower right.

### HUD
- Almost nothing. Time of day shown as a small sun/moon icon top-right. No health bars. No quest markers.

## Audio (notes for later)

Not art per se, but it must match: warm acoustic instrumentation (felt-hammer piano, soft strings, gentle woodwinds, music boxes). Ambient: birdsong by day, crickets by night, distant wind chimes. No drum kits. No synth pads.

## What to avoid

- Hard outlines (we use soft cel, not anime hard ink)
- Anime-style large round eyes (we use dot-eyes — restraint)
- Bright neon saturation (the palette caps this)
- Realistic textures (no PBR photorealism — we are a music box)
- Player aggression visuals (no combat HUD, no damage numbers, no aggressive UI states)
- Dense visual noise (every screen should have room to breathe)

## Reference pinboard (todo)

- [ ] Collect Animal Crossing screenshots at golden hour
- [ ] Bamboletta product photography for face proportions
- [ ] Porcelain plate florals for motif vocabulary
- [ ] Studio Ghibli backgrounds for sky and foliage massing
- [ ] Knit and felt textile macros for material reference
