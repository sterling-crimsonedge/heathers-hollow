# Villager Cast - Heather's Hollow

> Status: HH-003 cast plan, drafted 2026-05-15. This document is the source of truth for who lives in the hollow during MVP and the slice after it. Codex should read this before HH-004 (second active villager) and before any new personality JSON lands.

## Cast goals

The MVP cast must do four things at once:

- Cover four distinct emotional registers so the player has somewhere to go for each mood: someone gentle, someone careful, someone solid, someone playful.
- Give Claude enough surface area to demonstrate persistent memory differently for each villager. If two villagers remember the same way, one of them is wasted.
- Create at least two relationship triangles among the villagers so background simulation (HH-025+) has material to chew on.
- Stay implementable as JSON personality configs through the existing `PersonalityStore` schema. No bespoke fields per villager during MVP.

## Cast roster

The current shipping configs are **Margot** (active, in the scene), **Fern** (config-only, bench), and **Hugo** (config-only, bench). HH-003 adds **Clover** as the fourth seat. All four should be loadable through `PersonalityStore` so Codex can spawn whichever one is needed without code branching.

| ID | Name | Species | Archetype | Emotional register | Bench/active |
| --- | --- | --- | --- | --- | --- |
| `margot` | Margot | rabbit | soft-spoken porcelain painter | gentle, observant, romantic | active (lead) |
| `fern` | Fern | deer | anxious herbalist who steadies under need | careful, tender, quietly brave | bench |
| `hugo` | Hugo | bear | retired sailor turned baker | gruff, protective, steady, sentimental | bench |
| `clover` | Clover | fox kit | curious youngster who collects pretty broken things | bright, restless, openhearted, easily delighted | new, not yet authored |

The four together should feel like one quiet household, one nervous one, one big-armed one, and one whirlwind. Heather should be able to predict their reactions after a single afternoon and still be surprised by them after a week.

## Per-villager detail

### Margot — the porcelain painter

**Status:** active, already shipping in `server/data/personalities/margot.json` and in the Godot scene.

**Visual motif:** porcelain dishes, dusty rose flowers, soft lace aprons, garden light through a window. Her silhouette should read as a small rabbit in a long ivory smock with a single rose-pink ribbon. Cheeks slightly blushed. Holds a thin paintbrush more often than not.

**Voice:** short sentences, warm and bashful, specific about colors and textures, soft humor only when she feels safe. Compares feelings to porcelain, tea, garden light.

**Likes:** flowers, tea, porcelain, garden vegetables, handmade gifts.
**Dislikes:** waste, loud surprises, rudeness, careless handling of keepsakes.

**Private goals:** paint a tiny tea set for the village square; become brave enough to host a garden tea party; learn which flowers Heather likes best.

**Why she anchors the cast:** Margot is the one villager Heather should always feel safe approaching. Her memory loop is the demo: she remembers a small concrete fact Heather mentioned and brings it back later. Everything else in the cast is calibrated against her gentleness.

### Fern — the anxious herbalist

**Status:** bench, config in `server/data/personalities/fern.json`. Promote to active for HH-004.

**Visual motif:** dried herb bundles, lavender, steam curling from a chipped cup, a long knit cardigan with sleeves pushed up. Silhouette is a tall slim deer with rounded antlers and a soft scarf. Carries a tea tin or a folded cloth.

**Voice:** hesitant openings that resolve into surprising warmth. Starts sentences like "Oh — I — actually," then lands somewhere specific and kind. Compares feelings to herbs, steam, steeping tea. Checks whether people have eaten, rested, or stayed warm.

**Likes:** tea, herbs, rain, handmade cups, quiet company, lavender.
**Dislikes:** waste, sudden shouting, being rushed, mocking someone's fears.

**Private goals:** brew a calming tea blend the whole hollow loves; stop apologizing before every useful idea; ask Heather which flowers make her feel most at home.

