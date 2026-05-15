extends Node3D

const PLAYER_SCENE := preload("res://scenes/player.tscn")
const VILLAGER_SCENE := preload("res://scenes/villager.tscn")
const PLAYER_ID := "heather"
const BOOTSTRAP_CLIENT_ID := "godot_client"
const BOOTSTRAP_URL_TEMPLATE := "http://127.0.0.1:8765/client/bootstrap?client_id=%s&player_id=%s&notification_limit=5"
const VILLAGER_CONTEXT_URL_TEMPLATE := "http://127.0.0.1:8765/client/villagers/%s/context?subject_id=%s&memory_limit=5&event_limit=5"
const STARTER_GIFT_ID := "dusty_rose"
const FALLBACK_STARTER_GIFT := {
	"item_id": "dusty_rose",
	"display_name": "Dusty Rose",
}

# Approximate world-space anchors for each public `home_location` keyword the
# root server publishes via `/client/bootstrap`. Picked to roughly mirror the
# `game/web/scene.js` `LOCATION_POINTS` layout while staying inside the
# generated Godot village footprint:
#   - `town_square`: Margot's existing plaza spot near the central fountain.
#   - `garden`: edge of the cottage garden plots southwest of the plaza.
#   - `shop`: just in front of the shop cottage to the east.
#   - `brook`: the S-bend of water laid down by `_create_brook()` between
#     the plaza and shop, mirroring the web demo's (4, 5) landmark.
# Villagers without a known home_location fall through to FALLBACK_VILLAGER_POSITIONS.
const HOME_LOCATION_POSITIONS := {
	"town_square": Vector3(2.5, 0, 0.7),
	"garden": Vector3(-8.5, 0, -6.5),
	"shop": Vector3(9.5, 0, -2.0),
	"brook": Vector3(4.0, 0, 5.0),
	"player_house": Vector3(-9.5, 0, 4.0),
}
const FALLBACK_VILLAGER_POSITIONS := [
	Vector3(2.5, 0, 0.7),
	Vector3(-1.5, 0, -1.2),
	Vector3(1.8, 0, 2.6),
	Vector3(-3.4, 0, 0.4),
]
# Per-villager facing tweaks so each cast member angles toward the plaza
# instead of staring along world-Z. Keyed by villager_id; villagers without
# an entry use a neutral facing of -35° (the original Margot heading).
const HOME_LOCATION_FACING_DEGREES := {
	"margot": -35.0,
	"fern": 35.0,
	"hugo": -120.0,
	"clover": 200.0,
}
const DEFAULT_VILLAGER_FACING_DEGREES := -35.0

@onready var conversation_client = $ConversationClient

var bootstrap_request: HTTPRequest
var villager_context_request: HTTPRequest
var villager_context_request_villager_id := ""
var villager_context_refresh_pending_id := ""
var bootstrap_world: Dictionary = {}
var bootstrap_villagers: Array = []
var bootstrap_villagers_by_id: Dictionary = {}
var bootstrap_notifications: Dictionary = {}
var villager_context_by_id: Dictionary = {}
var starter_inventory: Array = []
var starter_gift := FALLBACK_STARTER_GIFT.duplicate(true)
var player
var active_villager = null
var villagers_by_id: Dictionary = {}
var world_status_label: Label
var notification_status_label: Label
var interact_hint: Label
var dialogue_panel: PanelContainer
var dialogue_name: Label
var dialogue_body: RichTextLabel
var dialogue_input: LineEdit
var dialogue_status: Label
var dialogue_context_label: Label
var dialogue_memory_label: Label
var dialogue_influence_label: Label
var send_button: Button
var gift_button: Button
# HH-062 (Godot half): per-item gift picker so Heather can send any starter
# inventory item from the dialogue panel instead of always pushing the default
# Dusty Rose. The picker is a hidden VBoxContainer that gets rebuilt from the
# cached `starter_inventory` each time the gift button is pressed; the existing
# keyboard "gift" shortcut still defaults to `_starter_gift_payload()` so the
# muscle-memory quick-send affordance from earlier heartbeats is preserved.
var gift_picker_panel: PanelContainer
var gift_picker_list: VBoxContainer

func _ready() -> void:
	_create_lighting()
	_create_village()
	_spawn_player()
	_spawn_test_villager()
	_build_ui()

	conversation_client.message_received.connect(_on_server_message)
	conversation_client.status_changed.connect(_on_server_status)
	conversation_client.error_received.connect(_on_server_error)
	_start_bootstrap_request()

func _process(_delta: float) -> void:
	if dialogue_panel.visible and Input.is_action_just_pressed("cancel"):
		_close_dialogue()
	elif Input.is_action_just_pressed("gift") and not (dialogue_panel.visible and dialogue_input.has_focus()):
		_send_starter_gift()

func _create_lighting() -> void:
	var world_environment := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color.html("#C8DEE8")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color.html("#FFF6E6")
	environment.ambient_light_energy = 0.85
	world_environment.environment = environment
	add_child(world_environment)

	var sun := DirectionalLight3D.new()
	sun.name = "WarmSun"
	sun.light_color = Color.html("#FFF0CC")
	sun.light_energy = 2.2
	sun.rotation_degrees = Vector3(-45, -35, 0)
	add_child(sun)

