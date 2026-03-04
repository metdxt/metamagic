@tool
extends Node3D
## Tool script attached by the Metamagic variant post-import plugin.
##
## Reads variant group configuration from the [code]_metamagic_variants[/code]
## metadata (written during post-import) and exposes a dropdown for each group
## in the Inspector via [method _get_property_list].  Selecting a variant
## automatically shows/hides the corresponding scene branches.

# Stores the current selection index per group name.
# { "group_name": int, ... }
# @export_storage persists this into the scene file so choices survive save/load.
@export_storage var _selections: Dictionary = {}

# Cache of the config dictionary read from metadata.
var _config: Dictionary = {}


func _ready() -> void:
	_reload_config()
	_apply_all()


func _reload_config() -> void:
	_config = get_meta("_metamagic_variants", {}) as Dictionary
	if _config.is_empty():
		return

	# Initialise selections that don't exist yet to their default indices.
	for group_name in _config:
		if not _selections.has(group_name):
			var group: Dictionary = _config[group_name]
			_selections[group_name] = group.get("default_index", 0)


# ---------------------------------------------------------------------------
#   Dynamic Inspector properties
# ---------------------------------------------------------------------------

func _get_property_list() -> Array[Dictionary]:
	_reload_config()

	var properties: Array[Dictionary] = []

	if _config.is_empty():
		return properties

	for group_name in _config:
		var group: Dictionary = _config[group_name]
		var names: Array = group.get("names", [])

		if names.is_empty():
			continue

		# Build the comma-separated enum hint string.
		var hint_string := ",".join(PackedStringArray(names))

		properties.append({
			"name":  "variants/" + group_name,
			"type":  TYPE_INT,
			"hint":  PROPERTY_HINT_ENUM,
			"hint_string": hint_string,
			"usage": PROPERTY_USAGE_DEFAULT | PROPERTY_USAGE_EDITOR | PROPERTY_USAGE_STORAGE,
		})

	return properties


func _set(property: StringName, value: Variant) -> bool:
	if not (property as String).begins_with("variants/"):
		return false

	var group_name: String = (property as String).substr("variants/".length())

	if not _config.has(group_name):
		return false

	_selections[group_name] = value as int
	_apply_group(group_name)
	return true


func _get(property: StringName) -> Variant:
	if not (property as String).begins_with("variants/"):
		return null

	var group_name: String = (property as String).substr("variants/".length())

	if not _config.has(group_name):
		return null

	return _selections.get(group_name, 0)


func _property_can_revert(property: StringName) -> bool:
	if not (property as String).begins_with("variants/"):
		return false
	var group_name: String = (property as String).substr("variants/".length())
	return _config.has(group_name)


func _property_get_revert(property: StringName) -> Variant:
	if not (property as String).begins_with("variants/"):
		return null
	var group_name: String = (property as String).substr("variants/".length())
	if not _config.has(group_name):
		return null
	return _config[group_name].get("default_index", 0)


# ---------------------------------------------------------------------------
#   Visibility helpers
# ---------------------------------------------------------------------------

func _apply_all() -> void:
	for group_name in _config:
		_apply_group(group_name)


func _apply_group(group_name: String) -> void:
	if not _config.has(group_name):
		return

	var group: Dictionary = _config[group_name]
	var paths: Array = group.get("paths", [])
	var selected: int = _selections.get(group_name, 0)

	for i in range(paths.size()):
		var node := get_node_or_null(NodePath(paths[i])) as Node3D
		if node:
			_set_branch_visible(node, i == selected)


func _set_branch_visible(node: Node3D, visible: bool) -> void:
	node.visible = visible
