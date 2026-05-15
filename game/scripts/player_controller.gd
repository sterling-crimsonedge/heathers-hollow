extends CharacterBody3D

signal interact_requested(villager: Node)
signal nearby_villager_changed(villager: Node)

@export var movement_speed := 4.2
@export var acceleration := 14.0
@export var deceleration := 18.0
@export var camera_turn_speed := 2.4

@onready var interaction_area: Area3D = $InteractionArea
@onready var spring_arm: SpringArm3D = $SpringArm3D

var nearby_villagers: Array = []
var current_nearby_villager = null

func _ready() -> void:
	_ensure_input_actions()
	interaction_area.body_entered.connect(_on_body_entered)
	interaction_area.body_exited.connect(_on_body_exited)

func _physics_process(delta: float) -> void:
	_update_camera(delta)
	_update_movement(delta)
	_update_nearest_villager()

	if Input.is_action_just_pressed("interact") and current_nearby_villager != null:
		interact_requested.emit(current_nearby_villager)

func _update_camera(delta: float) -> void:
	var orbit := Input.get_vector("camera_left", "camera_right", "camera_up", "camera_down")
	if absf(orbit.x) > 0.05:
		spring_arm.rotation.y -= orbit.x * camera_turn_speed * delta

func _update_movement(delta: float) -> void:
	var input_vector := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var desired_velocity := Vector3.ZERO

	if input_vector.length() > 0.01:
		var camera_basis := spring_arm.global_transform.basis
		var forward := -camera_basis.z
		forward.y = 0.0
		forward = forward.normalized()

		var right := camera_basis.x
		right.y = 0.0
		right = right.normalized()

		var move_direction := (right * input_vector.x + forward * -input_vector.y).normalized()
		var speed := movement_speed
		if Input.is_action_pressed("sprint"):
			speed *= 1.28
		desired_velocity = move_direction * speed
		rotation.y = lerp_angle(rotation.y, atan2(-move_direction.x, -move_direction.z), delta * 12.0)

	var rate := acceleration if desired_velocity.length() > 0.0 else deceleration
	velocity.x = move_toward(velocity.x, desired_velocity.x, rate * delta)
	velocity.z = move_toward(velocity.z, desired_velocity.z, rate * delta)
	velocity.y = 0.0
	move_and_slide()

func _update_nearest_villager() -> void:
	var nearest: Node = null
	var nearest_distance := INF
	for villager in nearby_villagers:
		if not is_instance_valid(villager):
			continue
		var distance := global_position.distance_to(villager.global_position)
		if distance < nearest_distance:
			nearest = villager
			nearest_distance = distance

	if nearest != current_nearby_villager:
		current_nearby_villager = nearest
		nearby_villager_changed.emit(current_nearby_villager)

func _on_body_entered(body: Node) -> void:
	if body.is_in_group("villager") and not nearby_villagers.has(body):
		nearby_villagers.append(body)

func _on_body_exited(body: Node) -> void:
	if nearby_villagers.has(body):
		nearby_villagers.erase(body)
		if current_nearby_villager == body:
			current_nearby_villager = null
			nearby_villager_changed.emit(null)

func _ensure_input_actions() -> void:
	_add_key_action("move_left", [KEY_A, KEY_LEFT])
	_add_key_action("move_right", [KEY_D, KEY_RIGHT])
	_add_key_action("move_forward", [KEY_W, KEY_UP])
	_add_key_action("move_back", [KEY_S, KEY_DOWN])
	_add_key_action("camera_left", [KEY_Q])
	_add_key_action("camera_right", [KEY_R])
	_add_key_action("interact", [KEY_E, KEY_ENTER])
	_add_key_action("cancel", [KEY_ESCAPE, KEY_BACKSPACE])
	_add_key_action("inventory", [KEY_I, KEY_TAB])
	_add_key_action("gift", [KEY_G])
	_add_key_action("pause", [KEY_ESCAPE])
	_add_key_action("sprint", [KEY_SHIFT])

	_add_joy_axis_action("move_left", JOY_AXIS_LEFT_X, -1.0)
	_add_joy_axis_action("move_right", JOY_AXIS_LEFT_X, 1.0)
	_add_joy_axis_action("move_forward", JOY_AXIS_LEFT_Y, -1.0)
	_add_joy_axis_action("move_back", JOY_AXIS_LEFT_Y, 1.0)
	_add_joy_axis_action("camera_left", JOY_AXIS_RIGHT_X, -1.0)
	_add_joy_axis_action("camera_right", JOY_AXIS_RIGHT_X, 1.0)
	_add_joy_axis_action("camera_up", JOY_AXIS_RIGHT_Y, -1.0)
	_add_joy_axis_action("camera_down", JOY_AXIS_RIGHT_Y, 1.0)

	_add_joy_button_action("move_left", JOY_BUTTON_DPAD_LEFT)
	_add_joy_button_action("move_right", JOY_BUTTON_DPAD_RIGHT)
	_add_joy_button_action("move_forward", JOY_BUTTON_DPAD_UP)
	_add_joy_button_action("move_back", JOY_BUTTON_DPAD_DOWN)
	_add_joy_button_action("interact", JOY_BUTTON_A)
	_add_joy_button_action("cancel", JOY_BUTTON_B)
	_add_joy_button_action("inventory", JOY_BUTTON_X)
	_add_joy_button_action("gift", JOY_BUTTON_Y)
	_add_joy_button_action("pause", JOY_BUTTON_START)
	_add_joy_button_action("sprint", JOY_BUTTON_RIGHT_SHOULDER)

func _ensure_action(action_name: StringName, deadzone := 0.23) -> void:
	if not InputMap.has_action(action_name):
		InputMap.add_action(action_name, deadzone)
	else:
		InputMap.action_set_deadzone(action_name, deadzone)

func _add_key_action(action_name: StringName, keycodes: Array[int]) -> void:
	_ensure_action(action_name)
	for keycode in keycodes:
		var event := InputEventKey.new()
		event.keycode = keycode
		event.physical_keycode = keycode
		InputMap.action_add_event(action_name, event)

func _add_joy_axis_action(action_name: StringName, axis: int, axis_value: float) -> void:
	_ensure_action(action_name)
	var event := InputEventJoypadMotion.new()
	event.axis = axis
	event.axis_value = axis_value
	InputMap.action_add_event(action_name, event)

func _add_joy_button_action(action_name: StringName, button: int) -> void:
	_ensure_action(action_name)
	var event := InputEventJoypadButton.new()
	event.button_index = button
	InputMap.action_add_event(action_name, event)
