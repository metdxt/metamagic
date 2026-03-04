extends EditorScenePostImportPlugin
## Post-import plugin that detects variant metadata written by the Metamagic
## Blender addon and sets up variant switching in the imported scene.
##
## For every variant group found it:
##   1. Hides non-default variant branches.
##   2. Stores a serialisable config dictionary as metadata on the scene root.
##   3. Attaches the variant_switcher.gd tool script so the user can pick
##      variants from the Inspector.


func _post_process(scene: Node) -> void:
	var groups := _collect_variant_groups(scene)
	if groups.is_empty():
		return

	var config := _build_config(scene, groups)
	_apply_default_visibility(groups)

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

	# group_name -> { "nodes": Array[Node3D], "default_node": Node3D | null }
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

		if group_name.is_empty():
			continue

		if not groups.has(group_name):
			groups[group_name] = { "nodes": [], "default_node": null }

		groups[group_name]["nodes"].append(node)

		if is_default:
			groups[group_name]["default_node"] = node

	return groups


# ---------------------------------------------------------------------------
#   Config building
# ---------------------------------------------------------------------------

func _build_config(scene: Node, groups: Dictionary) -> Dictionary:
	"""Build a plain Dictionary that can be stored as node metadata and
	later consumed by variant_switcher.gd.

	Structure::

	    {
	        "<group_name>": {
	            "paths":         [NodePath, ...],   # scene-relative paths
	            "names":         [String, ...],      # human-readable names
	            "default_index": int,                # index of the default variant
	        },
	        ...
	    }
	"""

	var config: Dictionary = {}

	for group_name in groups:
		var g: Dictionary    = groups[group_name]
		var default_node     = g["default_node"]
		var nodes: Array     = g["nodes"]
		var paths: Array     = []
		var names: Array     = []
		var default_idx: int = 0

		for i in range(nodes.size()):
			var node: Node = nodes[i]
			paths.append(str(scene.get_path_to(node)))
			names.append(node.name as String)
			if node == default_node:
				default_idx = i

		# Fallback – treat the first node as the default when none was
		# explicitly marked in Blender.
		if default_node == null and not paths.is_empty():
			default_idx = 0

		config[group_name] = {
			"paths":         paths,
			"names":         names,
			"default_index": default_idx,
		}

	return config


# ---------------------------------------------------------------------------
#   Visibility
# ---------------------------------------------------------------------------

func _apply_default_visibility(groups: Dictionary) -> void:
	"""Hide every variant that is not the default for its group."""

	for group_name in groups:
		var g: Dictionary = groups[group_name]
		var default_node  = g["default_node"]

		# Fallback to first node.
		if default_node == null and not g["nodes"].is_empty():
			default_node = g["nodes"][0]

		for node in g["nodes"]:
			if node is Node3D:
				node.visible = (node == default_node)
