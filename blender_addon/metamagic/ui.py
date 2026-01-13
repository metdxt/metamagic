import bpy
from bpy.types import Operator, Panel, UIList

from .properties import JiggleChainProperty, JiggleConfigProperty
from .utils import get_bones_in_chain, validate_jiggle_chain


class JIGGLE_UL_chains(UIList):
    """UI list for displaying jiggle bone chains"""

    bl_idname = "JIGGLE_UL_chains"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Validate bones and show status
            is_valid = False
            status_icon = "ERROR"
            obj = context.active_object

            if obj and obj.type == "ARMATURE" and item.start_bone and item.end_bone:
                is_valid, error_msg = validate_jiggle_chain(
                    obj, item.start_bone, item.end_bone
                )
                status_icon = "CHECKMARK" if is_valid else "ERROR"

            # Use split with precise proportions - start bone 30%, arrow 10%, end bone 55%, status 5%
            split = row.split(factor=0.30, align=True)
            split.prop(item, "start_bone", text="", emboss=False, icon="BONE_DATA")

            split = split.split(factor=0.1429, align=True)
            split.alignment = "CENTER"
            split.label(text="→")

            split = split.split(factor=0.9167, align=True)
            split.prop(item, "end_bone", text="", emboss=False, icon="BONE_DATA")

            split.alignment = "CENTER"
            split.label(icon=status_icon)

        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.prop(item, "start_bone", text="", emboss=False)


class JIGGLE_OT_add_chain(Operator):
    """Add a new jiggle bone chain"""

    bl_idname = "jiggle.add_chain"
    bl_label = "Add Chain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, "No armature selected")
            return {"CANCELLED"}

        config = obj.jiggle_config
        config.chains.add()
        config.active_chain_index = len(config.chains) - 1

        # Force update custom property
        force_update_config(self, context)
        self.report({"INFO"}, "Added new jiggle chain")

        return {"FINISHED"}


class JIGGLE_OT_remove_chain(Operator):
    """Remove selected jiggle bone chain"""

    bl_idname = "jiggle.remove_chain"
    bl_label = "Remove Chain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, "No armature selected")
            return {"CANCELLED"}

        config = obj.jiggle_config
        if 0 <= config.active_chain_index < len(config.chains):
            config.chains.remove(config.active_chain_index)
            config.active_chain_index = max(0, config.active_chain_index - 1)

            # Force update custom property
            force_update_config(self, context)
            self.report({"INFO"}, "Removed jiggle chain")

        return {"FINISHED"}


class JIGGLE_OT_force_update(Operator):
    """Force update jiggle configuration in armature custom properties"""

    bl_idname = "jiggle.force_update"
    bl_label = "Force Update"
    bl_options = {"REGISTER"}
    bl_description = "Manually update the custom properties with current config"

    def execute(self, context):
        force_update_config(self, context)
        return {"FINISHED"}