func _create_village() -> void:
	_add_plane("SoftSageTerrain", Vector3.ZERO, Vector2(42, 42), "#9EBB9B")
	_add_box("TownSquarePathNorthSouth", Vector3(0, 0.02, 0), Vector3(3.8, 0.04, 22), "#F7E3B4")
	_add_box("TownSquarePathEastWest", Vector3(0, 0.03, 0), Vector3(22, 0.04, 3.8), "#F7E3B4")
	_add_box("CentralPlaza", Vector3(0, 0.04, 0), Vector3(8.2, 0.04, 8.2), "#E7C78D")

	_create_tree(Vector3(0, 0, -1.2))
	_create_cottage("PlayerHouse", Vector3(-11, 0, 4), "#FFF6E6", "#D99AA5")
	_create_cottage("Shop", Vector3(11, 0, -2), "#F7E3B4", "#9EC7D8")
	_create_garden(Vector3(-9, 0, -8))
	_create_bench(Vector3(3.7, 0, 3.6))
	_create_brook(HOME_LOCATION_POSITIONS["brook"])

func _spawn_player() -> void:
	player = PLAYER_SCENE.instantiate()
	player.name = "Player"
	player.global_position = Vector3(0, 0, 7.0)
	add_child(player)
	player.interact_requested.connect(_on_player_interact)
	player.nearby_villager_changed.connect(_on_nearby_villager_changed)

func _spawn_test_villager() -> void:
	# Offline-fallback Margot — guarantees at least one talkable villager when
	# `/client/bootstrap` is unreachable. The full cast is spawned in
	# `_spawn_villagers_from_bootstrap()` once the server replies and may
	# upgrade this Margot in place via `apply_public_profile()`.
	_spawn_villager(
		"margot",
		"Margot",
		"town_square",
		HOME_LOCATION_POSITIONS["town_square"],
		HOME_LOCATION_FACING_DEGREES.get("margot", DEFAULT_VILLAGER_FACING_DEGREES)
	)

func _spawn_villager(
	villager_id: String,
	display_name: String,
	home_location: String,
	position: Vector3,
	facing_degrees: float
) -> Node:
	if villagers_by_id.has(villager_id):
		return villagers_by_id[villager_id]

	var villager = VILLAGER_SCENE.instantiate()
	villager.villager_id = villager_id
	villager.display_name = display_name
	villager.home_location = home_location
	villager.global_position = position
	villager.rotation_degrees.y = facing_degrees
	add_child(villager)
	villagers_by_id[villager.villager_id] = villager
	return villager

func _spawn_villagers_from_bootstrap() -> void:
	# Iterate the cached `/client/bootstrap` villagers payload and spawn one
	# `villager.tscn` per entry, placing each via HOME_LOCATION_POSITIONS so
	# the root server's data-driven `home_location` field drives the scene.
	# Villagers that already exist (typically the offline-fallback Margot) get
	# their public profile re-applied via `apply_public_profile()` instead of
	# being re-instantiated, which keeps Heather's nearby-villager tracking
	# stable across bootstrap completion.
	if bootstrap_villagers == null or typeof(bootstrap_villagers) != TYPE_ARRAY:
		return
	if bootstrap_villagers.is_empty():
		return

	var fallback_index := 0
	for villager_data in bootstrap_villagers:
		if typeof(villager_data) != TYPE_DICTIONARY:
			continue

		var villager_id := str(villager_data.get("id", "")).strip_edges()
		if villager_id.is_empty():
			continue

		var display_name := str(villager_data.get("display_name", villager_id))
		var home_location := str(villager_data.get("home_location", "town_square"))
		if home_location.is_empty():
			home_location = "town_square"

		var position: Vector3
		if HOME_LOCATION_POSITIONS.has(home_location):
			position = HOME_LOCATION_POSITIONS[home_location]
		else:
			position = FALLBACK_VILLAGER_POSITIONS[
				fallback_index % FALLBACK_VILLAGER_POSITIONS.size()
			]
			fallback_index += 1

		var facing := float(HOME_LOCATION_FACING_DEGREES.get(
			villager_id, DEFAULT_VILLAGER_FACING_DEGREES
		))

		if villagers_by_id.has(villager_id):
			var existing = villagers_by_id[villager_id]
			existing.global_position = position
			existing.rotation_degrees.y = facing
			existing.apply_public_profile(villager_data)
		else:
			_spawn_villager(
				villager_id,
				display_name,
				home_location,
				position,
				facing
			)

