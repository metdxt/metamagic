extends EditorScenePostImportPlugin



func _post_process(scene: Node) -> void:
	var skeletons: Array = scene.find_children("*", "Skeleton3D", true)
	for skeleton in skeletons:
		process_skeleton(scene, skeleton as Skeleton3D)

func process_skeleton(scene: Node, skeleton: Skeleton3D):
	# get actual node with metadata about jiggle physics
	var armature_node_3d = skeleton.get_parent()
	var meta_str = armature_node_3d.get_meta("extras", {}).get("jiggle_bones_config", "[]")
	var meta = JSON.parse_string(meta_str) as Array
	if not meta:
		return

	var sbs = SpringBoneSimulator3D.new()
	sbs.name = "JigglePhysics"
	skeleton.add_child(sbs)
	sbs.owner = scene

	var chain_idx = 0
	for chain_def in meta:
		var start_bone = chain_def.get("start_bone") as String
		var end_bone = chain_def.get("end_bone") as String
		if not start_bone or not end_bone:
			continue

		var start_bone_idx = skeleton.find_bone(start_bone)
		var end_bone_idx = skeleton.find_bone(end_bone)
		if start_bone_idx == -1 or end_bone_idx == -1:
			continue
		sbs.setting_count += 1
		sbs.set_root_bone(chain_idx, start_bone_idx)
		sbs.set_end_bone(chain_idx, end_bone_idx)

		# Extract properties with null tolerance
		var stiffness = chain_def.get("stiffness", 1.0) as float
		var drag = chain_def.get("drag", 0.4) as float
		var gravity = chain_def.get("gravity", 0.0) as float
		var radius = chain_def.get("radius", 0.02) as float
		var extend_end_bone = chain_def.get("extend_end_bone", false) as bool

		# Set properties on sbs
		sbs.set_stiffness(chain_idx, stiffness)
		sbs.set_drag(chain_idx, drag)
		sbs.set_gravity(chain_idx, gravity)
		sbs.set_radius(chain_idx, radius)
		sbs.set_extend_end_bone(chain_idx, extend_end_bone)

		chain_idx += 1
