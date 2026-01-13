import re

import bpy
from bpy.types import Operator, Panel, UIList

from .constants import (
    BONE_SUFFIX_PATTERNS,
    CONSTRAINT_INFLUENCE,
    CONSTRAINT_OWNER_SPACE,
    CONSTRAINT_TARGET_SPACE,
    CONSTRAINT_TYPE,
    ERROR_HIERARCHY_INVALID,
    ERROR_MIN_BONES_REQUIRED,
    ERROR_NEED_EDIT_MODE,
    ERROR_NO_ARMATURE_SELECTED,
    ERROR_NO_CHAIN_SELECTED,
    ERROR_NOT_ARMATURE,
    JIGGLE_CONFIG_KEY,
    MODE_EDIT,
    MODE_EDIT_ARMATURE,
    MODE_OBJECT,
    SUCCESS_ADDED_CHAIN,
    SUCCESS_CHAIN_UPDATED,
    SUCCESS_CONFIG_SAVED,
    SUCCESS_CONFIG_UPDATED,
    SUCCESS_REMOVED_CHAIN,
    SUCCESS_ROTATION_CHAIN_CREATED,
    SUCCESS_VALID_CHAIN,
    UI_SPLIT_ARROW,
    UI_SPLIT_END_BONE,
    UI_SPLIT_START_BONE,
    WARNING_BONES_NOT_IN_CHAIN,
    WARNING_BRANCHES_DETECTED,
    WARNING_CONFIG_NOT_SAVED,
)
from .properties import JiggleConfigProperty
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

            # Use split with precise proportions
            split = row.split(factor=UI_SPLIT_START_BONE, align=True)
            split.prop(item, "start_bone", text="", emboss=False, icon="BONE_DATA")

            split = split.split(factor=UI_SPLIT_ARROW, align=True)
            split.alignment = "CENTER"
            split.label(text="→")

            split = split.split(factor=UI_SPLIT_END_BONE, align=True)
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
            self.report({"ERROR"}, ERROR_NO_ARMATURE_SELECTED)
            return {"CANCELLED"}

        config = obj.jiggle_config
        config.chains.add()
        config.active_chain_index = len(config.chains) - 1

        # Force update custom property
        success = force_update_config(self, context)
        if not success:
            self.report({"WARNING"}, "Added chain, but failed to save config")
        else:
            self.report({"INFO"}, SUCCESS_ADDED_CHAIN)

        return {"FINISHED"}