class JIGGLE_OT_set_chain_from_selection(Operator):
    """Set chain bones from current bone selection"""

    bl_idname = "jiggle.set_chain_from_selection"
    bl_label = "From Selection"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Set start and end bones from currently selected bones"

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, "No armature selected")
            return {"CANCELLED"}

        config = obj.jiggle_config
        if config.active_chain_index < 0 or config.active_chain_index >= len(
            config.chains
        ):
            self.report({"ERROR"}, "No chain selected")
            return {"CANCELLED"}

        if context.mode != "EDIT_ARMATURE":
            self.report({"WARNING"}, "Select bones in Edit Mode")
            return {"CANCELLED"}

        selected_bones = [b.name for b in context.selected_bones]

        # Filter bones to use only one side when mirrored bones are present
        selected_bones = self.filter_bones_by_side(selected_bones)

        if len(selected_bones) < 2:
            self.report({"WARNING"}, "Select at least 2 bones")
            return {"CANCELLED"}

        chain = config.chains[config.active_chain_index]
        chain.start_bone = selected_bones[0]
        chain.end_bone = selected_bones[-1]

        # Force update custom property
        force_update_config(self, context)

        self.report(
            {"INFO"}, f"Set chain from '{selected_bones[0]}' to '{selected_bones[-1]}'"
        )

        return {"FINISHED"}

    def filter_bones_by_side(self, bone_names):
        """
        Filter bones to use only one side when mirrored bones are present.
        This handles Blender's X-axis mirror feature which automatically
        includes both left and right bones in the selection.

        When mirrored pairs are detected, keeps only the side matching the first bone.
        """
        if not bone_names or len(bone_names) < 2:
            return bone_names

        # Extract the side suffix from the first bone
        first_bone = bone_names[0]
        first_parts = first_bone.rsplit(".", 1)[0]
        if "_" in first_parts:
            target_side = first_parts.rsplit("_", 1)[-1]
            has_side = True
        else:
            target_side = ""
            has_side = False

        # If first bone has no side suffix, no filtering needed
        if not has_side:
            return bone_names

        # Check if we have mirrored pairs (bones with same base name but different _L/_R)
        has_mirrored_pairs = False
        for bone_name in bone_names[1:]:
            parts = bone_name.rsplit(".", 1)[0]
            if "_" in parts:
                side = parts.rsplit("_", 1)[-1]
                if side and side != target_side:
                    has_mirrored_pairs = True
                    break

        # If no mirrored pairs detected, return original list
        if not has_mirrored_pairs:
            return bone_names

        # Filter to keep only bones matching the first bone's side
        filtered_bones = []
        for bone_name in bone_names:
            parts = bone_name.rsplit(".", 1)[0]
            if "_" in parts:
                side = parts.rsplit("_", 1)[-1]
                # Keep bones that match the target side OR have no side suffix
                if side == target_side or side == "":
                    filtered_bones.append(bone_name)
            else:
                # Bone has no side suffix - keep it
                filtered_bones.append(bone_name)

        return filtered_bones if filtered_bones else bone_names


