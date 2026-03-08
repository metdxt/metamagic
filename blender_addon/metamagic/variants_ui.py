"""UI panels and operators for the Object Variants feature.

Provides a user‑friendly interface in the Metamagic sidebar tab to:
  • Create / remove variant groups
  • Add / remove objects (empties, meshes, etc.) as members of a group
  • Pick which variant is the *default* (visible in viewport & on Godot import)
  • Quickly add all selected objects to the active group
"""

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Operator, Panel, UIList

from .variants import (
    VARIANT_CONFIG_KEY,
    _set_subtree_visibility,
    find_group_for_object,
    sync_variant_custom_properties,
    update_viewport_visibility,
)

# ---------------------------------------------------------------------------
#   UI Lists
# ---------------------------------------------------------------------------


class VARIANTS_UL_groups(UIList):
    """Draws a single row in the variant‑groups list."""

    bl_idname = "VARIANTS_UL_groups"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_property, index
    ):
        group = item
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(group, "name", text="", emboss=False, icon="FILE_3D")
            row.label(text=f"({len(group.members)})")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=group.name, icon="FILE_3D")


class VARIANTS_UL_members(UIList):
    """Draws a single row in the variant‑members list."""

    bl_idname = "VARIANTS_UL_members"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_property, index
    ):
        member = item
        group = data  # The VariantGroupProperty that owns the collection

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)

            # Star icon for the default variant
            is_default = index == group.default_index
            star_icon = "SOLO_ON" if is_default else "SOLO_OFF"
            op = row.operator(
                "variants.set_default",
                text="",
                icon=star_icon,
                emboss=False,
            )
            op.member_index = index

            # Object name (or a placeholder when the pointer is empty)
            if member.obj:
                row.label(text=member.obj.name, icon="OBJECT_DATA")
            else:
                row.label(text="(empty slot)", icon="ERROR")

        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            if member.obj:
                layout.label(text=member.obj.name, icon="OBJECT_DATA")
            else:
                layout.label(text="?", icon="ERROR")


# ---------------------------------------------------------------------------
#   Operators – Group management
# ---------------------------------------------------------------------------


class VARIANTS_OT_add_group(Operator):
    """Add a new variant group"""

    bl_idname = "variants.add_group"
    bl_label = "Add Variant Group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        config = context.scene.variant_config
        group = config.add_group(name=f"VariantGroup.{len(config.groups):03d}")
        config.active_group_index = len(config.groups) - 1
        sync_variant_custom_properties(context.scene)
        return {"FINISHED"}


class VARIANTS_OT_remove_group(Operator):
    """Remove the selected variant group"""

    bl_idname = "variants.remove_group"
    bl_label = "Remove Variant Group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        return len(config.groups) > 0

    def execute(self, context):
        config = context.scene.variant_config
        if not config.remove_group(config.active_group_index):
            self.report({"WARNING"}, "No group to remove")
            return {"CANCELLED"}

        sync_variant_custom_properties(context.scene)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
#   Operators – Member management
# ---------------------------------------------------------------------------


class VARIANTS_OT_add_member(Operator):
    """Add a specific object to the active variant group"""

    bl_idname = "variants.add_member"
    bl_label = "Add Slot"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        return 0 <= config.active_group_index < len(config.groups)

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]
        member = group.members.add()
        group.active_member_index = len(group.members) - 1
        sync_variant_custom_properties(context.scene)
        update_viewport_visibility(context.scene)
        return {"FINISHED"}


class VARIANTS_OT_remove_member(Operator):
    """Remove the selected member from the active variant group"""

    bl_idname = "variants.remove_member"
    bl_label = "Remove Member"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        if not (0 <= config.active_group_index < len(config.groups)):
            return False
        group = config.groups[config.active_group_index]
        return len(group.members) > 0

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]

        if not group.remove_member(group.active_member_index):
            self.report({"WARNING"}, "No member to remove")
            return {"CANCELLED"}

        sync_variant_custom_properties(context.scene)
        update_viewport_visibility(context.scene)
        return {"FINISHED"}


