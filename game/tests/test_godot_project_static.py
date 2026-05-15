"""Static checks for the Godot prototype when the Godot editor is unavailable."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GAME_ROOT = REPO_ROOT / "game"

RES_REFERENCE_PATTERN = re.compile(r"res://[A-Za-z0-9_./-]+")
STRING_LITERAL_PATTERN = re.compile(r'"([^"]+)"')
INPUT_CALL_PATTERN = re.compile(
    r"Input\.(?:is_action_just_pressed|is_action_pressed|get_vector)\(([^)]*)\)"
)
ACTION_REGISTRATION_PATTERN = re.compile(
    r"_add_(?:key|joy_axis|joy_button)_action\(\"([^\"]+)\""
)
NODE_NAME_PATTERN = re.compile(r'\[node name="([^"]+)"')
NODE_REF_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_/]*)")

SCRIPT_TO_SCENE = {
    GAME_ROOT / "scripts/main.gd": GAME_ROOT / "scenes/main.tscn",
    GAME_ROOT / "scripts/player_controller.gd": GAME_ROOT / "scenes/player.tscn",
    GAME_ROOT / "scripts/villager.gd": GAME_ROOT / "scenes/villager.tscn",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_res_path(reference: str) -> Path:
    if not reference.startswith("res://"):
        raise AssertionError(f"Expected a res:// reference, got {reference!r}")
    return GAME_ROOT / reference.removeprefix("res://")


def _all_project_files() -> list[Path]:
    return [
        *sorted((GAME_ROOT / "scenes").glob("*.tscn")),
        *sorted((GAME_ROOT / "scripts").glob("*.gd")),
        GAME_ROOT / "project.godot",
    ]


def test_project_main_scene_exists() -> None:
    project_text = _read(GAME_ROOT / "project.godot")
    match = re.search(r'run/main_scene="([^"]+)"', project_text)
    assert match, "project.godot must declare run/main_scene"

    main_scene = _resolve_res_path(match.group(1))
    assert main_scene.exists(), f"Main scene does not exist: {main_scene}"


def test_res_references_exist() -> None:
    missing: list[str] = []

    for path in _all_project_files():
        for reference in RES_REFERENCE_PATTERN.findall(_read(path)):
            resolved = _resolve_res_path(reference)
            if not resolved.exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} -> {reference}")

    assert not missing, "Missing Godot res:// references:\n" + "\n".join(missing)


def test_input_actions_are_registered_at_runtime() -> None:
    used_actions: set[str] = set()
    for script_path in (GAME_ROOT / "scripts").glob("*.gd"):
        for call_args in INPUT_CALL_PATTERN.findall(_read(script_path)):
            used_actions.update(STRING_LITERAL_PATTERN.findall(call_args))

    player_script = _read(GAME_ROOT / "scripts/player_controller.gd")
    registered_actions = set(ACTION_REGISTRATION_PATTERN.findall(player_script))

    missing_actions = sorted(used_actions - registered_actions)
    assert not missing_actions, (
        "Input actions used in GDScript but not registered by player_controller.gd: "
        + ", ".join(missing_actions)
    )


def test_scene_node_references_exist() -> None:
    missing: list[str] = []

    for script_path, scene_path in SCRIPT_TO_SCENE.items():
        script_text = _read(script_path)
        scene_nodes = set(NODE_NAME_PATTERN.findall(_read(scene_path)))
        for raw_ref in NODE_REF_PATTERN.findall(script_text):
            first_node = raw_ref.split("/", 1)[0]
            if first_node not in scene_nodes:
                missing.append(
                    f"{script_path.relative_to(REPO_ROOT)} references ${raw_ref}, "
                    f"but {first_node!r} is not in {scene_path.relative_to(REPO_ROOT)}"
                )

    assert not missing, "Missing scene nodes:\n" + "\n".join(missing)


def test_main_bootstrap_inventory_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "/client/bootstrap" in main_script, "Main scene should request the client bootstrap payload."
    assert "HTTPRequest.new()" in main_script, "Main scene should create an HTTPRequest for bootstrap."
    assert "request_completed.connect(_on_bootstrap_request_completed)" in main_script
    assert "parsed.get(\"world\", {})" in main_script
    assert "parsed.get(\"villagers\", [])" in main_script
    assert "parsed.get(\"inventory\", {})" in main_script
    assert "bootstrap_world" in main_script
    assert "bootstrap_villagers" in main_script
    assert "_apply_bootstrap_inventory" in main_script
    assert "STARTER_GIFT_ID := \"dusty_rose\"" in main_script
    assert "_starter_gift_payload()" in main_script
    assert "conversation_client.send_gift" in main_script
    assert "FALLBACK_STARTER_GIFT" in main_script


def test_main_bootstrap_villager_data_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")
    villager_script = _read(GAME_ROOT / "scripts/villager.gd")

    assert "bootstrap_villagers_by_id" in main_script
    assert "villagers_by_id" in main_script
    assert "villagers_by_id[villager.villager_id] = villager" in main_script
    assert "_apply_bootstrap_villagers(villagers)" in main_script
    assert "villager_data.get(\"id\", \"\")" in main_script
    assert "apply_public_profile(villager_data)" in main_script
    assert "dialogue_status.text = \"%s is thinking...\"" in main_script
    assert "PLAYER_ID" in main_script

    assert "func apply_public_profile(profile: Dictionary)" in villager_script
    assert "profile.get(\"display_name\", display_name)" in villager_script
    assert "profile.get(\"home_location\", home_location)" in villager_script
    assert "name_label.text = display_name" in villager_script


def test_main_bootstrap_world_status_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "var world_status_label: Label" in main_script
    assert "world_status_label = Label.new()" in main_script
    assert "world_status_label.text = _world_status_text({})" in main_script
    assert "_apply_bootstrap_world(world)" in main_script
    assert "bootstrap_world = world.duplicate(true)" in main_script
    assert "world_status_label.text = _world_status_text(bootstrap_world)" in main_script
    assert "func _world_status_text(world: Dictionary) -> String" in main_script
    assert "world.get(\"clock\", \"\")" in main_script
    assert "_world_label_part(world, \"time_label\", \"morning\")" in main_script
    assert "_world_label_part(world, \"season\", \"spring\")" in main_script
    assert "_world_label_part(world, \"weather\", \"clear\")" in main_script


def test_main_bootstrap_notification_summary_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "var bootstrap_notifications: Dictionary = {}" in main_script
    assert "var notification_status_label: Label" in main_script
    assert "notification_status_label = Label.new()" in main_script
    assert "notification_status_label.text = _notification_status_text({})" in main_script
    assert "parsed.get(\"notifications\", {})" in main_script
    assert "_apply_bootstrap_notifications(notifications)" in main_script
    assert "bootstrap_notifications = notifications.duplicate(true)" in main_script
    assert "notification_status_label.text = _notification_status_text(bootstrap_notifications)" in main_script
    assert "func _notification_status_text(notifications: Dictionary) -> String" in main_script
    assert "notifications.get(\"count\", 0)" in main_script
    assert "notifications.get(\"has_more\", false)" in main_script
    assert "News: quiet in the hollow" in main_script
    assert "update_notification_cursor" not in main_script
    assert "notifications/cursor" not in main_script


def test_main_shared_interaction_context_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "func _interaction_context(villager, extra_context: Dictionary = {}) -> Dictionary" in main_script
    assert "var context: Dictionary = villager.get_context()" in main_script
    assert "context[\"location\"] = location" in main_script
    assert "context[\"client_time\"] = _bootstrap_world_value(\"time_label\", \"prototype_day\")" in main_script
    assert "context[\"world\"] = {" in main_script
    assert "\"day\": _bootstrap_world_day()" in main_script
    assert "\"clock\": _bootstrap_world_value(\"clock\", \"08:00\")" in main_script
    assert "\"time_label\": _bootstrap_world_value(\"time_label\", \"morning\")" in main_script
    assert "\"season\": _bootstrap_world_value(\"season\", \"spring\")" in main_script
    assert "\"weather\": _bootstrap_world_value(\"weather\", \"clear\")" in main_script
    assert "for key in extra_context.keys()" in main_script
    assert "_interaction_context(active_villager)" in main_script
    assert "_interaction_context(villager, {\"gift_source\": \"starter_inventory\"})" in main_script
    assert "active_villager.get_context()" not in main_script
    assert "context[\"gift_source\"] = \"starter_inventory\"" not in main_script


def test_main_villager_context_request_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "/client/villagers/%s/context" in main_script
    assert "var villager_context_request: HTTPRequest" in main_script
    assert "var villager_context_request_villager_id := \"\"" in main_script
    assert "var villager_context_by_id: Dictionary = {}" in main_script
    assert "func _start_villager_context_request(villager, queue_if_busy := false) -> void" in main_script
    assert "request.request_completed.connect(_on_villager_context_request_completed.bind(villager_id, request))" in main_script
    assert "_start_villager_context_request(villager)" in main_script
    assert "func _on_villager_context_request_completed(" in main_script
    assert "villager_context_by_id[villager_id] = context" in main_script
    assert "func _public_villager_context(payload: Dictionary) -> Dictionary" in main_script
    assert "func _public_villager_fields(villager_data: Dictionary) -> Dictionary" in main_script
    assert "public_fields[key] = villager_data[key]" in main_script
    assert "private_goals" not in main_script
    assert "system_prompt" not in main_script
    assert "print(" not in main_script
    assert "push_warning(" not in main_script


def test_main_context_refresh_after_interactions_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "var villager_context_refresh_pending_id := \"\"" in main_script
    assert "if villager_context_request != null and villager_context_request_villager_id == villager_id:" in main_script
    assert "if queue_if_busy:" in main_script
    assert "villager_context_refresh_pending_id = villager_id" in main_script
    assert "villager_context_request_villager_id = villager_id" in main_script
    assert "villager_context_request_villager_id = \"\"" in main_script
    assert "villager_context_refresh_pending_id = \"\"" in main_script
    assert "var should_refresh_after_completion := villager_context_refresh_pending_id == villager_id" in main_script
    assert "func _refresh_active_villager_context_after_reply(message: Dictionary) -> void" in main_script
    assert "_refresh_active_villager_context_after_reply(message)" in main_script
    assert "var reply_villager_id := str(message.get(\"villager_id\", active_villager_id))" in main_script
    assert "if reply_villager_id != active_villager_id:" in main_script
    assert "_start_villager_context_request(active_villager, true)" in main_script
    assert "func _start_active_villager_context_refresh(villager_id: String) -> void" in main_script
    assert "_start_active_villager_context_refresh(villager_id)" in main_script
    assert "if message.get(\"type\", \"\") == \"villager_reply\":" in main_script
    assert "conversation_client.send_player_message" in main_script
    assert "conversation_client.send_gift" in main_script


def test_main_dialogue_context_summary_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "var dialogue_context_label: Label" in main_script
    assert "var dialogue_memory_label: Label" in main_script
    assert "dialogue_context_label = Label.new()" in main_script
    assert "dialogue_context_label.visible = false" in main_script
    assert "stack.add_child(dialogue_context_label)" in main_script
    assert "dialogue_memory_label = Label.new()" in main_script
    assert "dialogue_memory_label.visible = false" in main_script
    assert "dialogue_memory_label.clip_text = true" in main_script
    assert "stack.add_child(dialogue_memory_label)" in main_script
    assert "_update_dialogue_context_summary(villager.villager_id)" in main_script
    assert "_clear_dialogue_context_summary()" in main_script
    assert "_hide_dialogue_memory_teaser()" in main_script
    assert "func _update_dialogue_context_summary(villager_id: String) -> void" in main_script
    assert "func _villager_context_summary(context: Dictionary) -> String" in main_script
    assert "func _latest_memory_teaser(context: Dictionary) -> String" in main_script
    assert "func _truncate_context_text(text: String, max_length: int) -> String" in main_script
    assert "func _context_array_count(context: Dictionary, key: String) -> int" in main_script
    assert "func _context_score(relationship: Dictionary, key: String) -> int" in main_script
    assert "func _relationship_tone(affection: int, trust: int, tension: int) -> String" in main_script
    assert "villager_context_by_id.get(villager_id, {})" in main_script
    assert "dialogue_context_label.text = summary" in main_script
    assert "dialogue_context_label.visible = true" in main_script
    assert "dialogue_memory_label.text = latest_memory" in main_script
    assert "dialogue_memory_label.visible = true" in main_script
    assert "if active_villager != null and str(active_villager.villager_id) == villager_id:" in main_script
    assert "Bond: %s (A%d T%d) / Memories: %d / Events: %d" in main_script
    assert "Latest memory: %s" in main_script
    assert "memory.get(\"text\", \"\")" in main_script
    assert "_truncate_context_text(memory_text, 92)" in main_script
    assert ".replace(\"\\n\", \" \").replace(\"\\r\", \" \")" in main_script
    assert "cleaned.substr(0, max_length - 3)" in main_script
    assert "_context_array_count(context, \"memories\")" in main_script
    assert "_context_array_count(context, \"events\")" in main_script
    assert "_context_score(relationship, \"affection\")" in main_script
    assert "_context_score(relationship, \"trust\")" in main_script
    assert "_context_score(relationship, \"tension\")" in main_script
    assert "dialogue_context_label.text = str(" not in main_script
    assert "dialogue_memory_label.text = str(" not in main_script
    assert "memory.get(\"metadata\"" not in main_script
    assert "private_goals" not in main_script
    assert "system_prompt" not in main_script


def test_main_reply_memory_influence_status_wiring() -> None:
    main_script = _read(GAME_ROOT / "scripts/main.gd")

    assert "var dialogue_influence_label: Label" in main_script
    assert "dialogue_influence_label = Label.new()" in main_script
    assert "dialogue_influence_label.visible = false" in main_script
    assert "dialogue_influence_label.clip_text = true" in main_script
    assert "dialogue_influence_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL" in main_script
    assert "stack.add_child(dialogue_influence_label)" in main_script
    assert "func _update_dialogue_influence_status(message: Dictionary) -> void" in main_script
    assert "_update_dialogue_influence_status(message)" in main_script
    assert "func _memories_used_count(message: Dictionary) -> int" in main_script
    assert "message.get(\"memories_used\", [])" in main_script
    assert "typeof(memories_used) != TYPE_ARRAY" in main_script
    assert "str(entry).strip_edges().is_valid_int()" in main_script
    assert "func _dialogue_influence_text(count: int) -> String" in main_script
    assert "dialogue_influence_label.text = _dialogue_influence_text(count)" in main_script
    assert "dialogue_influence_label.visible = true" in main_script
    assert "Remembered 1 thing" in main_script
    assert "Remembered %d things" in main_script
    assert "func _hide_dialogue_influence_status() -> void" in main_script
    assert "_hide_dialogue_influence_status()" in main_script
    # Mood status, refresh flow, and context summary must still run alongside.
    assert "dialogue_status.text = \"Mood: %s\" % mood" in main_script
    assert "_refresh_active_villager_context_after_reply(message)" in main_script
    # The cue must never expose raw memory text or private fields.
    assert "dialogue_influence_label.text = str(memory" not in main_script
    assert "dialogue_influence_label.text = str(" not in main_script
    assert "memory.get(\"text\"" not in main_script.split("func _update_dialogue_influence_status", 1)[1].split("\nfunc ", 1)[0]
    assert "private_goals" not in main_script
    assert "system_prompt" not in main_script


def main() -> None:
    test_project_main_scene_exists()
    test_res_references_exist()
    test_input_actions_are_registered_at_runtime()
    test_scene_node_references_exist()
    test_main_bootstrap_inventory_wiring()
    test_main_bootstrap_villager_data_wiring()
    test_main_bootstrap_world_status_wiring()
    test_main_bootstrap_notification_summary_wiring()
    test_main_shared_interaction_context_wiring()
    test_main_villager_context_request_wiring()
    test_main_context_refresh_after_interactions_wiring()
    test_main_dialogue_context_summary_wiring()
    test_main_reply_memory_influence_status_wiring()
    print("✓ Godot project static checks passed")


if __name__ == "__main__":
    main()