class JIGGLE_OT_remove_chain(Operator):
    """Remove selected jiggle bone chain"""

    bl_idname = "jiggle.remove_chain"
    bl_label = "Remove Chain"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, ERROR_NO_ARMATURE_SELECTED)
            return {"CANCELLED"}

        config = obj.jiggle_config
        if 0 <= config.active_chain_index < len(config.chains):
            config.chains.remove(config.active_chain_index)
            config.active_chain_index = max(0, config.active_chain_index - 1)

            # Force update custom property
            success = force_update_config(self, context)
            if not success:
                self.report({"WARNING"}, "Removed chain, but failed to save config")
            else:
                self.report({"INFO"}, SUCCESS_REMOVED_CHAIN)

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
            self.report({"ERROR"}, ERROR_NO_ARMATURE_SELECTED)
            return {"CANCELLED"}

        config = obj.jiggle_config
        if config.active_chain_index < 0 or config.active_chain_index >= len(
            config.chains
        ):
            self.report({"ERROR"}, ERROR_NO_CHAIN_SELECTED)
            return {"CANCELLED"}

        if context.mode != MODE_EDIT_ARMATURE:
            self.report({"WARNING"}, ERROR_NEED_EDIT_MODE)
            return {"CANCELLED"}

        selected_bones = [b.name for b in context.selected_bones]

        # Filter bones to use only one side when mirrored bones are present
        selected_bones = self.filter_bones_by_side(selected_bones)

        if len(selected_bones) < 2:
            self.report({"WARNING"}, ERROR_MIN_BONES_REQUIRED.format(count=2))
            return {"CANCELLED"}

        chain = config.chains[config.active_chain_index]
        chain.start_bone = selected_bones[0]
        chain.end_bone = selected_bones[-1]

        # Validate the chain
        is_valid, error_msg = validate_jiggle_chain(
            obj, chain.start_bone, chain.end_bone
        )
        if not is_valid:
            self.report({"ERROR"}, f"Invalid chain: {error_msg}")
            # Reset invalid chain
            chain.start_bone = ""
            chain.end_bone = ""
            return {"CANCELLED"}

        # Force update custom property
        force_update_config(self, context)

        self.report(
            {"INFO"},
            SUCCESS_CHAIN_UPDATED.format(
                start=selected_bones[0], end=selected_bones[-1]
            ),
        )

        return {"FINISHED"}

    def filter_bones_by_side(self, bone_names):
        """
        Filter bones to use only one side when mirrored bones are present.
        This handles Blender's X-axis mirror feature which automatically
        includes both left and right bones in the selection.

        When mirrored pairs are detected, keeps only the side matching the first bone.
        Uses regex patterns to support common naming conventions like:
        - bone_name.L / bone_name.R
        - bone_name_L / bone_name_R
        - bone_name_left / bone_name_right
        """
        if not bone_names or len(bone_names) < 2:
            return bone_names

        # Parse the first bone to determine target side
        first_bone = bone_names[0]
        first_base, first_side = self._parse_bone_side(first_bone)

        # If first bone has no side suffix, no filtering needed
        if not first_side:
            return bone_names

        # Check if we have mirrored pairs (bones with same base name but different sides)
        has_mirrored_pairs = False
        for bone_name in bone_names[1:]:
            base, side = self._parse_bone_side(bone_name)
            if base == first_base and side and side != first_side:
                has_mirrored_pairs = True
                break

        # If no mirrored pairs detected, return original list
        if not has_mirrored_pairs:
            return bone_names

        # Filter to keep only bones matching the target side or having no side
        filtered_bones = []
        for bone_name in bone_names:
            base, side = self._parse_bone_side(bone_name)
            # Keep bones that match the target side OR have no side suffix OR different base name
            if not side or side == first_side or base != first_base:
                filtered_bones.append(bone_name)

        return filtered_bones if filtered_bones else bone_names

    def _parse_bone_side(self, bone_name):
        """
        Parse a bone name to extract its base name and side suffix.

        Args:
            bone_name: Name of the bone (may include .001, .002, etc. suffixes)

        Returns:
            tuple: (base_name, side_suffix) where side_suffix is L/R/LEFT/RIGHT or empty string
        """
        # Remove Blender's duplicate suffix (.001, .002, etc.)
        bone_name_without_dup = bone_name.rsplit(".", 1)[0]

        # Try each pattern
        for pattern in BONE_SUFFIX_PATTERNS:
            match = re.match(pattern, bone_name_without_dup, re.IGNORECASE)
            if match:
                base, side = match.groups()
                return base.lower(), side.upper()

        # No pattern matched - return original name with no side
        return bone_name_without_dup.lower(), ""