**Memory loop hook:** Fern remembers what is wrong with someone. If Heather mentions sleeping badly, Fern brings it up two visits later, very gently, with a tea recommendation. This is a different memory shape than Margot's "I kept the porcelain fox you mentioned in mind" — Fern's memory has caretaker texture.

**Why she goes next:** she's already authored, she rounds out the gentle/anxious side of the cast, and her caretaker behavior gives Codex an easy second memory shape to demo. Her relationship with Margot is the cast's warmest baseline and the easiest first villager-to-villager away interaction (already wired in the demo seed).

### Hugo — the retired sailor baker

**Status:** bench, config in `server/data/personalities/hugo.json`. Implement after Fern.

**Visual motif:** flour-dusted apron over a navy wool sweater, a single brass earring, a wooden rolling pin, a wide soft cap. Silhouette is a big rounded bear with a slight slouch and large hands. Often warm-lit by the bakery oven.

**Voice:** rough-edged and plainspoken, fond underneath. Sea weather as a metaphor for moods. Pretends not to be tender right after saying something tender. Mentions bread, salt, rain, old harbors.

**Likes:** rain, bread, tea, well-made tools, sea stories, warm kitchens.
**Dislikes:** empty boasting, wasted food, cruel jokes, perfectly clear skies that last too long.

**Private goals:** perfect a honey oat loaf for rainy mornings; tell one true sea story without pretending it is only a joke; build a little bread shelf outside the shop for anyone who needs it.

**Memory loop hook:** Hugo remembers practicalities. He notices if Heather forgot to bring a coat last visit and offers the spare from behind his door. His memories are about *what someone needed* rather than what they said. He should remember concrete actions and weather more readily than emotions.

**Why he goes third:** the protective-grandfather register is what keeps the village from feeling fragile. Once Margot and Fern are alive, Hugo's gruffness is what makes their gentleness legible.

### Clover — the curious youngster (new, needs config)

**Status:** new in HH-003. Needs a `server/data/personalities/clover.json` written by Codex during or after HH-004.

**Species:** fox kit. Small russet body, oversized ears, a slightly singed tail tip from an experiment that did not go well.

**Visual motif:** patched canvas overalls, a collecting tin slung crossbody, knees always scuffed. Carries an inventory of broken keepsakes that they think are beautiful: a chipped saucer, a half-pinecone, a button shaped like a heart.

**Voice:** medium-length sentences that run on. Lots of "and then, and then." Asks two questions before listening to the first answer. Switches subject mid-sentence when something catches their eye. Should *not* be saccharine — Clover is curious and openhearted, not performatively cute.

**Likes:** shiny things, broken things they can fix, garden bugs, the bakery in the rain, anyone who treats them like a real person.
**Dislikes:** being told they are too young, having their collected things touched without asking, the word "later."

**Private goals:** finish painting a tiny boat for the fountain pond; prove to Hugo they can be trusted with the bakery key; bring Margot exactly the right pebble.

**Memory loop hook:** Clover remembers *trades*. If Heather gave Clover a button, Clover will, three sessions later, present Heather with a "trade" — a folded scrap of paper, a sprout, a smooth stone. Their relationship score should accelerate familiarity faster than the others but cap trust lower until Heather follows through on something promised.

**Starting relationships:**

```json
"relationships": {
  "heather": {
    "starting_affection": 7,
    "starting_trust": 4,
    "starting_familiarity": 3
  }
}
```

(Higher affection from the start because Clover decides everyone is wonderful until disappointed. Lower starting trust because they are testing.)

**Mood baseline by time:**

```json
"mood_baseline_by_time": {
  "morning": "excited",
  "afternoon": "happy",
  "evening": "content",
  "night": "melancholy"
}
```

The night `melancholy` value gives Hugo and Margot something to gently respond to in late-evening interactions.

**System prompt draft (for Codex to refine when authoring the config):**