class VARIANTS_OT_add_selected(Operator):
    """Add all currently selected objects to the active variant group"""

    bl_idname = "variants.add_selected"
    bl_label = "Add Selected Objects"
    bl_description = "Add all selected objects to the active variant group"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        if not (0 <= config.active_group_index < len(config.groups)):
            return False
        return len(context.selected_objects) > 0

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]

        added = 0
        skipped_tracked = []
        for obj in context.selected_objects:
            # Don't allow the same object in multiple groups.
            if config.object_is_tracked(obj):
                existing, _, _ = find_group_for_object(config, obj)
                if existing and existing != group:
                    skipped_tracked.append(obj.name)
                    continue
            member = group.add_member(obj)
            if member is not None:
                added += 1

        if skipped_tracked:
            self.report(
                {"WARNING"},
                f"Skipped {len(skipped_tracked)} object(s) already in another group: "
                + ", ".join(skipped_tracked),
            )

        if added > 0:
            group.active_member_index = len(group.members) - 1
            self.report({"INFO"}, f"Added {added} object(s) to '{group.name}'")
        else:
            self.report({"INFO"}, "No new objects to add")

        sync_variant_custom_properties(context.scene)
        update_viewport_visibility(context.scene)
        return {"FINISHED"}


class VARIANTS_OT_set_default(Operator):
    """Set this member as the default (visible) variant"""

    bl_idname = "variants.set_default"
    bl_label = "Set Default Variant"
    bl_options = {"REGISTER", "UNDO"}

    member_index: IntProperty(name="Member Index", default=0)

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        return 0 <= config.active_group_index < len(config.groups)

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]
        if self.member_index < 0 or self.member_index >= len(group.members):
            self.report({"WARNING"}, "Invalid member index")
            return {"CANCELLED"}

        # Optional groups: clicking the current default toggles it off (→ None).
        if group.optional and group.default_index == self.member_index:
            group.default_index = -1
        else:
            group.default_index = self.member_index
        sync_variant_custom_properties(context.scene)
        update_viewport_visibility(context.scene)
        return {"FINISHED"}


class VARIANTS_OT_preview_variant(Operator):
    """Preview a specific variant by showing only it in the viewport"""

    bl_idname = "variants.preview_variant"
    bl_label = "Preview Variant"
    bl_options = {"REGISTER", "UNDO"}

    variant_index: IntProperty(name="Variant Index", default=0)

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        return 0 <= config.active_group_index < len(config.groups)

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]

        # -1 means "preview nothing" (only valid for optional groups).
        if self.variant_index == -1:
            for member in group.members:
                if member.obj:
                    _set_subtree_visibility(member.obj, hidden=True)
            self.report({"INFO"}, "Previewing: (None)")
            return {"FINISHED"}

        if self.variant_index < 0 or self.variant_index >= len(group.members):
            self.report({"WARNING"}, "Invalid variant index")
            return {"CANCELLED"}

        # Temporarily show only this variant (without changing default_index).
        for i, member in enumerate(group.members):
            if member.obj:
                _set_subtree_visibility(member.obj, hidden=(i != self.variant_index))

        member = group.members[self.variant_index]
        name = member.obj.name if member.obj else "(empty)"
        self.report({"INFO"}, f"Previewing: {name}")
        return {"FINISHED"}


class VARIANTS_OT_reset_preview(Operator):
    """Reset viewport visibility back to the default variant for each group"""

    bl_idname = "variants.reset_preview"
    bl_label = "Reset to Defaults"
    bl_description = "Show only the default variant per group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        update_viewport_visibility(context.scene)
        self.report({"INFO"}, "Viewport reset to default variants")
        return {"FINISHED"}


class VARIANTS_OT_move_member(Operator):
    """Move the selected member up or down in the list"""

    bl_idname = "variants.move_member"
    bl_label = "Move Variant Member"
    bl_options = {"REGISTER", "UNDO"}

    direction: StringProperty(name="Direction", default="UP")

    @classmethod
    def poll(cls, context):
        config = context.scene.variant_config
        if not (0 <= config.active_group_index < len(config.groups)):
            return False
        group = config.groups[config.active_group_index]
        return len(group.members) > 1

    def execute(self, context):
        config = context.scene.variant_config
        group = config.groups[config.active_group_index]
        idx = group.active_member_index

        if self.direction == "UP":
            new_idx = idx - 1
        else:
            new_idx = idx + 1

        if new_idx < 0 or new_idx >= len(group.members):
            return {"CANCELLED"}

        group.members.move(idx, new_idx)

        # Track the default if it was one of the swapped items.
        if group.default_index == idx:
            group["default_index"] = new_idx
        elif group.default_index == new_idx:
            group["default_index"] = idx

        group.active_member_index = new_idx

        sync_variant_custom_properties(context.scene)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
#   Panel
# ---------------------------------------------------------------------------