func _build_ui() -> void:
	var canvas := CanvasLayer.new()
	canvas.name = "UI"
	add_child(canvas)

	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	canvas.add_child(root)

	world_status_label = Label.new()
	world_status_label.text = _world_status_text({})
	world_status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	world_status_label.add_theme_color_override("font_color", Color.html("#6E5144"))
	world_status_label.add_theme_font_size_override("font_size", 16)
	world_status_label.anchor_left = 0.0
	world_status_label.anchor_right = 0.0
	world_status_label.anchor_top = 0.0
	world_status_label.anchor_bottom = 0.0
	world_status_label.offset_left = 24
	world_status_label.offset_right = 420
	world_status_label.offset_top = 18
	world_status_label.offset_bottom = 44
	root.add_child(world_status_label)

	notification_status_label = Label.new()
	notification_status_label.text = _notification_status_text({})
	notification_status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	notification_status_label.add_theme_color_override("font_color", Color.html("#9B5061"))
	notification_status_label.add_theme_font_size_override("font_size", 15)
	notification_status_label.anchor_left = 0.0
	notification_status_label.anchor_right = 0.0
	notification_status_label.anchor_top = 0.0
	notification_status_label.anchor_bottom = 0.0
	notification_status_label.offset_left = 24
	notification_status_label.offset_right = 420
	notification_status_label.offset_top = 44
	notification_status_label.offset_bottom = 70
	root.add_child(notification_status_label)

	interact_hint = Label.new()
	interact_hint.visible = false
	interact_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	interact_hint.add_theme_color_override("font_color", Color.html("#6E5144"))
	interact_hint.add_theme_font_size_override("font_size", 22)
	interact_hint.anchor_left = 0.5
	interact_hint.anchor_right = 0.5
	interact_hint.anchor_top = 1.0
	interact_hint.anchor_bottom = 1.0
	interact_hint.offset_left = -180
	interact_hint.offset_right = 180
	interact_hint.offset_top = -94
	interact_hint.offset_bottom = -58
	root.add_child(interact_hint)

	dialogue_panel = PanelContainer.new()
	dialogue_panel.visible = false
	dialogue_panel.anchor_left = 0.5
	dialogue_panel.anchor_right = 0.5
	dialogue_panel.anchor_top = 1.0
	dialogue_panel.anchor_bottom = 1.0
	dialogue_panel.offset_left = -360
	dialogue_panel.offset_right = 360
	dialogue_panel.offset_top = -255
	dialogue_panel.offset_bottom = -24
	dialogue_panel.add_theme_stylebox_override("panel", _panel_style())
	root.add_child(dialogue_panel)

	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 8)
	dialogue_panel.add_child(stack)

	var header := HBoxContainer.new()
	stack.add_child(header)

	dialogue_name = Label.new()
	dialogue_name.text = "Margot"
	dialogue_name.add_theme_color_override("font_color", Color.html("#6E5144"))
	dialogue_name.add_theme_font_size_override("font_size", 22)
	header.add_child(dialogue_name)

	dialogue_status = Label.new()
	dialogue_status.text = "AI server connecting..."
	dialogue_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	dialogue_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dialogue_status.add_theme_color_override("font_color", Color.html("#9B5061"))
	header.add_child(dialogue_status)

	dialogue_context_label = Label.new()
	dialogue_context_label.visible = false
	dialogue_context_label.text = ""
	dialogue_context_label.add_theme_color_override("font_color", Color.html("#8A6049"))
	dialogue_context_label.add_theme_font_size_override("font_size", 14)
	stack.add_child(dialogue_context_label)

	dialogue_memory_label = Label.new()
	dialogue_memory_label.visible = false
	dialogue_memory_label.text = ""
	dialogue_memory_label.clip_text = true
	dialogue_memory_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dialogue_memory_label.add_theme_color_override("font_color", Color.html("#8A6049"))
	dialogue_memory_label.add_theme_font_size_override("font_size", 13)
	stack.add_child(dialogue_memory_label)

	dialogue_influence_label = Label.new()
	dialogue_influence_label.visible = false
	dialogue_influence_label.text = ""
	dialogue_influence_label.clip_text = true
	dialogue_influence_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dialogue_influence_label.add_theme_color_override("font_color", Color.html("#8A6049"))
	dialogue_influence_label.add_theme_font_size_override("font_size", 13)
	stack.add_child(dialogue_influence_label)

	dialogue_body = RichTextLabel.new()
	dialogue_body.custom_minimum_size = Vector2(0, 115)
	dialogue_body.fit_content = false
	dialogue_body.scroll_active = true
	dialogue_body.bbcode_enabled = false
	dialogue_body.add_theme_color_override("default_color", Color.html("#6E5144"))
	stack.add_child(dialogue_body)

	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 8)
	stack.add_child(input_row)

	dialogue_input = LineEdit.new()
	dialogue_input.placeholder_text = "Say something to the villager..."
	dialogue_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dialogue_input.text_submitted.connect(_on_dialogue_submitted)
	input_row.add_child(dialogue_input)

	send_button = Button.new()
	send_button.text = "Send"
	send_button.pressed.connect(_on_send_pressed)
	input_row.add_child(send_button)

	gift_button = Button.new()
	gift_button.text = "Gift..."
	gift_button.tooltip_text = "Choose a gift from the starter inventory."
	gift_button.pressed.connect(_on_gift_pressed)
	input_row.add_child(gift_button)

	# Hidden gift picker. Rebuilt from `starter_inventory` each time the gift
	# button is pressed, so any inventory delta from `/client/bootstrap` is
	# picked up the next time Heather opens it. Placed inside the dialogue
	# `stack` (above the input row) so it floats inside the dialogue panel
	# rather than as a separate window — keeps the focus loop simple.
	gift_picker_panel = PanelContainer.new()
	gift_picker_panel.visible = false
	gift_picker_panel.add_theme_stylebox_override("panel", _gift_picker_panel_style())
	stack.add_child(gift_picker_panel)
	stack.move_child(gift_picker_panel, stack.get_child_count() - 2)

	var gift_picker_stack := VBoxContainer.new()
	gift_picker_stack.add_theme_constant_override("separation", 6)
	gift_picker_panel.add_child(gift_picker_stack)

	var gift_picker_header := HBoxContainer.new()
	gift_picker_stack.add_child(gift_picker_header)

	var gift_picker_title := Label.new()
	gift_picker_title.text = "Choose a gift"
	gift_picker_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gift_picker_title.add_theme_color_override("font_color", Color.html("#6E5144"))
	gift_picker_title.add_theme_font_size_override("font_size", 16)
	gift_picker_header.add_child(gift_picker_title)

	var gift_picker_cancel := Button.new()
	gift_picker_cancel.text = "Cancel"
	gift_picker_cancel.pressed.connect(_close_gift_picker)
	gift_picker_header.add_child(gift_picker_cancel)

	gift_picker_list = VBoxContainer.new()
	gift_picker_list.add_theme_constant_override("separation", 4)
	gift_picker_stack.add_child(gift_picker_list)

func _start_bootstrap_request() -> void:
	bootstrap_request = HTTPRequest.new()
	bootstrap_request.name = "BootstrapRequest"
	add_child(bootstrap_request)
	bootstrap_request.request_completed.connect(_on_bootstrap_request_completed)

	var bootstrap_url := BOOTSTRAP_URL_TEMPLATE % [BOOTSTRAP_CLIENT_ID, PLAYER_ID]
	var error := bootstrap_request.request(bootstrap_url)
	if error != OK:
		bootstrap_request.queue_free()
		bootstrap_request = null

