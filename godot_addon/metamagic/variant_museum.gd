@tool
extends RefCounted
## Converts the currently open scene into a "museum" layout in-place.
##
## For every variant group the generator:
##   1. Removes any previously generated museum nodes (safe to re-run).
##   2. Makes all variants visible.
##   3. Spaces them out along the X axis (using mesh AABBs for sizing).
##   4. Adds [Label3D] captions above each variant and each group row.
##   5. Strips the variant switcher script and saves the scene.
##
## Call [method generate] from the editor plugin (e.g. via a Tools menu item).

# -- Metadata tag used to mark nodes we created, so we can clean them up ----

const MUSEUM_META := "_metamagic_museum"

# -- Layout tunables --------------------------------------------------------

## Minimum gap between two variant columns.
const VARIANT_MARGIN := 1.5
## Extra vertical gap between the tallest mesh and its label.
const LABEL_PAD_Y := 0.4
## Minimum width assumed when AABB computation yields nothing useful.
const FALLBACK_SIZE := 2.0
## Gap between group rows along the Z axis.
const GROUP_ROW_MARGIN := 3.0

# -- Colours / sizes --------------------------------------------------------

const GROUP_LABEL_FONT_SIZE := 72
const GROUP_LABEL_COLOR := Color(1.0, 0.85, 0.25) # gold
const VARIANT_LABEL_FONT_SIZE := 48
const VARIANT_LABEL_COLOR := Color(1.0, 1.0, 1.0)


## Entry point — call from [code]plugin.gd[/code].
## Modifies the currently open scene in-place and saves it.
## Returns [constant OK] on success or an error code.
static func generate() -> Error:
	var editor_interface := EditorInterface

	# ---- validate ----------------------------------------------------------
	var root := editor_interface.get_edited_scene_root()
	if not root:
		push_warning("[Metamagic] No scene is currently open — open a variant scene first.")
		return ERR_INVALID_DATA

	var source_path: String = root.scene_file_path
	if source_path.is_empty():
		push_warning(
			"[Metamagic] The current scene has no source file. "
			+ "Right-click your .blend file → New Inherited Scene, "
			+ "save it to disk (Ctrl+S), then try again."
		)
		return ERR_FILE_NOT_FOUND

	var config: Dictionary = root.get_meta("_metamagic_variants", {})
	if config.is_empty():
		push_warning("[Metamagic] The current scene has no variant metadata (_metamagic_variants).")
		return ERR_INVALID_DATA

	# ---- clean up previous run (idempotent) --------------------------------
	_cleanup_museum_nodes(root)

	# ---- strip the variant switcher so it doesn't re-hide anything ---------
	if root.get_script():
		root.set_script(null)

	# ---- layout each group as a row ---------------------------------------
	var row_z := 0.0

	for group_name: String in config:
		var group: Dictionary = config[group_name]
		var paths: Array = group.get("paths", [])
		var names: Array = group.get("names", [])

		if paths.is_empty():
			continue

		# Gather nodes & their bounding boxes.
		var nodes: Array[Node3D] = []
		var aabbs: Array[AABB] = []

		for p in paths:
			var node := root.get_node_or_null(NodePath(p as String)) as Node3D
			nodes.append(node) # may be null
			if node:
				aabbs.append(_compute_subtree_aabb(node))
			else:
				aabbs.append(AABB(Vector3.ZERO, Vector3(FALLBACK_SIZE, FALLBACK_SIZE, FALLBACK_SIZE)))

		# Compute the row height & depth for group label placement.
		var row_max_height := 0.0
		var row_max_depth := 0.0
		for aabb: AABB in aabbs:
			row_max_height = maxf(row_max_height, aabb.size.y)
			row_max_depth = maxf(row_max_depth, aabb.size.z)

		# Place variants side by side along X.
		var cursor_x := 0.0

		for i in range(nodes.size()):
			var node := nodes[i]
			if not node:
				continue

			var aabb: AABB = aabbs[i]
			var width := maxf(aabb.size.x, FALLBACK_SIZE)

			# Show the variant and position it so AABBs don't overlap.
			node.visible = true
			node.position = Vector3(
				cursor_x - aabb.position.x,
				-aabb.position.y,
				row_z - aabb.position.z,
			)

			# ---- variant label -------------------------------------------
			var label_text: String = names[i] if i < names.size() else "Variant_%d" % i
			var label := Label3D.new()
			label.text = label_text
			label.font_size = VARIANT_LABEL_FONT_SIZE
			label.modulate = VARIANT_LABEL_COLOR
			label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			label.position = Vector3(
				width * 0.5,
				aabb.size.y + LABEL_PAD_Y,
				0.0,
			)
			label.name = _safe_node_name("VLabel_%s" % label_text)
			label.set_meta(MUSEUM_META, true)
			node.add_child(label)
			label.owner = root

			cursor_x += width + VARIANT_MARGIN

		# ---- group label (centred above the row) -------------------------
		var group_label := Label3D.new()
		group_label.text = group_name
		group_label.font_size = GROUP_LABEL_FONT_SIZE
		group_label.modulate = GROUP_LABEL_COLOR
		group_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		group_label.outline_size = 12
		group_label.position = Vector3(
			cursor_x * 0.5,
			row_max_height + LABEL_PAD_Y + 1.2,
			row_z,
		)
		group_label.name = _safe_node_name("GLabel_%s" % group_name)
		group_label.set_meta(MUSEUM_META, true)
		root.add_child(group_label)
		group_label.owner = root

		# Advance Z for the next group row.
		row_z += maxf(row_max_depth, FALLBACK_SIZE) + GROUP_ROW_MARGIN

	# ---- save --------------------------------------------------------------
	editor_interface.save_scene()
	print("[Metamagic] ✓ Museum layout applied and scene saved.")
	return OK