class JIGGLE_OT_create_rotation_chain(Operator):
    """Create copy rotation constraints for a bone chain"""

    bl_idname = "jiggle.create_rotation_chain"
    bl_label = "Create Rotation Chain"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Add Copy Rotation constraints to each bone (except first) to copy from the previous bone in the hierarchy. Constraints use LOCAL space for additive rotation."

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "ARMATURE":
            self.report({"ERROR"}, ERROR_NO_ARMATURE_SELECTED)
            return {"CANCELLED"}

        if context.mode != MODE_EDIT_ARMATURE:
            self.report({"WARNING"}, ERROR_NEED_EDIT_MODE)
            return {"CANCELLED"}

        # Get selected bone names
        selected_bone_names = [b.name for b in context.selected_bones]

        if len(selected_bone_names) < 2:
            self.report({"WARNING"}, ERROR_MIN_BONES_REQUIRED.format(count=2))
            return {"CANCELLED"}

        # Find the topmost bone (highest in hierarchy) among selected bones
        armature = obj.data
        top_bone = self.find_topmost_bone(armature, selected_bone_names)

        if not top_bone:
            self.report({"ERROR"}, ERROR_HIERARCHY_INVALID)
            return {"CANCELLED"}

        # Build the chain from top to bottom
        chain, is_linear, branch_bone = self.build_chain_from_top(
            top_bone, selected_bone_names
        )

        if len(chain) < 2:
            self.report({"ERROR"}, ERROR_MIN_BONES_REQUIRED.format(count=2))
            return {"CANCELLED"}

        # Validate that all selected bones are in the chain
        missing_bones = set(selected_bone_names) - set(chain)
        if missing_bones:
            self.report(
                {"WARNING"},
                WARNING_BONES_NOT_IN_CHAIN.format(
                    bones=", ".join(sorted(missing_bones))
                ),
            )

        # Check if chain is linear
        if not is_linear:
            self.report(
                {"WARNING"},
                WARNING_BRANCHES_DETECTED.format(bone=branch_bone),
            )

        # Switch to object mode to add constraints
        bpy.ops.object.mode_set(mode=MODE_OBJECT)

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
                if constraint.type == CONSTRAINT_TYPE and constraint.target == obj:
                    existing_constraint = constraint
                    break

            if existing_constraint:
                # Update existing constraint
                existing_constraint.subtarget = prev_bone_name
                existing_constraint.owner_space = CONSTRAINT_OWNER_SPACE
                existing_constraint.target_space = CONSTRAINT_TARGET_SPACE
                existing_constraint.influence = CONSTRAINT_INFLUENCE
            else:
                # Create the Copy Rotation constraint
                constraint = pose_bone.constraints.new(type=CONSTRAINT_TYPE)
                constraint.target = obj
                constraint.subtarget = prev_bone_name
                constraint.owner_space = CONSTRAINT_OWNER_SPACE
                constraint.target_space = CONSTRAINT_TARGET_SPACE
                constraint.influence = CONSTRAINT_INFLUENCE

        # Switch back to edit mode
        bpy.ops.object.mode_set(mode=MODE_EDIT)

        self.report({"INFO"}, SUCCESS_ROTATION_CHAIN_CREATED.format(count=len(chain)))
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
            if context.mode == MODE_EDIT_ARMATURE:
                row.operator(
                    "jiggle.set_chain_from_selection", icon="RESTRICT_SELECT_OFF"
                )
            else:
                row.label(text=ERROR_NEED_EDIT_MODE, icon="INFO")

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
                        text=SUCCESS_VALID_CHAIN.format(count=len(bones)),
                        icon="CHECKMARK",
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
        if JIGGLE_CONFIG_KEY in obj:
            status_box.label(text=SUCCESS_CONFIG_SAVED, icon="CHECKMARK")
        else:
            status_box.label(text=WARNING_CONFIG_NOT_SAVED, icon="ERROR")

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
        if context.mode == MODE_EDIT_ARMATURE:
            row.operator("jiggle.create_rotation_chain", icon="CONSTRAINT")
        else:
            row.label(text=ERROR_NEED_EDIT_MODE, icon="INFO")

        # Instructions
        if context.mode == MODE_EDIT_ARMATURE:
            info_row = box.row()
            info_row.label(
                text=f"{ERROR_MIN_BONES_REQUIRED.format(count=2)}, then click above",
                icon="INFO",
            )


def force_update_config(op, context):
    """Force update armature's custom properties with current config as JSON"""
    obj = context.active_object
    if obj and obj.type == "ARMATURE" and hasattr(obj, "jiggle_config"):
        try:
            json_string = obj.jiggle_config.to_json()
            obj[JIGGLE_CONFIG_KEY] = json_string
            op.report(
                {"INFO"},
                SUCCESS_CONFIG_UPDATED.format(count=len(obj.jiggle_config.chains)),
            )
            return True
        except Exception as e:
            op.report({"ERROR"}, f"Failed to update config: {str(e)}")
            return False
    else:
        op.report({"ERROR"}, ERROR_NOT_ARMATURE)
        return False


def register():
    bpy.types.Object.jiggle_config = bpy.props.PointerProperty(
        type=JiggleConfigProperty
    )


def unregister():
    del bpy.types.Object.jiggle_config