class JIGGLE_OT_create_rotation_chain(Operator):
    """Create copy rotation constraints for a bone chain"""

    bl_idname = "jiggle.create_rotation_chain"
    bl_label = "Create Rotation Chain"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add Copy Rotation constraints to each bone (except first) to copy from the previous bone in the hierarchy. Constraints use LOCAL space for additive rotation."

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, "No armature selected")
            return {"CANCELLED"}

        if context.mode != "EDIT_ARMATURE":
            self.report({"WARNING"}, "Select bones in Edit Mode")
            return {"CANCELLED"}

        # Get selected bone names
        selected_bone_names = [b.name for b in context.selected_bones]

        if len(selected_bone_names) < 2:
            self.report({"WARNING"}, "Select at least 2 bones")
            return {"CANCELLED"}

        # Find the topmost bone (highest in hierarchy) among selected bones
        armature = obj.data
        top_bone = self.find_topmost_bone(armature, selected_bone_names)

        if not top_bone:
            self.report(
                {"ERROR"},
                "Could not determine bone hierarchy - check parent relationships",
            )
            return {"CANCELLED"}

        # Build the chain from top to bottom
        chain, is_linear, branch_bone = self.build_chain_from_top(
            top_bone, selected_bone_names
        )

        if len(chain) < 2:
            self.report({"ERROR"}, "Chain must have at least 2 bones")
            return {"CANCELLED"}

        # Validate that all selected bones are in the chain
        missing_bones = set(selected_bone_names) - set(chain)
        if missing_bones:
            self.report(
                {"WARNING"},
                f"Selected bones not in chain: {', '.join(sorted(missing_bones))}",
            )

        # Check if chain is linear
        if not is_linear:
            self.report(
                {"WARNING"},
                f"Multiple branches detected at '{branch_bone}' - rotation chain may not work as expected",
            )

        # Switch to object mode to add constraints
        bpy.ops.object.mode_set(mode="OBJECT")

        # Add Copy Rotation constraints to each bone (except the first)
        for i in range(1, len(chain)):
            bone_name = chain[i]
            prev_bone_name = chain[i - 1]

            # Get the pose bone
            pose_bone = obj.pose.bones.get(bone_name)
            if not pose_bone:
                self.report({"ERROR"}, f"Could not find pose bone: {bone_name}")
                continue

            # Check if constraint already exists
            existing_constraint = None
            for constraint in pose_bone.constraints:
                if constraint.type == "COPY_ROTATION" and constraint.target == obj:
                    existing_constraint = constraint
                    break

            if existing_constraint:
                # Update existing constraint
                existing_constraint.subtarget = prev_bone_name
                existing_constraint.owner_space = "LOCAL"
                existing_constraint.target_space = "LOCAL"
                existing_constraint.influence = 1.0
            else:
                # Create the Copy Rotation constraint
                constraint = pose_bone.constraints.new(type="COPY_ROTATION")
                constraint.target = obj
                constraint.subtarget = prev_bone_name
                constraint.owner_space = "LOCAL"
                constraint.target_space = "LOCAL"
                constraint.influence = 1.0

        # Switch back to edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        self.report({"INFO"}, f"Created rotation chain with {len(chain)} bones")
        return {"FINISHED"}

    def find_topmost_bone(self, armature, selected_bones):
        """
        Find the bone that is highest in the hierarchy among the selected bones.
        This is the bone that is not a child of any other selected bone.
        """
        # Check each selected bone to see if it's the topmost
        for bone_name in selected_bones:
            bone = armature.bones.get(bone_name)
            if not bone:
                continue

            # Walk up the parent chain
            is_topmost = True
            current_bone = bone.parent

            while current_bone:
                if current_bone.name in selected_bones:
                    # This bone has a selected parent, so it's not the topmost
                    is_topmost = False
                    break
                current_bone = current_bone.parent

            if is_topmost:
                return bone

        return None

    def build_chain_from_top(self, top_bone, selected_bones):
        """
        Build a list of bones in order from top to bottom, following a linear chain
        of children that are in the selection.

        Returns:
            tuple: (chain_list, is_linear, branch_bone_name_or_None)
        """
        chain = []
        current_bone = top_bone
        armature = top_bone.id_data
        is_linear = True
        branch_bone = None

        while current_bone:
            if current_bone.name in selected_bones:
                chain.append(current_bone.name)

                # Find children of this bone that are in the selection
                children_in_selection = []
                for bone in armature.bones:
                    if bone.parent == current_bone and bone.name in selected_bones:
                        children_in_selection.append(bone)

                # For a linear chain, we expect at most one child in the selection
                if len(children_in_selection) == 0:
                    # End of chain
                    break
                elif len(children_in_selection) == 1:
                    # Continue down the chain
                    current_bone = children_in_selection[0]
                else:
                    # Multiple children in selection - not a linear chain
                    # For this case, we'll use breadth-first to include all
                    # but this is less ideal for rotation chains
                    is_linear = False
                    branch_bone = current_bone.name
                    bfs_chain = self.build_chain_bfs(top_bone, selected_bones)
                    return (bfs_chain, is_linear, branch_bone)
            else:
                break

        return (chain, is_linear, branch_bone)

    def build_chain_bfs(self, top_bone, selected_bones):
        """
        Build a list of bones using breadth-first search.
        This is a fallback when multiple branches are detected.
        """
        chain = []
        bones_to_visit = [top_bone]

        while bones_to_visit:
            current_bone = bones_to_visit.pop(0)

            if current_bone.name in selected_bones:
                chain.append(current_bone.name)

                # Find children that are in the selection
                armature = top_bone.id_data
                for bone in armature.bones:
                    if bone.parent == current_bone and bone.name in selected_bones:
                        bones_to_visit.append(bone)

        return chain