func _start_villager_context_request(villager, queue_if_busy := false) -> void:
	if villager == null:
		return

	var villager_id := str(villager.villager_id)
	if villager_id.is_empty():
		return

	if villager_context_request != null and villager_context_request_villager_id == villager_id:
		if queue_if_busy:
			villager_context_refresh_pending_id = villager_id
		return

	if villager_context_request != null:
		villager_context_request.queue_free()
		villager_context_request = null
		villager_context_request_villager_id = ""
		villager_context_refresh_pending_id = ""

	var request := HTTPRequest.new()
	request.name = "VillagerContextRequest"
	add_child(request)
	villager_context_request = request
	villager_context_request_villager_id = villager_id
	request.request_completed.connect(_on_villager_context_request_completed.bind(villager_id, request))

	var context_url := VILLAGER_CONTEXT_URL_TEMPLATE % [_url_part(villager_id), _url_part(PLAYER_ID)]
	var error := request.request(context_url)
	if error != OK:
		request.queue_free()
		if villager_context_request == request:
			villager_context_request = null
			villager_context_request_villager_id = ""

func _on_bootstrap_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		return

	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		return

	var world = parsed.get("world", {})
	if typeof(world) == TYPE_DICTIONARY:
		_apply_bootstrap_world(world)

	var villagers = parsed.get("villagers", [])
	if typeof(villagers) == TYPE_ARRAY:
		_apply_bootstrap_villagers(villagers)

	var inventory = parsed.get("inventory", {})
	if typeof(inventory) == TYPE_DICTIONARY:
		_apply_bootstrap_inventory(inventory)

	var notifications = parsed.get("notifications", {})
	if typeof(notifications) == TYPE_DICTIONARY:
		_apply_bootstrap_notifications(notifications)

func _on_villager_context_request_completed(
	result: int,
	response_code: int,
	_headers: PackedStringArray,
	body: PackedByteArray,
	villager_id: String,
	request: HTTPRequest
) -> void:
	var should_refresh_after_completion := villager_context_refresh_pending_id == villager_id
	if should_refresh_after_completion:
		villager_context_refresh_pending_id = ""

	if villager_context_request == request:
		villager_context_request = null
		villager_context_request_villager_id = ""
	request.queue_free()

	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		if should_refresh_after_completion:
			_start_active_villager_context_refresh(villager_id)
		return

	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		if should_refresh_after_completion:
			_start_active_villager_context_refresh(villager_id)
		return

	var context := _public_villager_context(parsed)
	if context.is_empty():
		if should_refresh_after_completion:
			_start_active_villager_context_refresh(villager_id)
		return

	villager_context_by_id[villager_id] = context
	if active_villager != null and str(active_villager.villager_id) == villager_id:
		_update_dialogue_context_summary(villager_id)
	if should_refresh_after_completion:
		_start_active_villager_context_refresh(villager_id)

func _apply_bootstrap_world(world: Dictionary) -> void:
	bootstrap_world = world.duplicate(true)
	if world_status_label != null:
		world_status_label.text = _world_status_text(bootstrap_world)

func _url_part(value: String) -> String:
	return str(value).uri_encode()

func _public_villager_context(payload: Dictionary) -> Dictionary:
	var public_context: Dictionary = {}

	var world = payload.get("world", {})
	if typeof(world) == TYPE_DICTIONARY:
		public_context["world"] = world.duplicate(true)

	var villager_data = payload.get("villager", {})
	if typeof(villager_data) == TYPE_DICTIONARY:
		public_context["villager"] = _public_villager_fields(villager_data)

	var relationship = payload.get("relationship", {})
	if typeof(relationship) == TYPE_DICTIONARY:
		public_context["relationship"] = relationship.duplicate(true)

	var memories = payload.get("memories", [])
	if typeof(memories) == TYPE_ARRAY:
		public_context["memories"] = memories.duplicate(true)

	var events = payload.get("events", [])
	if typeof(events) == TYPE_ARRAY:
		public_context["events"] = events.duplicate(true)

	return public_context

func _public_villager_fields(villager_data: Dictionary) -> Dictionary:
	var public_fields: Dictionary = {}
	for key in [
		"id",
		"display_name",
		"home_location",
		"species",
		"archetype",
		"core_traits",
		"values",
		"speaking_style",
		"likes",
		"dislikes",
		"relationships",
		"mood_baseline_by_time"
	]:
		if villager_data.has(key):
			public_fields[key] = villager_data[key]
	return public_fields

func _update_dialogue_context_summary(villager_id: String) -> void:
	if dialogue_context_label == null and dialogue_memory_label == null:
		return

	var context = villager_context_by_id.get(villager_id, {})
	if typeof(context) != TYPE_DICTIONARY:
		_clear_dialogue_context_summary()
		return

	var summary := _villager_context_summary(context)
	if summary.is_empty():
		_hide_dialogue_context_label()
	elif dialogue_context_label != null:
		dialogue_context_label.text = summary
		dialogue_context_label.visible = true

	var latest_memory := _latest_memory_teaser(context)
	if latest_memory.is_empty():
		_hide_dialogue_memory_teaser()
	elif dialogue_memory_label != null:
		dialogue_memory_label.text = latest_memory
		dialogue_memory_label.visible = true

func _clear_dialogue_context_summary() -> void:
	_hide_dialogue_context_label()
	_hide_dialogue_memory_teaser()
	_hide_dialogue_influence_status()

