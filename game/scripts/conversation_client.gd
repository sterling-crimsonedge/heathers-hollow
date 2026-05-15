extends Node

signal message_received(message: Dictionary)
signal status_changed(status: String)
signal error_received(message: String)

@export var server_url := "ws://127.0.0.1:8765/ws/conversation"
@export var reconnect_delay := 2.5

var socket := WebSocketPeer.new()
var reconnect_timer := 0.0
var last_state := WebSocketPeer.STATE_CLOSED

func _ready() -> void:
	connect_to_server()

func _process(delta: float) -> void:
	socket.poll()
	var state := socket.get_ready_state()

	if state != last_state:
		last_state = state
		_emit_state(state)

	if state == WebSocketPeer.STATE_OPEN:
		while socket.get_available_packet_count() > 0:
			var raw := socket.get_packet().get_string_from_utf8()
			var parsed = JSON.parse_string(raw)
			if typeof(parsed) == TYPE_DICTIONARY:
				message_received.emit(parsed)
			else:
				error_received.emit("Received malformed server message.")
	elif state == WebSocketPeer.STATE_CLOSED:
		reconnect_timer -= delta
		if reconnect_timer <= 0.0:
			connect_to_server()

func connect_to_server() -> void:
	reconnect_timer = reconnect_delay
	socket = WebSocketPeer.new()
	var error := socket.connect_to_url(server_url)
	if error != OK:
		error_received.emit("Could not connect to AI server at %s." % server_url)
		status_changed.emit("AI server unavailable")

func send_player_message(villager_id: String, player_id: String, text: String, context := {}) -> bool:
	if socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		error_received.emit("AI server is not connected yet.")
		return false

	var payload := {
		"type": "player_message",
		"villager_id": villager_id,
		"player_id": player_id,
		"text": text,
		"context": context
	}
	socket.send_text(JSON.stringify(payload))
	return true

func send_gift(villager_id: String, player_id: String, item: Dictionary, context := {}) -> bool:
	if socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		error_received.emit("AI server is not connected yet.")
		return false

	var payload := {
		"type": "gift_item",
		"villager_id": villager_id,
		"player_id": player_id,
		"item": item,
		"context": context
	}
	socket.send_text(JSON.stringify(payload))
	return true

func _emit_state(state: int) -> void:
	match state:
		WebSocketPeer.STATE_CONNECTING:
			status_changed.emit("Connecting to AI server...")
		WebSocketPeer.STATE_OPEN:
			status_changed.emit("AI server connected")
		WebSocketPeer.STATE_CLOSING:
			status_changed.emit("AI server closing")
		WebSocketPeer.STATE_CLOSED:
			status_changed.emit("AI server disconnected")