class JIGGLE_PT_jiggle_bones(Panel):
    """Panel for configuring jiggle bone physics"""

    bl_label = "Jiggle Physics"
    bl_idname = "JIGGLE_PT_jiggle_bones"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Metamagic"
    bl_order = 100

    @classmethod
    def poll(cls, context):
        """Only show panel when an armature is selected"""
        obj = context.active_object
        if not obj:
            return False
        if obj.type != "ARMATURE":
            return False
        return True

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if not obj or obj.type != "ARMATURE":
            return

        config = obj.jiggle_config

        # Header
        box = layout.box()
        box.label(text="Jiggle Bone Configuration", icon="BONE_DATA")

        # Chains list
        row = box.row()
        row.template_list(
            "JIGGLE_UL_chains",
            "",
            config,
            "chains",
            config,
            "active_chain_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator("jiggle.add_chain", icon="ADD", text="")
        col.operator("jiggle.remove_chain", icon="REMOVE", text="")

        # Active chain properties
        if 0 <= config.active_chain_index < len(config.chains):
            active_chain = config.chains[config.active_chain_index]
            chain_box = layout.box()
            chain_box.label(text="Chain Configuration", icon="PROPERTIES")

            # Bone selection
            row = chain_box.row()
            row.prop(active_chain, "start_bone")

            row = chain_box.row()
            row.prop(active_chain, "end_bone")

            # Quick select from selection
            row = chain_box.row()
            if context.mode == "EDIT_ARMATURE":
                row.operator(
                    "jiggle.set_chain_from_selection", icon="RESTRICT_SELECT_OFF"
                )
            else:
                row.label(text="Enter Edit Mode to select bones", icon="INFO")

            # Validation info
            if active_chain.start_bone and active_chain.end_bone:
                is_valid, error_msg = validate_jiggle_chain(
                    obj, active_chain.start_bone, active_chain.end_bone
                )

                info_row = chain_box.row()
                if is_valid:
                    # Show chain info
                    bones = get_bones_in_chain(
                        obj, active_chain.start_bone, active_chain.end_bone
                    )
                    info_row.label(
                        text=f"✓ Valid chain ({len(bones)} bones)", icon="CHECKMARK"
                    )
                else:
                    info_row.label(text=f"✗ {error_msg}", icon="ERROR")

            # Physics parameters
            chain_box.separator()
            chain_box.label(text="Physics Parameters", icon="PHYSICS")

            # Stiffness and Drag
            row = chain_box.row()
            row.prop(active_chain, "stiffness")
            row.prop(active_chain, "drag")

            # Gravity and Radius
            row = chain_box.row()
            row.prop(active_chain, "gravity")
            row.prop(active_chain, "radius")

            # Extend End Bone
            row = chain_box.row()
            row.prop(active_chain, "extend_end_bone")

        # Instructions
        if len(config.chains) == 0:
            info_box = layout.box()
            info_box.label(text="Instructions:", icon="INFO")
            info_box.label(text="1. Add a new chain", icon="BLANK1")
            info_box.label(text="2. Select bones in Edit Mode", icon="BLANK1")
            info_box.label(text="3. Click 'From Selection'", icon="BLANK1")

        # Status indicator
        status_box = layout.box()
        if "jiggle_bones_config" in obj:
            status_box.label(text="✓ Config saved to armature", icon="CHECKMARK")
        else:
            status_box.label(text="No config saved yet", icon="ERROR")

        # Force update button
        status_box.operator("jiggle.force_update", icon="FILE_REFRESH")


class JIGGLE_PT_utilities(Panel):
    """Panel for various armature utilities"""

    bl_label = "Utilities"
    bl_idname = "JIGGLE_PT_utilities"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Metamagic"
    bl_order = 200

    @classmethod
    def poll(cls, context):
        """Only show panel when an armature is selected"""
        obj = context.active_object
        if not obj:
            return False
        if obj.type != "ARMATURE":
            return False
        return True

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if not obj or obj.type != "ARMATURE":
            return

        # Rotation chain section
        box = layout.box()
        box.label(text="Rotation Chains", icon="LINKED")

        # Create rotation chain button
        row = box.row()
        if context.mode == "EDIT_ARMATURE":
            row.operator("jiggle.create_rotation_chain", icon="CONSTRAINT")
        else:
            row.label(text="Enter Edit Mode to create rotation chains", icon="INFO")

        # Instructions
        if context.mode == "EDIT_ARMATURE":
            info_row = box.row()
            info_row.label(
                text="Select 2+ bones in hierarchy, then click above", icon="INFO"
            )


def force_update_config(op, context):
    """Force update armature's custom properties with current config as JSON"""
    obj = context.active_object
    if obj and obj.type == "ARMATURE" and hasattr(obj, "jiggle_config"):
        try:
            json_string = obj.jiggle_config.to_json()
            obj["jiggle_bones_config"] = json_string
            op.report(
                {"INFO"}, f"Config updated: {len(obj.jiggle_config.chains)} chain(s)"
            )
        except Exception as e:
            op.report({"ERROR"}, f"Failed to update config: {str(e)}")
    else:
        op.report({"ERROR"}, "No armature with jiggle config found")


def register():
    bpy.types.Object.jiggle_config = bpy.props.PointerProperty(
        type=JiggleConfigProperty
    )


def unregister():
    del bpy.types.Object.jiggle_config