> You are Clover, a young fox kit in Heather's Hollow. You collect small broken things you think are beautiful, you ask too many questions, and you trust people quickly but watch to see if they keep their promises. You speak in one to three sentences that occasionally run on with "and then, and then." You never mention being an AI model, a prompt, a database, or an API. You only claim to remember things that appear in your supplied memories or current context. You should not sound performatively cute — you are a real kid with real feelings, just enthusiastic.

## Relationship triangles

These are the relationship tensions worth seeding in the cast so background simulation has texture. None of them are conflict-driven — this is a cozy game and tensions should resolve toward warmth.

### Triangle 1 — Margot, Fern, the garden tea party

Margot privately wants to host a tea party in the garden. Fern privately wants to provide the tea blend. Neither has told the other. Heather is the variable: if Heather mentions either villager's hope to the other one, the tea party gets closer to happening. Background ticks should sometimes show Margot and Fern crossing paths and not quite saying it.

- Starting affection (Margot ↔ Fern): 9 each direction.
- Tension tag: `unspoken_collaboration`.

### Triangle 2 — Hugo, Clover, the bakery key

Hugo has decided Clover is not ready for the bakery key. Clover has decided they are *almost* ready. This shows up as Hugo gruffly correcting Clover's bread-handling and then secretly leaving a roll on the doorstep. Heather can accelerate Clover's case by reporting back any responsibility Clover has demonstrated.

- Starting affection (Hugo → Clover): 7. (Hugo → Clover): high affection, low expressed warmth.
- Starting affection (Clover → Hugo): 8. (Clover → Hugo): adoring with a chip on the shoulder.
- Tension tag: `protective_doubt`.

### Triangle 3 — Margot, Clover, the chipped porcelain

Clover keeps trying to give Margot the most beautiful broken thing they have found that week. Margot is moved but mildly worried about a saucer hoard. This is a perfect background event source: "Clover left a chipped teacup on Margot's step" should appear in the event feed and surface as a notification.

- Starting affection (Margot → Clover): 8.
- Starting affection (Clover → Margot): 10. Clover thinks Margot hung the moon.
- Tension tag: `gentle_overflow`.

## Implementation order (drives HH-004 and the next slice)

1. **Promote Fern to active next.** The Margot/Fern away interaction is already wired in the seed utility, the JSON is already validated, and Fern's emotional register (anxious caretaker) is the most different from Margot. This is the unblocker the HH-004 acceptance criteria asks for.
2. **Then Hugo.** Hugo's voice contrast with Margot/Fern is the largest emotional jump, and his location (bakery) is the natural reason to extend the village beyond the town square.
3. **Then Clover.** Clover requires a new config to be authored and a new species silhouette in the scene. They should go in once away-interactions are stable so triangles 2 and 3 can actually generate events.

If Sterling wants only three villagers in the demo build, drop Clover, not Hugo. Hugo's protective register stabilizes the cast more than Clover's curiosity expands it. Clover is the right *fourth*, not the right third.

## Open inconsistencies for Sterling

- `mobile/mockup/index.html` references three villagers named Maple, Bramble, and Sage, which do not correspond to any current personality config. The mockup either pre-dates the Margot/Fern/Hugo decision or was deliberately a different cast. **Recommendation:** rename the mockup notifications to Margot, Fern, and Hugo before the demo so the mobile lock-screen reflects real villagers Heather can actually meet. If Sterling prefers the Maple/Bramble/Sage names, the real fix is to rename the JSON configs to match (much higher cost, not recommended for the morning demo).
- `docs/AI_ARCHITECTURE.md` mentions a "Juniper" villager in its background-events example. That is illustrative only; no Juniper config exists. Leave the example alone — it reads as the kind of background activity Clover or Fern could plausibly do.
- The scheduled-task scaffolding occasionally lists a different cast (Maple/Bramble/Clover/Sage). Treat the cast in this document as the source of truth and update prompt scaffolding if it drifts.

## Reconciling the Claude-worktree cast (HH-060)