func _hide_dialogue_context_label() -> void:
	if dialogue_context_label == null:
		return
	dialogue_context_label.text = ""
	dialogue_context_label.visible = false

func _hide_dialogue_memory_teaser() -> void:
	if dialogue_memory_label == null:
		return
	dialogue_memory_label.text = ""
	dialogue_memory_label.visible = false

func _villager_context_summary(context: Dictionary) -> String:
	var relationship = context.get("relationship", {})
	if typeof(relationship) != TYPE_DICTIONARY:
		return ""

	var affection := _context_score(relationship, "affection")
	var trust := _context_score(relationship, "trust")
	var tension := _context_score(relationship, "tension")
	var memory_count := _context_array_count(context, "memories")
	var event_count := _context_array_count(context, "events")
	var tone := _relationship_tone(affection, trust, tension)
	return "Bond: %s (A%d T%d) / Memories: %d / Events: %d" % [
		tone,
		affection,
		trust,
		memory_count,
		event_count
	]

func _latest_memory_teaser(context: Dictionary) -> String:
	var memories = context.get("memories", [])
	if typeof(memories) != TYPE_ARRAY:
		return ""

	for memory in memories:
		if typeof(memory) != TYPE_DICTIONARY:
			continue

		var memory_text := str(memory.get("text", "")).strip_edges()
		if memory_text.is_empty():
			continue

		return "Latest memory: %s" % _truncate_context_text(memory_text, 92)

	return ""

func _truncate_context_text(text: String, max_length: int) -> String:
	var cleaned := text.replace("\n", " ").replace("\r", " ").strip_edges()
	while cleaned.find("  ") != -1:
		cleaned = cleaned.replace("  ", " ")

	if cleaned.length() <= max_length:
		return cleaned
	if max_length <= 0:
		return ""
	if max_length <= 3:
		return cleaned.substr(0, max_length)
	return "%s..." % cleaned.substr(0, max_length - 3).strip_edges()

func _context_array_count(context: Dictionary, key: String) -> int:
	var value = context.get(key, [])
	if typeof(value) == TYPE_ARRAY:
		return value.size()
	return 0

func _context_score(relationship: Dictionary, key: String) -> int:
	var value = relationship.get(key, 0)
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)

	var text := str(value).strip_edges()
	if text.is_valid_int():
		return int(text)
	return 0

func _relationship_tone(affection: int, trust: int, tension: int) -> String:
	if tension >= 8:
		return "strained"
	if affection >= 8 or trust >= 8:
		return "warm"
	if affection <= -4 or trust <= -4:
		return "cool"
	return "new"

func _world_status_text(world: Dictionary) -> String:
	var clock := str(world.get("clock", "")).strip_edges()
	var time_label := _world_label_part(world, "time_label", "morning")
	var season := _world_label_part(world, "season", "spring")
	var weather := _world_label_part(world, "weather", "clear")
	if clock.is_empty():
		return "Hollow: %s / %s / %s" % [time_label, season, weather]
	return "Hollow: %s %s / %s / %s" % [clock, time_label, season, weather]

func _world_label_part(world: Dictionary, key: String, fallback: String) -> String:
	var value := str(world.get(key, fallback)).strip_edges()
	if value.is_empty():
		value = fallback
	return value.replace("_", " ").capitalize()

func _bootstrap_world_value(key: String, fallback: String) -> String:
	var value := str(bootstrap_world.get(key, fallback)).strip_edges()
	if value.is_empty():
		return fallback
	return value

func _bootstrap_world_day() -> int:
	var day_value = bootstrap_world.get("day", 1)
	if typeof(day_value) == TYPE_INT or typeof(day_value) == TYPE_FLOAT:
		return int(day_value)

	var day_text := str(day_value).strip_edges()
	if day_text.is_valid_int():
		return int(day_text)
	return 1

func _interaction_context(villager, extra_context: Dictionary = {}) -> Dictionary:
	var context: Dictionary = villager.get_context()
	var location := str(context.get("location", "town_square")).strip_edges()
	if location.is_empty():
		location = "town_square"

	context["location"] = location
	context["client_time"] = _bootstrap_world_value("time_label", "prototype_day")
	context["world"] = {
		"day": _bootstrap_world_day(),
		"clock": _bootstrap_world_value("clock", "08:00"),
		"time_label": _bootstrap_world_value("time_label", "morning"),
		"season": _bootstrap_world_value("season", "spring"),
		"weather": _bootstrap_world_value("weather", "clear")
	}

	for key in extra_context.keys():
		context[key] = extra_context[key]
	return context

func _apply_bootstrap_notifications(notifications: Dictionary) -> void:
	bootstrap_notifications = notifications.duplicate(true)
	if notification_status_label != null:
		notification_status_label.text = _notification_status_text(bootstrap_notifications)

func _notification_status_text(notifications: Dictionary) -> String:
	var count := int(notifications.get("count", 0))
	if count <= 0:
		return "News: quiet in the hollow"

	var suffix := ""
	if notifications.get("has_more", false) == true:
		suffix = "+"
	if count == 1 and suffix.is_empty():
		return "News: 1 new note"
	return "News: %d%s new notes" % [count, suffix]

func _apply_bootstrap_villagers(villagers: Array) -> void:
	bootstrap_villagers = villagers
	bootstrap_villagers_by_id.clear()

	for villager_data in villagers:
		if typeof(villager_data) != TYPE_DICTIONARY:
			continue

		var villager_id := str(villager_data.get("id", ""))
		if villager_id.is_empty():
			continue

		bootstrap_villagers_by_id[villager_id] = villager_data.duplicate(true)

	# Spawn the rest of the cast (Fern/Hugo/Clover) from the bootstrap payload
	# and upgrade any already-spawned villagers (typically the offline-fallback
	# Margot) with their server-side public profile + home_location anchor.
	_spawn_villagers_from_bootstrap()

	if active_villager != null and dialogue_panel != null and dialogue_panel.visible:
		dialogue_name.text = active_villager.display_name

