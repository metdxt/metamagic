extends EditorScenePostImportPlugin

func _post_process(scene: Node) -> void:
	# Find all Node3D nodes in the imported scene
	var nodes = scene.find_children("*", "Node3D", true)

	# Include root if it's a Node3D
	if scene is Node3D:
		nodes.append(scene)

	for node in nodes:
		_process_node(scene, node)

func _process_node(scene: Node, node: Node3D) -> void:
	var extras = node.get_meta("extras", {})
	if not extras is Dictionary:
		return

	var meta_str = extras.get("metamagic_bone_attachment", "")
	if meta_str == "":
		return

	var data = JSON.parse_string(meta_str)
	if not data or not data is Dictionary:
		return

	var armature_name = data.get("armature", "")
	var bone_name = data.get("bone", "")

	if armature_name == "" or bone_name == "":
		return

	# Find the skeleton in the scene
	var skeleton: Skeleton3D = _find_skeleton(scene, armature_name)

	if not skeleton:
		push_error("[Metamagic] Could not find skeleton named: '%s'! BoneAttachment import plugin will have no effect." % [armature_name])
		return

	var skeleton_parent = skeleton.get_parent() as Node3D
	if not skeleton_parent:
		push_error("[Metamagic] Skeleton3D does not have valid parent!BoneAttachment import plugin will have no effect.")
		return


	var bone_idx = skeleton.find_bone(bone_name)
	if bone_idx == -1:
		push_error("[Metamagic] Bone '%s' not found in skeleton '%s' for node '%s'" % [bone_name, armature_name, node.name])
		return

	# Calculate relative position of the node to the rest pose of the bone
	# we're attaching to. This is needed to put it in the right place, where
	# its seen in Blender. We can't use BoneAttachment3D transform because
	# it gives us scuffed and useless zero transform.
	var rest_transform = skeleton.get_bone_global_pose(bone_idx)
	var delta_position = node.position - (rest_transform.origin + skeleton_parent.position)

	# Create BoneAttachment3D
	var ba = BoneAttachment3D.new()
	ba.name = "BA_" + bone_name + "_" + node.name
	ba.bone_name = bone_name

	skeleton.add_child(ba)
	ba.owner = scene

	# Reparent the node to the BoneAttachment3D, resetting the owner so that the warning shuts up
	node.owner = null
	node.reparent(ba)
	node.owner = scene
	node.position = delta_position


func _find_skeleton(scene: Node, armature_name: String) -> Skeleton3D:
	var skeletons = scene.find_children("*", "Skeleton3D", true)
	for s in skeletons:
		# In many Blender GLTF exports, the Skeleton3D is a child of a Node3D named after the Armature
		if s.get_parent().name == armature_name:
			return s as Skeleton3D
		# Fallback: check if the skeleton itself is named after the armature
		if s.name == armature_name:
			return s as Skeleton3D
	return null
