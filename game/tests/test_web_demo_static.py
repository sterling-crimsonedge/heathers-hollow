"""Static checks for the root browser demo consolidation client."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "game" / "web"


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str]] = []
        self.canvas_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "script":
            self.scripts.append(attr_map)
        if tag == "canvas" and attr_map.get("id"):
            self.canvas_ids.add(attr_map["id"])


def read_web_file(name: str) -> str:
    return (WEB_ROOT / name).read_text(encoding="utf-8")


def test_web_demo_files_exist() -> None:
    for name in ("index.html", "main.js", "scene.js", "README.md"):
        assert (WEB_ROOT / name).exists(), f"Missing game/web/{name}"


def test_throwaway_codex_demo_is_archived() -> None:
    assert not (REPO_ROOT / "codex-demo.html").exists()
    assert (REPO_ROOT / "docs" / "prototypes" / "codex-demo.html").exists()


def test_index_loads_module_and_canvas() -> None:
    parser = ScriptParser()
    parser.feed(read_web_file("index.html"))

    assert "village-canvas" in parser.canvas_ids
    assert any(
        script.get("type") == "module" and script.get("src") == "./main.js"
        for script in parser.scripts
    ), "index.html must load ./main.js as an ES module"
    assert "Server offline" in read_web_file("index.html")
    assert "interaction-prompt" in read_web_file("index.html")
    assert "nearby-chip" in read_web_file("index.html")


def test_main_uses_root_client_protocol() -> None:
    main_js = read_web_file("main.js")

    assert "/client/bootstrap" in main_js
    assert "/client/villagers/${encodeURIComponent(villagerId)}/context" in main_js
    assert "ws://127.0.0.1:8765/ws/conversation" in main_js
    assert 'type: "player_message"' in main_js
    assert 'type: "gift_item"' in main_js
    assert "player_id: PLAYER_ID" in main_js
    assert "villager_id: villager.id" in main_js
    assert "item," in main_js
    assert "gift_source: \"starter_inventory\"" in main_js
    assert "memories_used" in main_js
    assert "setVillagerStatus(villagerId, contextStatusLine(context))" in main_js
    assert "relationshipTone(relationship)" in main_js
    assert "renderInteractionPrompt" in main_js


def test_web_demo_does_not_use_legacy_worktree_protocol() -> None:
    main_js = read_web_file("main.js")
    legacy_payloads = [
        'type: "hello"',
        'type: "begin"',
        'type: "say"',
        'type: "gift"',
        'type: "end"',
        'type: "set_name"',
        '"ready"',
        '"reply_chunk"',
        '"greeting_chunk"',
    ]
    for payload in legacy_payloads:
        assert payload not in main_js, f"Legacy worktree payload leaked into root web demo: {payload}"


def test_web_demo_drops_worktree_cast_names() -> None:
    main_js = read_web_file("main.js")
    assert "Maple" not in main_js
    assert "Bramble" not in main_js
    assert re.search(r"\bSage\b", main_js) is None


def test_scene_is_local_canvas_village() -> None:
    scene_js = read_web_file("scene.js")

    assert "export function createVillageScene" in scene_js
    assert "getContext(\"2d\")" in scene_js
    assert "setVillagers(villagers)" in scene_js
    assert "getNearbyVillagerId" in scene_js
    assert "drawVillager" in scene_js
    assert "drawHouse" in scene_js
    assert "drawGarden" in scene_js
    assert "drawFountain" in scene_js
    assert "setVillagerStatus(villagerId, status)" in scene_js
    assert "this.velocity" in scene_js
    assert "drawCloud" in scene_js
    assert "drawFlowerBed" in scene_js
    assert "drawLantern" in scene_js
    assert "truncate(villager.status" in scene_js
    assert "import * as THREE" not in scene_js
    # Clover's brook landmark — `LOCATION_POINTS.brook` exists, but the brook
    # needs an actual draw method so the cast-doc chipped-saucer beat reads
    # at a glance instead of leaving Clover floating on bare grass.
    assert "drawBrook" in scene_js
    assert "this.drawBrook(" in scene_js
    assert "marigold" in scene_js.lower(), (
        "Brook landmark should ground Clover's marigold motif on the bank."
    )
    # HH-061 visual polish: a full-scene time-of-day wash so dawn/evening/
    # night actually re-tint the whole hollow, a starfield at night, and
    # richer villager labels (archetype line plus an in-world interaction
    # cue when Heather is nearby but hasn't selected anyone yet).
    assert "applyTimeOfDayWash" in scene_js
    assert "this.applyTimeOfDayWash(" in scene_js
    assert "TIME_WASH" in scene_js
    assert "drawStars" in scene_js
    assert "this.drawStars(" in scene_js
    assert "STAR_FIELD" in scene_js
    assert "villager.archetype" in scene_js, (
        "Villager labels should show archetype so Heather can identify "
        "each villager at a glance."
    )
    assert "nearby && !active" in scene_js, (
        "Nearby-but-not-active villagers should advertise the 'E' interaction "
        "cue in-world, mirroring the bottom-of-screen prompt."
    )


def test_web_readme_documents_run_path() -> None:
    readme = read_web_file("README.md")

    assert "python3 -m http.server 8000 -d game/web" in readme
    assert "uv run --python 3.12 --with-requirements server/requirements.txt uvicorn" in readme
    assert "GET /client/bootstrap" in readme
    assert "player_message" in readme
    assert "gift_item" in readme


def main() -> None:
    test_web_demo_files_exist()
    test_throwaway_codex_demo_is_archived()
    test_index_loads_module_and_canvas()
    test_main_uses_root_client_protocol()
    test_web_demo_does_not_use_legacy_worktree_protocol()
    test_web_demo_drops_worktree_cast_names()
    test_scene_is_local_canvas_village()
    test_web_readme_documents_run_path()
    print("PASS: Root browser demo uses the canonical client protocol.")


if __name__ == "__main__":
    main()