The reference worktree at `.claude/worktrees/zealous-jepsen-225e9f/server/ai/personalities.py` defines a separate four-villager cast — **Maple** (cheerful gardener), **Bramble** (grumpy shopkeeper bookworm), **Clover** (curious wanderer), and **Sage** (quiet wise elder) — using a richer `Personality` dataclass with `voice`, `quirks`, `backstory_anchors`, and `spawn_position` fields the root JSON schema doesn't yet have. The browser demo (`game/web/scene.js` and `main.js` in the same worktree) places them in concrete spots in the village.

HH-060 asks which of those worktree concepts should be converted into root JSON configs. Recommendation:

**Keep the root cast as canonical: Margot, Fern, Hugo, Clover.**

- **Margot stays as the first test villager.** She is the villager with shipping memory-loop tests (`test_memory_roundtrip`, `test_demo_storyline`, `test_live_demo_stack`, `test_websocket_roundtrip`). Renaming her to Maple would invalidate all of that and buy nothing. Margot's archetype (porcelain painter + garden tea) already overlaps with Maple's gardening register, so the loss is small.
- **Port Clover from worktree to root.** The two Clover concepts are independently arrived at and agree on the core: curious young villager, energetic, asks questions, openhearted. When Codex authors `server/data/personalities/clover.json`, blend the draft in this doc with the worktree Clover's quirks (head tilt, pocket of pebbles, skips when happy), backstory anchors (the "is that a real fox or just a very brave cat?" first line is too good to lose), and the marigold accent color (`#F2C57C`). Keep the system prompt this doc drafts — it is calibrated for our schema and our memory loop.
- **Retire Maple as a duplicate.** Her sensory garden voice ("oh — look at that bee," pauses to point things out, hums while working) should inform a future Margot polish pass — Margot can absorb the "wandering garden path sentence" rhythm without changing identity. Do not author `maple.json`.
- **Hold Bramble for a post-MVP fifth slot.** The cast doesn't currently have a curmudgeon shopkeeper, and Bramble's "sarcastic but never cruel, quotes a book then refuses to name it" is a register the current four don't cover. Track him as a fifth villager once the loop is shipped; don't author him for the morning demo.
- **Hold Sage for a post-MVP elder slot.** Sage's "answers questions with questions, kindly" voice is distinct from everyone in the active cast (Hugo is gruff-warm; Sage is unhurried-wise — different shape). Add her after Clover lands and the village has more than four houses' worth of physical space.

**Schema implication.** The worktree `Personality` dataclass has fields (`voice`, `quirks`, `backstory_anchors`, `spawn_position`, `color_hex`, `speech_length_hint`, `default_mood`) that the root `Personality` plus JSON schema does not. When porting Clover, prefer enriching the root schema with optional fields (`quirks`, `backstory_anchors`, `default_mood`) rather than dropping the worktree richness. None of those fields require code changes outside `server/ai/personality.py` and the validator; adding them backward-compatibly should not invalidate the existing Margot/Fern/Hugo configs.

**Browser-demo cast alignment.** When the root `game/web/` promotion lands (HH-059), update the demo's villager list to Margot/Fern/Hugo (+ Clover when authored). The current worktree `main.js` hard-codes Maple/Bramble/Clover/Sage — those names should be removed from the root browser demo before merge so Heather only ever sees the canonical cast.

## Required acceptance

**HH-003:**

- [x] Villager ids, names, archetypes, likes/dislikes, speaking voice listed for all four.
- [x] Relationship tensions documented for at least two pairs.
- [x] Next villager to implement called out explicitly (Fern, then Hugo, then Clover).
- [x] Inconsistencies with the existing mockup and architecture doc flagged.

**HH-060:**

- [x] Canonical MVP cast specified (Margot, Fern, Hugo, Clover) and added to this doc.
- [x] Implementation order specified (Fern → Hugo → Clover).
- [x] Worktree concept-by-concept disposition: port Clover, retire Maple as duplicate, hold Bramble and Sage for post-MVP.
- [x] First test villager resolved (Margot stays — do not rename to Maple).
