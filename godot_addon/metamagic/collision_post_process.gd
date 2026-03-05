extends EditorScenePostImportPlugin
## Post-import plugin that detects collision metadata written by the Metamagic
## Blender addon and converts tagged Empty nodes into physics body nodes
## (e.g. StaticBody3D) with an appropriate CollisionShape3D child.
##
## This mirrors the classic Collada ``-colonly`` workflow but works with
## straight ``.blend`` file imports.  The Blender-side addon writes a
## ``metamagic_collision`` JSON custom property on each tagged Empty that
## encodes the desired shape type, body type, display size, and optional
## physics parameters.


func _post_process(scene: Node) -> void:
	# Collect candidates first so we don't mutate the tree while iterating.
	var candidates: Array[Dictionary] = []

	var all_nodes := scene.find_children("*", "Node3D", true)
	if scene is Node3D:
		all_nodes.push_back(scene)

	for node in all_nodes:
		var meta := _read_collision_meta(node)
		if meta.is_empty():
			continue
		candidates.append({"node": node, "meta": meta})

	for entry in candidates:
		_convert_node(scene, entry["node"] as Node3D, entry["meta"] as Dictionary)


# ---------------------------------------------------------------------------
#   Metadata reading
# ---------------------------------------------------------------------------

func _read_collision_meta(node: Node) -> Dictionary:
	var extras = node.get_meta("extras", {})
	if not extras is Dictionary:
		return {}

	var meta_str: String = extras.get("metamagic_collision", "")
	if meta_str.is_empty():
		return {}

	var data = JSON.parse_string(meta_str)
	if not data or not data is Dictionary:
		return {}

	# Minimum required key.
	if not data.has("shape"):
		return {}

	return data


# ---------------------------------------------------------------------------
#   Node conversion
# ---------------------------------------------------------------------------

func _convert_node(scene: Node, node: Node3D, meta: Dictionary) -> void:
	var shape_name: String = meta.get("shape", "SphereShape3D")
	var body_type: String  = meta.get("body_type", "StaticBody3D")
	var display_size: float = meta.get("size", 1.0)
	var margin: float      = meta.get("margin", 0.0)
	var col_layer: int     = meta.get("collision_layer", 1)
	var col_mask: int      = meta.get("collision_mask", 1)

	# --- Extract scale and bake it into shape dimensions ---------------------
	# Physics bodies with non-uniform scale trigger warnings in Godot, so we
	# pull the scale out of the transform, multiply it into the shape size,
	# and give the body a clean uniform-scale transform.
	var node_scale: Vector3 = node.transform.basis.get_scale()
	var shape_scale := Vector3(
		display_size * node_scale.x,
		display_size * node_scale.y,
		display_size * node_scale.z,
	)

	# --- Create the collision shape resource ---------------------------------
	var shape_resource: Shape3D = _create_shape(shape_name, shape_scale)
	if shape_resource == null:
		push_warning("[Metamagic] Unsupported collision shape '%s' on node '%s', skipping." % [shape_name, node.name])
		return

	if margin > 0.0 and shape_resource.has_method("set_margin"):
		shape_resource.margin = margin

	# --- Build the CollisionShape3D -----------------------------------------
	var col_shape := CollisionShape3D.new()
	col_shape.shape = shape_resource

	# --- Build the physics body ---------------------------------------------
	var body: CollisionObject3D = _create_body(body_type)
	if body == null:
		push_warning("[Metamagic] Unsupported body type '%s' on node '%s', falling back to StaticBody3D." % [body_type, node.name])
		body = StaticBody3D.new()

	# Strip scale from the transform so the body has uniform scale (1,1,1).
	# The original scale has been baked into the collision shape dimensions.
	var clean_basis := node.transform.basis.orthonormalized()
	body.transform = Transform3D(clean_basis, node.transform.origin)
	body.collision_layer = col_layer
	body.collision_mask = col_mask

	# Add the collision shape as a child of the body.
	# NOTE: col_shape.owner is set later, after body is in the scene tree.
	body.add_child(col_shape)

	# --- Replace the original node in the tree ------------------------------
	var parent := node.get_parent()
	if parent == null:
		# The node IS the scene root – replace in-place.
		push_warning("[Metamagic] Cannot replace scene root '%s' with a collision body. Add a parent node above it." % node.name)
		body.queue_free()
		return

	# Remember the original name and position before removing the node.
	var original_name: String = node.name
	var idx := node.get_index()

	# Name the body and collision shape after the original empty.
	body.name = original_name
	col_shape.name = original_name + "_col"

	# Reparent any children of the original empty onto the body so the
	# sub-tree (meshes, other empties, etc.) is preserved.
	var children: Array[Node] = []
	for child in node.get_children():
		children.append(child)
	for child in children:
		child.owner = null
		child.reparent(body)

	# Remove the original node BEFORE adding the body so there's no name
	# collision that would cause Godot to auto-rename the body.
	parent.remove_child(node)
	node.queue_free()

	# Now add the body at the same position in the child list.
	parent.add_child(body)
	body.owner = scene
	parent.move_child(body, idx)

	# Now that body is in the tree, owner assignments will stick.
	col_shape.owner = scene
	for child in body.get_children():
		if child == col_shape:
			continue
		child.owner = scene
		_reassign_owner_recursive(child, scene)


# ---------------------------------------------------------------------------
#   Factory helpers
# ---------------------------------------------------------------------------

func _create_body(body_type: String) -> CollisionObject3D:
	match body_type:
		"StaticBody3D":
			return StaticBody3D.new()
		"AnimatableBody3D":
			return AnimatableBody3D.new()
		"RigidBody3D":
			return RigidBody3D.new()
		"Area3D":
			return Area3D.new()
		"CharacterBody3D":
			return CharacterBody3D.new()
		_:
			return null


func _create_shape(shape_name: String, scale: Vector3) -> Shape3D:
	## Create a Shape3D resource whose dimensions incorporate the original
	## node scale so the body itself can stay at uniform scale (1,1,1).
	match shape_name:
		"BoxShape3D":
			var box := BoxShape3D.new()
			# Blender's CUBE empty display_size is the half-extent, so the
			# full box size is 2 * scale on each axis.
			box.size = scale * 2.0
			return box

		"SphereShape3D":
			var sphere := SphereShape3D.new()
			# Use the largest axis so the sphere fully encloses the extent.
			sphere.radius = max(scale.x, max(scale.y, scale.z))
			return sphere

		"CapsuleShape3D":
			var capsule := CapsuleShape3D.new()
			# Height along Y, radius from the wider of X/Z.
			capsule.radius = max(scale.x, scale.z)
			capsule.height = scale.y * 2.0
			return capsule

		"CylinderShape3D":
			var cylinder := CylinderShape3D.new()
			# Height along Y, radius from the wider of X/Z.
			cylinder.radius = max(scale.x, scale.z)
			cylinder.height = scale.y * 2.0
			return cylinder

		"SeparationRayShape3D":
			var ray := SeparationRayShape3D.new()
			# Ray points along Y; use Y scale for length.
			ray.length = scale.y
			return ray

		"WorldBoundaryShape3D":
			# WorldBoundaryShape3D is an infinite plane; no size needed.
			return WorldBoundaryShape3D.new()

		_:
			return null


# ---------------------------------------------------------------------------
#   Utility
# ---------------------------------------------------------------------------

func _reassign_owner_recursive(node: Node, owner: Node) -> void:
	for child in node.get_children():
		child.owner = owner
		_reassign_owner_recursive(child, owner)