func _apply_bootstrap_inventory(inventory: Dictionary) -> void:
	var items = inventory.get("items", [])
	if typeof(items) != TYPE_ARRAY:
		return

	starter_inventory = items
	for item in items:
		if typeof(item) == TYPE_DICTIONARY and item.get("item_id", "") == STARTER_GIFT_ID:
			starter_gift = item.duplicate(true)
			# The gift button is the picker entry point now, so the tooltip
			# should describe the picker rather than a specific item. The
			# Dusty Rose stays the default for the keyboard shortcut.
			if gift_button != null:
				gift_button.tooltip_text = "Choose a gift from the starter inventory (%d items)." % items.size()
			return
	# Even without an explicit Dusty Rose entry, surface the inventory size on
	# the picker entry point so Heather knows the picker is populated.
	if gift_button != null and not items.is_empty():
		gift_button.tooltip_text = "Choose a gift from the starter inventory (%d items)." % items.size()

func _starter_gift_payload() -> Dictionary:
	return starter_gift.duplicate(true)

func _starter_gift_name() -> String:
	return str(starter_gift.get("display_name", "Dusty Rose"))

func _on_player_interact(villager) -> void:
	_open_dialogue(villager)

func _open_dialogue(villager) -> void:
	active_villager = villager
	dialogue_name.text = villager.display_name
	dialogue_body.text = "%s: %s\n\n" % [villager.display_name, villager.idle_line]
	_update_dialogue_context_summary(villager.villager_id)
	_hide_dialogue_influence_status()
	dialogue_panel.visible = true
	interact_hint.visible = false
	_start_villager_context_request(villager)
	dialogue_input.grab_focus()

func _on_nearby_villager_changed(villager) -> void:
	if dialogue_panel != null and dialogue_panel.visible:
		return
	if villager == null:
		interact_hint.visible = false
	else:
		interact_hint.text = villager.get_interaction_prompt()
		interact_hint.visible = true

func _on_dialogue_submitted(_text: String) -> void:
	_send_dialogue()

func _on_send_pressed() -> void:
	_send_dialogue()

func _on_gift_pressed() -> void:
	# Dialogue-side gift button now opens the per-item picker so Heather can
	# pick any inventory item. The keyboard "gift" shortcut still falls
	# through to `_send_starter_gift()` (default Dusty Rose) so muscle memory
	# from earlier heartbeats is preserved.
	_open_gift_picker()

func _send_dialogue() -> void:
	if active_villager == null:
		return

	var text := dialogue_input.text.strip_edges()
	if text.is_empty():
		return

	dialogue_body.text += "Heather: %s\n" % text
	dialogue_input.text = ""
	dialogue_status.text = "%s is thinking..." % active_villager.display_name
	_hide_dialogue_influence_status()

	var context := _interaction_context(active_villager)
	var sent := conversation_client.send_player_message(active_villager.villager_id, PLAYER_ID, text, context)
	if not sent:
		dialogue_status.text = "AI server unavailable"

func _send_starter_gift() -> void:
	# Keyboard "gift" shortcut path: send the default Dusty Rose without
	# opening the picker so muscle memory still works during the demo.
	_send_gift_item(_starter_gift_payload())

func _send_gift_item(item: Dictionary) -> void:
	var villager = active_villager
	if villager == null and player != null:
		villager = player.current_nearby_villager
	if villager == null:
		return

	if not dialogue_panel.visible:
		_open_dialogue(villager)
	_close_gift_picker()

	var gift_payload := _normalize_gift_item(item)
	var gift_name := _gift_display_name(gift_payload)
	dialogue_body.text += "Heather gives %s a %s.\n" % [villager.display_name, gift_name]
	dialogue_status.text = "%s is looking at the %s..." % [villager.display_name, gift_name.to_lower()]
	_hide_dialogue_influence_status()

	var context := _interaction_context(villager, {"gift_source": "starter_inventory"})
	var sent := conversation_client.send_gift(villager.villager_id, PLAYER_ID, gift_payload, context)
	if not sent:
		dialogue_status.text = "AI server unavailable"

func _normalize_gift_item(item) -> Dictionary:
	# Defensive copy so a stale picker entry can't mutate the cached
	# `starter_inventory`. Falls back to the default Dusty Rose payload if
	# the caller hands us something the server wouldn't accept.
	if typeof(item) == TYPE_DICTIONARY:
		var item_id := str(item.get("item_id", "")).strip_edges()
		if not item_id.is_empty():
			return item.duplicate(true)
	return _starter_gift_payload()

func _gift_display_name(item: Dictionary) -> String:
	var name := str(item.get("display_name", "")).strip_edges()
	if name.is_empty():
		name = str(item.get("item_id", "Gift")).strip_edges()
		if name.is_empty():
			name = "Gift"
	return name

func _gift_caption(item: Dictionary) -> String:
	# Mirrors the web demo's category caption beneath each gift button so
	# Heather can scan the picker by gift shape rather than reading every
	# name. Falls back to a soft "gift" label when the server didn't tag
	# the item with a category.
	var category := str(item.get("category", "")).strip_edges()
	if category.is_empty():
		return "gift"
	return category

func _gift_tooltip(item: Dictionary) -> String:
	# Hover hint sourced from the server's `gift_prompt`, giving the player
	# a one-line sensory cue so the picker reads as personality rather than
	# a flat list of names.
	return str(item.get("gift_prompt", "")).strip_edges()