# ---------------------------------------------------------------------------
#   Helpers
# ---------------------------------------------------------------------------

## Remove all nodes tagged with [constant MUSEUM_META] so the tool can be
## re-run without duplicating labels.
static func _cleanup_museum_nodes(root: Node) -> void:
	var to_remove: Array[Node] = []
	for child in root.find_children("*"):
		if child.has_meta(MUSEUM_META):
			to_remove.append(child)
	# Remove in reverse so child indices don't shift mid-loop.
	for i in range(to_remove.size() - 1, -1, -1):
		to_remove[i].get_parent().remove_child(to_remove[i])
		to_remove[i].queue_free()


## Compute a merged AABB for the entire subtree rooted at [param node] by
## reading [method Mesh.get_aabb] from every [MeshInstance3D] descendant.
## Works outside the scene tree because it only reads mesh resources and local
## transforms.
static func _compute_subtree_aabb(node: Node3D) -> AABB:
	var result := AABB()
	var found := false

	var meshes := node.find_children("*", "MeshInstance3D", true)
	if node is MeshInstance3D:
		meshes.push_back(node)

	for child in meshes:
		var mi := child as MeshInstance3D
		if not mi or not mi.mesh:
			continue

		var mesh_aabb := mi.mesh.get_aabb()

		# Walk the parent chain back to `node` to build the relative transform.
		var rel := Transform3D.IDENTITY
		var current: Node3D = mi
		while current != node and current != null:
			rel = current.transform * rel
			var parent = current.get_parent()
			current = parent as Node3D if parent is Node3D else null

		var transformed := rel * mesh_aabb
		if not found:
			result = transformed
			found = true
		else:
			result = result.merge(transformed)

	if not found:
		result = AABB(
			Vector3(-FALLBACK_SIZE * 0.5, 0.0, -FALLBACK_SIZE * 0.5),
			Vector3(FALLBACK_SIZE, FALLBACK_SIZE, FALLBACK_SIZE),
		)

	return result


## Sanitise a string for use as a node name.
static func _safe_node_name(text: String) -> String:
	return text.replace("/", "_").replace(":", "_").replace(".", "_")
