@tool
extends Node3D
## Tool script attached by the Metamagic variant post-import plugin.
##
## Reads variant group configuration from the [code]_metamagic_variants[/code]
## metadata (written during post-import) and exposes a dropdown for each group
## in the Inspector via [method _get_property_list].  Selecting a variant
## instantiates the corresponding [PackedScene] on demand and frees the
## previously active instance — only one variant per group is alive at a time.
##
## Each variant group gets its own internal [Node3D] container (named after the
## group) added with [constant Node.INTERNAL_MODE_BACK].  This keeps the
## instantiated variant subtrees out of the visible scene-tree hierarchy while
## still rendering and functioning normally.  Because the containers are
## internal they are not serialised with the scene — they are re-created every
## time [method _ready] fires, driven by the persisted [member _selections].

# Stores the current selection index per group name.
# { "group_name": int, ... }
# @export_storage persists this into the scene file so choices survive save/load.
@export_storage var _selections: Dictionary = {}

# Cache of the config dictionary read from metadata.
var _config: Dictionary = {}

# Maps group_name -> internal Node3D container that holds the variant instance.
var _containers: Dictionary = {}

# Maps group_name -> currently instantiated Node (or null).
var _instances: Dictionary = {}

# Metadata tags so we can positively identify our nodes.
const _CONTAINER_META := "_metamagic_variant_container"
const _INSTANCE_META := "_metamagic_variant_instance"


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
			var default_idx: int = group.get("default_index", 0)
			# Optional groups may legitimately default to -1 (nothing shown).
			_selections[group_name] = default_idx


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

		var is_optional: bool = group.get("optional", false)

		# Build the comma-separated enum hint string.
		# Optional groups get a leading "(None)" entry so the user can
		# deselect all variants.
		var enum_names := PackedStringArray(names)
		if is_optional:
			enum_names = PackedStringArray(["(None)"]) + enum_names
		var hint_string := ",".join(enum_names)

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

	var group: Dictionary = _config[group_name]
	var is_optional: bool = group.get("optional", false)

	# For optional groups the enum is offset by 1 because index 0 is "(None)".
	# Translate the UI enum value back to our internal convention where -1 means
	# nothing selected and 0+ are real variant indices.
	var internal: int = value as int
	if is_optional:
		internal -= 1

	_selections[group_name] = internal
	_apply_group(group_name)
	return true


func _get(property: StringName) -> Variant:
	if not (property as String).begins_with("variants/"):
		return null

	var group_name: String = (property as String).substr("variants/".length())

	if not _config.has(group_name):
		return null

	var group: Dictionary = _config[group_name]
	var is_optional: bool = group.get("optional", false)
	var internal: int = _selections.get(group_name, 0)

	# Translate internal index → enum index (offset by 1 for optional groups).
	if is_optional:
		return internal + 1
	return internal


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
	var group: Dictionary = _config[group_name]
	var is_optional: bool = group.get("optional", false)
	var default_idx: int = group.get("default_index", 0)
	# Translate to enum index for optional groups.
	if is_optional:
		return default_idx + 1
	return default_idx


# ---------------------------------------------------------------------------
#   Instantiation helpers
# ---------------------------------------------------------------------------

func _apply_all() -> void:
	for group_name in _config:
		_apply_group(group_name)


func _apply_group(group_name: String) -> void:
	if not _config.has(group_name):
		return

	var group: Dictionary = _config[group_name]
	var scenes: Array = group.get("scenes", [])
	var selected: int = _selections.get(group_name, 0)

	# Resolve the parent node where the internal container should live.
	var parent_path: String = group.get("parent_path", ".")
	var parent := get_node_or_null(NodePath(parent_path))
	if parent == null:
		parent = self

	# Free the previous instance (container stays).
	_free_instance(group_name)

	# -1 means "no variant shown" (optional group with nothing selected).
	if selected < 0 or selected >= scenes.size():
		return

	# Instantiate the selected variant.
	var packed: PackedScene = scenes[selected] as PackedScene
	if packed == null:
		return

	var instance := packed.instantiate()
	if instance == null:
		return

	instance.set_meta(_INSTANCE_META, group_name)

	# Get (or create) the internal container for this group and add the
	# instance inside it.  The container is added with INTERNAL_MODE_BACK
	# so it never appears in the editor scene-tree dock.
	var container := _get_or_create_container(group_name, parent)
	container.add_child(instance)

	_instances[group_name] = instance


func _get_or_create_container(group_name: String, parent: Node) -> Node3D:
	"""Return the internal container for *group_name*, creating it on first
	use.  The container is a plain [Node3D] added as an internal child of
	*parent* so it is invisible in the scene-tree dock."""

	var existing: Node3D = _containers.get(group_name) as Node3D
	if existing != null and is_instance_valid(existing):
		return existing

	var container := Node3D.new()
	container.name = group_name
	container.set_meta(_CONTAINER_META, true)
	parent.add_child(container, false, Node.INTERNAL_MODE_BACK)

	_containers[group_name] = container
	return container


func _free_instance(group_name: String) -> void:
	"""Remove and free the currently instantiated node for *group_name*.
	The container is kept alive so it can be reused on the next switch."""

	var old_instance: Node = _instances.get(group_name)
	if old_instance != null and is_instance_valid(old_instance):
		old_instance.get_parent().remove_child(old_instance)
		old_instance.queue_free()
	_instances.erase(group_name)


func _free_container(group_name: String) -> void:
	"""Remove and free both the instance and its container for *group_name*."""

	_free_instance(group_name)

	var container: Node3D = _containers.get(group_name) as Node3D
	if container != null and is_instance_valid(container):
		container.get_parent().remove_child(container)
		container.queue_free()
	_containers.erase(group_name)


# ---------------------------------------------------------------------------
#   Cleanup
# ---------------------------------------------------------------------------

func _exit_tree() -> void:
	# Free all managed containers (and their instances) when leaving the tree.
	for group_name in _containers.keys():
		_free_container(group_name)