class METAMAGIC_PT_variants(Panel):
    """Panel for managing Object Variants"""

    bl_label = "Object Variants"
    bl_idname = "METAMAGIC_PT_variants"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Metamagic"
    bl_order = 50

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        config = scene.variant_config

        # --- Groups list ---
        box = layout.box()
        box.label(text="Variant Groups", icon="FILE_3D")

        row = box.row()
        row.template_list(
            "VARIANTS_UL_groups",
            "",
            config,
            "groups",
            config,
            "active_group_index",
            rows=3,
        )
        col = row.column(align=True)
        col.operator("variants.add_group", icon="ADD", text="")
        col.operator("variants.remove_group", icon="REMOVE", text="")

        # --- Active group detail ---
        if 0 <= config.active_group_index < len(config.groups):
            group = config.groups[config.active_group_index]

            # Group name (editable) & optional flag
            name_box = layout.box()
            name_box.prop(group, "name", text="Group Name", icon="GREASEPENCIL")
            name_box.prop(group, "optional", icon="GHOST_ENABLED")

            # --- Members list ---
            members_box = layout.box()
            members_box.label(text="Variants", icon="OBJECT_DATA")

            row = members_box.row()
            row.template_list(
                "VARIANTS_UL_members",
                "",
                group,
                "members",
                group,
                "active_member_index",
                rows=4,
            )
            col = row.column(align=True)
            col.operator("variants.add_member", icon="ADD", text="")
            col.operator("variants.remove_member", icon="REMOVE", text="")
            col.separator()
            move_up = col.operator("variants.move_member", icon="TRIA_UP", text="")
            move_up.direction = "UP"
            move_down = col.operator("variants.move_member", icon="TRIA_DOWN", text="")
            move_down.direction = "DOWN"

            # Active member – object picker
            if 0 <= group.active_member_index < len(group.members):
                member = group.members[group.active_member_index]
                prop_row = members_box.row()
                prop_row.prop(member, "obj", text="Object")

            # Quick‑add from selection
            sel_row = members_box.row(align=True)
            sel_row.operator("variants.add_selected", icon="RESTRICT_SELECT_OFF")

            # --- Default variant info ---
            info_box = layout.box()
            info_box.label(text="Default Variant", icon="SOLO_ON")

            if len(group.members) > 0:
                if group.default_index == -1 and group.optional:
                    default_name = "(None – no variant shown)"
                elif 0 <= group.default_index < len(group.members):
                    default_member = group.members[group.default_index]
                    default_name = (
                        default_member.obj.name if default_member.obj else "(empty)"
                    )
                else:
                    default_name = "(none)"
                info_box.label(text=f"  Current: {default_name}", icon="CHECKMARK")
                if group.optional:
                    info_box.label(text="Click star to set/unset default", icon="INFO")
                else:
                    info_box.label(text="Click the star icon to change", icon="INFO")
            else:
                info_box.label(text="Add objects to set a default", icon="INFO")

            # --- Preview controls ---
            preview_box = layout.box()
            preview_box.label(text="Preview", icon="HIDE_OFF")
            if len(group.members) > 0:
                grid = preview_box.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=True,
                    even_rows=True,
                    align=True,
                )

                # Optional groups get a "(None)" preview button.
                if group.optional:
                    op = grid.operator(
                        "variants.preview_variant",
                        text="(None)",
                        icon="GHOST_ENABLED"
                        if group.default_index == -1
                        else "GHOST_DISABLED",
                    )
                    op.variant_index = -1

                for i, member in enumerate(group.members):
                    name = member.obj.name if member.obj else f"Slot {i}"
                    op = grid.operator(
                        "variants.preview_variant",
                        text=name,
                        icon="SOLO_ON" if i == group.default_index else "SOLO_OFF",
                    )
                    op.variant_index = i

            preview_box.operator("variants.reset_preview", icon="FILE_REFRESH")

            # --- Status ---
            status_box = layout.box()
            has_data = any(VARIANT_CONFIG_KEY in m.obj for m in group.members if m.obj)
            if has_data:
                status_box.label(
                    text="✓ Variant metadata saved on objects",
                    icon="CHECKMARK",
                )
            else:
                status_box.label(
                    text="Add objects & they will be tagged automatically",
                    icon="INFO",
                )

        elif len(config.groups) == 0:
            # Empty state instructions
            info_box = layout.box()
            info_box.label(text="Getting started:", icon="INFO")
            info_box.label(text="1. Click '+' to create a variant group", icon="BLANK1")
            info_box.label(text="2. Select objects (e.g. mod_* empties)", icon="BLANK1")
            info_box.label(text="3. Click 'Add Selected Objects'", icon="BLANK1")
            info_box.label(text="4. Choose a default with the star icon", icon="BLANK1")
