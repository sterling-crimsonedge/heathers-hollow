extends CharacterBody3D

@export var villager_id := "margot"
@export var display_name := "Margot"
@export var home_location := "town_square"
@export var idle_line := "The plaza smells like warm tea and garden soil today."

@onready var name_label: Label3D = $NameLabel

func _ready() -> void:
	add_to_group("villager")
	name_label.text = display_name

func apply_public_profile(profile: Dictionary) -> void:
	var next_display_name := str(profile.get("display_name", display_name))
	if not next_display_name.is_empty():
		display_name = next_display_name
		name_label.text = display_name

	var next_home_location := str(profile.get("home_location", home_location))
	if not next_home_location.is_empty():
		home_location = next_home_location

func get_interaction_prompt() -> String:
	return "A / E Talk to %s" % display_name

func get_context() -> Dictionary:
	return {
		"villager_id": villager_id,
		"display_name": display_name,
		"location": home_location,
		"idle_line": idle_line,
		"position": {
			"x": global_position.x,
			"y": global_position.y,
			"z": global_position.z
		}
	}
