extends EditorScenePostImportPlugin
## Post-import plugin that detects variant metadata written by the Metamagic
## Blender addon and packs each variant subtree into an embedded PackedScene.
##
## For every variant group found it:
##   1. Packs each variant branch into a PackedScene resource.
##   2. Removes the original variant nodes from the scene tree.
##   3. Stores the PackedScene resources and a serialisable config dictionary
##      as metadata on the scene root.
##   4. Attaches the variant_switcher.gd tool script so the user can pick
##      variants from the Inspector; only the selected variant is instantiated
##      at any given time rather than keeping every variant loaded and hidden.


func _post_process(scene: Node) -> void:
	var groups := _collect_variant_groups(scene)
	if groups.is_empty():
		return

	var config := _build_config_and_pack(scene, groups)
	_remove_variant_nodes(groups)

	# Persist config so the tool script can read it at edit-time.
	scene.set_meta("_metamagic_variants", config)

	# Attach the switcher tool script to the scene root.
	var script_path := "res://addons/metamagic/variant_switcher.gd"
	if ResourceLoader.exists(script_path):
		scene.set_script(load(script_path))
	else:
		push_warning("[Metamagic] variant_switcher.gd not found at: %s – variant Inspector controls will not be available." % script_path)


# ---------------------------------------------------------------------------
#   Gathering
# ---------------------------------------------------------------------------

func _collect_variant_groups(scene: Node) -> Dictionary:
	"""Scan every Node3D in the tree for the ``metamagic_variant`` extras
	property and collect nodes into their declared groups."""

	var all_nodes := scene.find_children("*", "Node3D", true)
	if scene is Node3D:
		all_nodes.push_back(scene)

	# group_name -> { "nodes": Array[Node3D], "default_node": Node3D | null, "optional": bool }
	var groups: Dictionary = {}

	for node in all_nodes:
		var extras = node.get_meta("extras", {})
		if not extras is Dictionary:
			continue

		var meta_str: String = extras.get("metamagic_variant", "")
		if meta_str.is_empty():
			continue

		var data = JSON.parse_string(meta_str)
		if not data or not data is Dictionary:
			continue

		var group_name: String = data.get("group", "")
		var is_default: bool  = data.get("is_default", false)
		var is_optional: bool = data.get("optional", false)

		if group_name.is_empty():
			continue

		if not groups.has(group_name):
			groups[group_name] = { "nodes": [], "default_node": null, "optional": false }

		# Any member flagging optional=true makes the whole group optional.
		if is_optional:
			groups[group_name]["optional"] = true

		groups[group_name]["nodes"].append(node)

		if is_default:
			groups[group_name]["default_node"] = node

	return groups


# ---------------------------------------------------------------------------
#   Config building & packing
# ---------------------------------------------------------------------------

func _build_config_and_pack(scene: Node, groups: Dictionary) -> Dictionary:
	"""Build a config dictionary that stores an embedded PackedScene for each
	variant alongside the human-readable metadata.

	Structure::

	    {
	        "<group_name>": {
	            "scenes":        [PackedScene, ...],  # embedded packed scenes
	            "names":         [String, ...],       # human-readable names
	            "default_index": int,                 # index of the default variant
	            "parent_path":   String,              # scene-relative path to the parent node
	        },
	        ...
	    }
	"""

	var config: Dictionary = {}

	for group_name in groups:
		var g: Dictionary    = groups[group_name]
		var default_node     = g["default_node"]
		var nodes: Array     = g["nodes"]
		var scenes: Array    = []
		var names: Array     = []
		var default_idx: int = 0

		# All variants in a group are assumed to be siblings.  Use the
		# default variant's parent as the instantiation target, falling
		# back to the first variant's parent.
		var ref_node: Node = default_node if default_node != null else (nodes[0] if not nodes.is_empty() else null)
		var parent_path: String = "."
		if ref_node:
			var parent := ref_node.get_parent()
			if parent and parent != scene:
				parent_path = str(scene.get_path_to(parent))

		for i in range(nodes.size()):
			var node: Node = nodes[i]
			var packed := _pack_subtree(node as Node3D)
			if packed:
				scenes.append(packed)
			else:
				# Fallback: store null so indices stay aligned.
				scenes.append(null)

			names.append(node.name as String)

			if node == default_node:
				default_idx = i

		# Fallback – treat the first node as the default when none was
		# explicitly marked in Blender.
		if default_node == null and not nodes.is_empty():
			default_idx = 0

		var is_optional: bool = g.get("optional", false)

		# Optional groups with no explicit default → default_index = -1
		# so the switcher starts with nothing instantiated.
		if is_optional and default_node == null:
			default_idx = -1

		config[group_name] = {
			"scenes":        scenes,
			"names":         names,
			"default_index": default_idx,
			"parent_path":   parent_path,
			"optional":      is_optional,
		}

	return config


func _pack_subtree(node: Node3D) -> PackedScene:
	"""Duplicate a node's entire subtree and pack it into a new PackedScene.

	The duplicate is used so that the original node (still part of the
	imported scene tree) is not disturbed until we explicitly remove it
	later.  Ownership is reassigned so that ``PackedScene.pack()`` picks
	up every descendant."""

	var dupe := node.duplicate()

	# pack() only serialises nodes whose owner == the root passed to pack().
	# After duplicate() the owner references are stale, so reset them.
	_set_owner_recursive(dupe, dupe)

	var packed := PackedScene.new()
	var err := packed.pack(dupe)

	# The duplicate was only needed for packing – discard it.
	dupe.free()

	if err != OK:
		push_warning("[Metamagic] Failed to pack variant subtree '%s': %s" % [node.name, error_string(err)])
		return null

	return packed


# ---------------------------------------------------------------------------
#   Tree cleanup
# ---------------------------------------------------------------------------

func _remove_variant_nodes(groups: Dictionary) -> void:
	"""Remove the original variant nodes from the imported scene tree.

	This is safe because each subtree has already been packed into a
	PackedScene stored in the config metadata."""

	for group_name in groups:
		var nodes: Array = groups[group_name]["nodes"]
		for node in nodes:
			var parent: Node = node.get_parent()
			if parent == null:
				# Cannot remove the scene root itself.
				push_warning("[Metamagic] Variant node '%s' is the scene root and cannot be removed." % node.name)
				continue
			parent.remove_child(node)
			node.free()


# ---------------------------------------------------------------------------
#   Utility
# ---------------------------------------------------------------------------

func _set_owner_recursive(node: Node, owner: Node) -> void:
	"""Recursively assign *owner* to every descendant of *node* so that
	``PackedScene.pack()`` will include the full subtree."""

	for child in node.get_children():
		child.owner = owner
		_set_owner_recursive(child, owner)