func _gift_picker_items() -> Array:
	# Use the cached bootstrap inventory when it has at least one entry,
	# falling back to the default starter gift so the picker is never
	# empty even when `/client/bootstrap` hasn't replied yet.
	if typeof(starter_inventory) == TYPE_ARRAY and not starter_inventory.is_empty():
		return starter_inventory
	return [_starter_gift_payload()]

func _open_gift_picker() -> void:
	if gift_picker_panel == null or gift_picker_list == null:
		return

	# Rebuild the list from the latest cached inventory so any post-startup
	# bootstrap inventory delta is reflected the next time Heather opens it.
	for existing_child in gift_picker_list.get_children():
		existing_child.queue_free()

	for item in _gift_picker_items():
		if typeof(item) != TYPE_DICTIONARY:
			continue

		var button := Button.new()
		var display_name := _gift_display_name(item)
		var caption := _gift_caption(item)
		button.text = "%s — %s" % [display_name, caption]
		var tooltip := _gift_tooltip(item)
		if not tooltip.is_empty():
			button.tooltip_text = tooltip
		# Make a per-item defensive copy so each button binds its own dict.
		var bound_item := item.duplicate(true)
		button.pressed.connect(_on_gift_picker_item_pressed.bind(bound_item))
		gift_picker_list.add_child(button)

	gift_picker_panel.visible = true

func _close_gift_picker() -> void:
	if gift_picker_panel == null:
		return
	gift_picker_panel.visible = false

func _on_gift_picker_item_pressed(item: Dictionary) -> void:
	_send_gift_item(item)

func _gift_picker_panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color.html("#FFF6E6")
	style.border_color = Color.html("#D99AA5")
	style.set_border_width_all(1)
	style.corner_radius_top_left = 6
	style.corner_radius_top_right = 6
	style.corner_radius_bottom_left = 6
	style.corner_radius_bottom_right = 6
	style.set_content_margin(SIDE_LEFT, 12)
	style.set_content_margin(SIDE_RIGHT, 12)
	style.set_content_margin(SIDE_TOP, 8)
	style.set_content_margin(SIDE_BOTTOM, 8)
	return style

func _on_server_message(message: Dictionary) -> void:
	if message.get("type", "") == "villager_reply":
		var name := message.get("display_name", "Villager")
		var text := message.get("text", "...")
		dialogue_body.text += "%s: %s\n\n" % [name, text]
		var mood := message.get("mood", "content")
		dialogue_status.text = "Mood: %s" % mood
		_update_dialogue_influence_status(message)
		_refresh_active_villager_context_after_reply(message)
	elif message.get("type", "") == "error":
		_on_server_error(message.get("message", "Unknown AI server error."))

func _update_dialogue_influence_status(message: Dictionary) -> void:
	if dialogue_influence_label == null:
		return
	var count := _memories_used_count(message)
	if count <= 0:
		_hide_dialogue_influence_status()
		return
	dialogue_influence_label.text = _dialogue_influence_text(count)
	dialogue_influence_label.visible = true

func _memories_used_count(message: Dictionary) -> int:
	var memories_used = message.get("memories_used", [])
	if typeof(memories_used) != TYPE_ARRAY:
		return 0
	var count := 0
	for entry in memories_used:
		if typeof(entry) == TYPE_INT or typeof(entry) == TYPE_FLOAT:
			count += 1
		elif typeof(entry) == TYPE_STRING and str(entry).strip_edges().is_valid_int():
			count += 1
	return count

func _dialogue_influence_text(count: int) -> String:
	if count <= 1:
		return "Remembered 1 thing"
	return "Remembered %d things" % count

func _hide_dialogue_influence_status() -> void:
	if dialogue_influence_label == null:
		return
	dialogue_influence_label.text = ""
	dialogue_influence_label.visible = false

func _refresh_active_villager_context_after_reply(message: Dictionary) -> void:
	if active_villager == null:
		return

	var active_villager_id := str(active_villager.villager_id)
	var reply_villager_id := str(message.get("villager_id", active_villager_id))
	if reply_villager_id != active_villager_id:
		return

	_start_villager_context_request(active_villager, true)

func _start_active_villager_context_refresh(villager_id: String) -> void:
	if active_villager == null:
		return
	if str(active_villager.villager_id) != villager_id:
		return
	_start_villager_context_request(active_villager)

func _on_server_status(status: String) -> void:
	if dialogue_status != null:
		dialogue_status.text = status

func _on_server_error(message: String) -> void:
	if dialogue_status != null:
		dialogue_status.text = message

func _close_dialogue() -> void:
	dialogue_panel.visible = false
	_close_gift_picker()
	active_villager = null
	_clear_dialogue_context_summary()
	if player != null:
		_on_nearby_villager_changed(player.current_nearby_villager)

func _panel_style() -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color.html("#FFF6E6")
	style.border_color = Color.html("#D99AA5")
	style.set_border_width_all(2)
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	style.set_content_margin(SIDE_LEFT, 16)
	style.set_content_margin(SIDE_RIGHT, 16)
	style.set_content_margin(SIDE_TOP, 12)
	style.set_content_margin(SIDE_BOTTOM, 12)
	return style

func _material(hex_color: String, roughness := 0.86) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color.html(hex_color)
	material.roughness = roughness
	return material

func _add_plane(node_name: String, position: Vector3, size: Vector2, color: String) -> MeshInstance3D:
	var mesh := PlaneMesh.new()
	mesh.size = size
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = _material(color)
	instance.position = position
	add_child(instance)
	return instance

func _add_box(node_name: String, position: Vector3, size: Vector3, color: String) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = size
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = _material(color)
	instance.position = position
	add_child(instance)
	return instance

