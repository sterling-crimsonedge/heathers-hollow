# Art Direction - Heather's Hollow

> Status: Foundation draft for MVP prototyping.

## North Star

Heather's Hollow should feel like a tiny handmade village kept on a sunny kitchen shelf: soft, rounded, warm, floral, and gently alive. The style target is **Animal Crossing x Neko Atsume x Bamboletta dolls x porcelain dishes** in low-poly 3D with soft shading.

The art should be cozy without becoming visually noisy. Every object should look touchable, safe, and slightly handcrafted.

## Visual Pillars

- **Soft silhouettes:** Round heads, pillowy bodies, curved roofs, beveled props.
- **Handcrafted imperfection:** Slight asymmetry, painted edges, visible fabric or brush texture.
- **Warm materiality:** Ceramic, linen, painted wood, cotton, wool, paper, garden soil.
- **Readable scale:** Chunky forms that are clear from a pulled-back camera.
- **Gentle detail:** Floral motifs and pattern accents should reward looking closer without cluttering the play view.

## Inspiration Notes

### Animal Crossing

- Friendly proportions.
- Clear village readability.
- Small daily routines.
- Soft outdoor lighting.

Use as a reference for accessibility and silhouette, not for direct copying.

### Neko Atsume

- Simple forms with high charm.
- Calm compositions.
- Characters that are cute without excessive detail.

Use as a restraint reference: not every surface needs decoration.

### Bamboletta Dolls

- Handmade textile quality.
- Soft faces, rosy cheeks, warm imperfections.
- Hair and clothing that feel stitched or brushed.

Use as the character warmth reference.

### Porcelain Dishware

- Warm ivory base colors.
- Tiny floral accents.
- Glossy ceramic highlights.
- Blue and rose decorative details.

Use as the motif and material reference for homes, dishes, signs, and keepsakes.

## Color Palette

The palette should be pastel, warm, and balanced. Avoid a single-hue world; cream and ivory are the base, but sage, rose, blue, clay, and muted berry accents should all be present.

### Core Swatches

| Name | Hex | Usage |
| --- | --- | --- |
| Warm Ivory | `#FFF6E6` | UI panels, porcelain, window glow |
| Butter Cream | `#F7E3B4` | Paths, light trim, cozy highlights |
| Soft Sage | `#9EBB9B` | Grass, garden leaves, painted shutters |
| Deep Sage | `#5F7F64` | Foliage shadows, sign text, contrast |
| Dusty Rose | `#D99AA5` | flowers, cheeks, cloth, emotional accents |
| Soft Blue | `#9EC7D8` | sky, porcelain motifs, cool shadows |
| Powder Blue | `#C8DEE8` | UI tint, ceramic glaze variation |
| Warm Clay | `#C98964` | roof tiles, pots, path stones |
| Berry Jam | `#9B5061` | small accents, special flowers, UI focus |
| Cocoa Line | `#6E5144` | outlines, wood, readable text |

### Palette Rules

- Use Warm Ivory or Butter Cream for most UI surfaces.
- Use Soft Sage as the dominant outdoor color, balanced by flowers and warm paths.
- Use Dusty Rose sparingly so it remains special.
- Use Cocoa Line instead of black for outlines and text.
- Keep saturation low except for tiny focal accents.

## Character Design Principles

### Proportions

- Slightly oversized head.
- Short body with rounded limbs.
- Stubby hands and feet.
- Large readable face.
- Low-poly silhouette with smoothed normals.

### Faces

- Dot or bead eyes.
- Tiny mouth shapes.
- Rosy cheek circles or soft blush patches.
- Expressions should be subtle and readable: content, shy, delighted, worried.

### Materials

- Skin/fur: soft matte with gentle subsurface warmth.
- Clothing: cloth shader with faint weave normal.
- Accessories: ceramic, ribbon, felt, wood, or paper.

### Villager Differentiation

Each villager should be distinct through:

- Silhouette.
- Color accents.
- Favorite material or motif.
- Idle animation.
- Voice and personality.

Avoid relying only on color swaps.

## Environment Design

### Village Shape

- Circular or gently winding paths.
- Small destination clusters rather than a grid.
- Clear landmarks visible from the town square.
- Low fences, flower boxes, and garden beds to guide movement.

### Town Square

- Central tree or fountain.
- Benches and bulletin board.
- Warm stone or packed-earth path.
- Open space for player movement and villager gatherings.

### Player House

- Rounded cottage roof.
- Warm window glow.
- Handmade sign or mailbox.
- Soft floral accents around the door.

### Garden

- Lush but readable.
- Raised beds, little sprouts, pumpkins, herbs, roses.
- Slight animation on leaves.
- Dirt should be warm brown, not gray.

### Shop

- Cozy storefront, not a commercial block.
- Painted wooden sign.
- Crates, jars, folded cloth, ceramic pieces.
- Warm interior glow visible through windows.

### Interiors

Future interiors should feel like dollhouse rooms:

- Low furniture.
- Round tables.
- Quilts, lace, curtains, tiny dishes.
- Clutter grouped into readable vignettes.
- Soft window light and warm lamps.

## Lighting

### Default

- Warm sun key light.
- Cool blue sky fill.
- Soft ambient occlusion.
- Low contrast shadows.

### Day Parts

- Morning: ivory-gold, misty, fresh.
- Afternoon: clean and bright, stronger garden color.
- Evening: rose-gold, long soft shadows.
- Night: powder blue ambient with warm windows and lanterns.

## Godot 4 Shader And Material Approach

### MVP Materials

Use `StandardMaterial3D` first:

- Albedo palette colors.
- Roughness high for cloth/wood.
- Slight specular for ceramic.
- Smooth normals on low-poly meshes.

This keeps the first prototype fast and editable.

### Stylized Toon Ramp

After the base scene works, add a custom spatial shader:

- Two or three diffuse bands.
- Soft transition thresholds.
- Warm highlight band.
- Cocoa-colored rim or outline only where needed.
- Optional screen-space outline later.

### Painterly Edges

Use texture accents rather than heavy outlines:

- Hand-painted trim.
- Slight color variation on roof tiles.
- Brushy path edges.
- Tiny floral decals.

### Cloth Shader

For dolls and home textiles:

- Faint weave normal map.
- High roughness.
- Slight color variation.
- No sharp specular highlights.

### Ceramic Shader

For porcelain dishes and keepsakes:

- Warm ivory albedo.
- Moderate roughness.
- Soft clearcoat/specular.
- Blue or rose decal motifs.

### Foliage Shader

For later garden polish:

- Vertex wind sway.
- Slight color variation per instance.
- Brighter top-facing leaves.
- Footstep or proximity response as a future delight.

## UI Art Direction

- Rounded panels, but avoid bulky nested cards.
- Warm ivory panel backgrounds.
- Cocoa text.
- Dusty rose focus accents.
- Small icons for talk, gift, inventory, and time.
- Dialogue panel should feel like a porcelain label or stitched note, not a sci-fi chat window.

## Prototype Asset Guidance

The first prototype can use primitive meshes if they obey the art direction:

- Capsule or sphere characters.
- Box cottages with rounded-looking proportions.
- Cylinder tree trunks and sphere/capsule canopies.
- Plane terrain with warm sage material.
- Simple path shapes in butter cream or warm clay.

Do not wait for final art to validate the AI interaction loop. The scene only needs enough warmth and spatial clarity to make the first conversation feel grounded.

## Open Questions For Cowork

- Should villagers be animal-like, doll-like, or a hybrid?
- How visible should porcelain motifs be on characters versus environment props?
- What are the first three signature props that make the village feel made for Heather?
- Should the camera lean more dollhouse/isometric or third-person cozy adventure?
- What reference board should become the source of truth for final modeling?