func _add_cylinder(node_name: String, position: Vector3, radius: float, height: float, color: String) -> MeshInstance3D:
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 10
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = _material(color)
	instance.position = position + Vector3(0, height * 0.5, 0)
	add_child(instance)
	return instance

func _add_sphere(node_name: String, position: Vector3, radius: float, color: String) -> MeshInstance3D:
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	mesh.radial_segments = 12
	mesh.rings = 6
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.mesh = mesh
	instance.material_override = _material(color)
	instance.position = position
	add_child(instance)
	return instance

func _create_tree(position: Vector3) -> void:
	_add_cylinder("PlazaTreeTrunk", position, 0.28, 1.7, "#6E5144")
	_add_sphere("PlazaTreeCanopy", position + Vector3(0, 2.0, 0), 1.35, "#5F7F64")
	_add_sphere("PlazaTreeCanopySoft", position + Vector3(-0.65, 1.75, 0.25), 0.82, "#9EBB9B")

func _create_cottage(node_name: String, position: Vector3, wall_color: String, roof_color: String) -> void:
	_add_box("%sWalls" % node_name, position + Vector3(0, 0.9, 0), Vector3(3.8, 1.8, 3.2), wall_color)
	_add_box("%sRoof" % node_name, position + Vector3(0, 2.05, 0), Vector3(4.25, 0.75, 3.65), roof_color)
	_add_box("%sDoor" % node_name, position + Vector3(0, 0.62, -1.63), Vector3(0.78, 1.12, 0.08), "#6E5144")
	_add_box("%sWindowLeft" % node_name, position + Vector3(-1.15, 1.12, -1.64), Vector3(0.52, 0.52, 0.08), "#FFF6E6")
	_add_box("%sWindowRight" % node_name, position + Vector3(1.15, 1.12, -1.64), Vector3(0.52, 0.52, 0.08), "#FFF6E6")

func _create_garden(position: Vector3) -> void:
	for x in range(2):
		for z in range(3):
			var plot_position := position + Vector3(x * 1.5, 0.08, z * 1.35)
			_add_box("GardenPlot", plot_position, Vector3(1.1, 0.12, 0.95), "#8A6049")
			_add_sphere("GardenSprout", plot_position + Vector3(0, 0.28, 0), 0.22, "#5F7F64")

func _create_bench(position: Vector3) -> void:
	_add_box("BenchSeat", position + Vector3(0, 0.42, 0), Vector3(2.0, 0.22, 0.48), "#C98964")
	_add_box("BenchBack", position + Vector3(0, 0.86, 0.23), Vector3(2.0, 0.62, 0.18), "#C98964")
	_add_cylinder("BenchLegLeft", position + Vector3(-0.74, 0, -0.15), 0.07, 0.42, "#6E5144")
	_add_cylinder("BenchLegRight", position + Vector3(0.74, 0, -0.15), 0.07, 0.42, "#6E5144")

func _create_brook(position: Vector3) -> void:
	# Clover's home — a soft S-bend of water with marigold tufts on the bank,
	# mirroring `drawBrook()` in `game/web/scene.js`. The brook flows along x
	# and bends around `position` (the canonical `home_location` for clover),
	# so Clover spawns standing on the dry bank at the bend instead of in the
	# stream. Keep the geometry primitive-only (boxes + spheres) to match the
	# rest of the generated village in this file.
	#
	# Wet earth bank — a darker oblong under the water that grounds the
	# marigolds and reads as moist ground instead of grass.
	_add_box("BrookBank", position + Vector3(0, 0.02, 0), Vector3(5.6, 0.04, 2.4), "#705C46")

	# Brook body — two flat boxes flanking the bend. Together they sketch the
	# canvas demo's S-curve without needing a real curved mesh, and the gap
	# between them lines up with `HOME_LOCATION_POSITIONS["brook"]` so Clover
	# stands on the dry bank rather than the water.
	_add_box("BrookWaterWest", position + Vector3(-1.55, 0.05, -0.2), Vector3(2.4, 0.04, 0.85), "#88A9BF")
	_add_box("BrookWaterEast", position + Vector3(1.55, 0.05, 0.25), Vector3(2.4, 0.04, 0.85), "#88A9BF")

	# Lighter highlight strips so the water reads as flowing rather than flat.
	# Sits a hair above the main water plane to avoid z-fighting.
	_add_box("BrookWaterHighlightWest", position + Vector3(-1.55, 0.07, -0.2), Vector3(2.2, 0.03, 0.18), "#D9E6EC")
	_add_box("BrookWaterHighlightEast", position + Vector3(1.55, 0.07, 0.25), Vector3(2.2, 0.03, 0.18), "#D9E6EC")

	# Marigold clusters on the banks — Clover's cast-doc orange motif. Each
	# cluster is a soft green tuft grounding an orange marigold sphere with a
	# pale center bead. Positions alternate banks so the brook feels lined.
	var marigold_offsets := [
		Vector3(-2.05, 0, -0.95),
		Vector3(-1.15, 0, 0.95),
		Vector3(0.40, 0, -0.95),
		Vector3(1.45, 0, 0.95),
		Vector3(2.30, 0, -0.90),
	]
	for offset in marigold_offsets:
		var marigold_center := position + offset
		_add_box(
			"BrookMarigoldTuft",
			marigold_center + Vector3(0, 0.05, 0),
			Vector3(0.58, 0.04, 0.32),
			"#5F7F64"
		)
		_add_sphere(
			"BrookMarigoldPetals",
			marigold_center + Vector3(0, 0.18, 0),
			0.16,
			"#F0A35A"
		)
		_add_sphere(
			"BrookMarigoldCenter",
			marigold_center + Vector3(0, 0.24, 0),
			0.06,
			"#FFE8B0"
		)
