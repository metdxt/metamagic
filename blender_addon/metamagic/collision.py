"""Collision shape metadata for Empty objects.

Allows tagging Blender Empty objects so that Godot's post-import plugin
converts them into physics body nodes with an appropriate CollisionShape3D
child.

The shape type can be set explicitly or derived automatically from the
Empty's display type, matching the classic Collada ``-colonly`` convention:

    Single Arrow  → SeparationRayShape3D
    Cube          → BoxShape3D
    Image         → WorldBoundaryShape3D
    Sphere/others → SphereShape3D

The configuration is stored as a JSON custom property
(``metamagic_collision``) on each tagged object so it survives the
``.blend`` file import pipeline into Godot.
"""

import json

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
)
from bpy.types import Operator, Panel, PropertyGroup

from .constants import (
    COLLISION_CONFIG_KEY,
    COLLISION_SHAPE_AUTO,
    COLLISION_SHAPE_BOX,
    COLLISION_SHAPE_CAPSULE,
    COLLISION_SHAPE_CYLINDER,
    COLLISION_SHAPE_ITEMS,
    COLLISION_SHAPE_RAY,
    COLLISION_SHAPE_SPHERE,
    COLLISION_SHAPE_WORLD_BOUNDARY,
    EMPTY_DRAW_TYPE_TO_SHAPE,
    ERROR_COLLISION_NOT_EMPTY,
    SUCCESS_COLLISION_APPLIED,
    SUCCESS_COLLISION_REMOVED,
)

__all__ = [
    "CollisionProperty",
    "COLLISION_OT_enable",
    "COLLISION_OT_disable",
    "COLLISION_OT_batch_enable",
    "METAMAGIC_PT_collision",
    "resolve_shape",
    "register",
    "unregister",
]

# ---------------------------------------------------------------------------
#   Body-type enum items  (Godot node type for the physics body)
# ---------------------------------------------------------------------------

BODY_TYPE_ITEMS = [
    ("StaticBody3D", "Static Body", "StaticBody3D – immovable solid collision"),
    (
        "AnimatableBody3D",
        "Animatable Body",
        "AnimatableBody3D – movable via code/animation",
    ),
    ("RigidBody3D", "Rigid Body", "RigidBody3D – fully simulated physics body"),
    ("Area3D", "Area", "Area3D – trigger / overlap detection zone"),
    ("CharacterBody3D", "Character Body", "CharacterBody3D – character controller"),
]


# ---------------------------------------------------------------------------
#   Helpers
# ---------------------------------------------------------------------------


def resolve_shape(obj: bpy.types.Object) -> str:
    """Return the concrete Godot shape class name for *obj*.

    If the collision property's ``shape_type`` is ``AUTO`` the shape is
    derived from ``obj.empty_display_type`` using
    :data:`EMPTY_DRAW_TYPE_TO_SHAPE`.  Otherwise the explicit override is
    returned directly.
    """
    if not obj or obj.type != "EMPTY":
        return COLLISION_SHAPE_SPHERE

    config = getattr(obj, "collision_config", None)
    if config is None:
        return COLLISION_SHAPE_SPHERE

    if config.shape_type != COLLISION_SHAPE_AUTO:
        return config.shape_type

    return EMPTY_DRAW_TYPE_TO_SHAPE.get(obj.empty_display_type, COLLISION_SHAPE_SPHERE)


def _sync_custom_property(obj: bpy.types.Object) -> None:
    """Write or remove the ``metamagic_collision`` custom property on *obj*.

    Called automatically whenever any collision property changes.
    """
    config = getattr(obj, "collision_config", None)
    if config is None:
        return

    if not config.enabled:
        # Remove stale property when collision is disabled.
        if COLLISION_CONFIG_KEY in obj:
            del obj[COLLISION_CONFIG_KEY]
        return

    shape = resolve_shape(obj)

    data = {
        "shape": shape,
        "body_type": config.body_type,
        "size": obj.empty_display_size,
    }

    # Only include optional overrides when they differ from defaults so
    # the JSON stays lean.
    if config.margin != 0.0:
        data["margin"] = round(config.margin, 4)
    if config.collision_layer != 1:
        data["collision_layer"] = config.collision_layer
    if config.collision_mask != 1:
        data["collision_mask"] = config.collision_mask

    obj[COLLISION_CONFIG_KEY] = json.dumps(data)


# ---------------------------------------------------------------------------
#   Update callbacks
# ---------------------------------------------------------------------------


def _on_collision_property_changed(self, context):
    """Generic callback – keeps the custom property in sync."""
    obj = self.id_data
    if obj:
        _sync_custom_property(obj)


# ---------------------------------------------------------------------------
#   Property group
# ---------------------------------------------------------------------------


class CollisionProperty(PropertyGroup):
    """Per-object configuration stored on every Empty that should become a
    collision shape in Godot."""

    bl_idname = "metamagic_collision_config"

    enabled: BoolProperty(
        name="Collision Shape",
        description=(
            "Tag this Empty so Godot converts it into a physics body "
            "with a CollisionShape3D child on import"
        ),
        default=False,
        update=_on_collision_property_changed,
    )

    shape_type: EnumProperty(
        name="Shape",
        description="Collision shape type (AUTO derives it from the Empty draw type)",
        items=COLLISION_SHAPE_ITEMS,
        default=COLLISION_SHAPE_AUTO,
        update=_on_collision_property_changed,
    )

    body_type: EnumProperty(
        name="Body Type",
        description="Godot physics body node to create",
        items=BODY_TYPE_ITEMS,
        default="StaticBody3D",
        update=_on_collision_property_changed,
    )

    margin: FloatProperty(
        name="Margin",
        description="Collision margin (0 = Godot default)",
        default=0.0,
        min=0.0,
        soft_max=0.1,
        step=0.01,
        precision=4,
        update=_on_collision_property_changed,
    )

    collision_layer: bpy.props.IntProperty(
        name="Layer",
        description="Collision layer bitmask (1 = layer 1 only)",
        default=1,
        min=0,
        update=_on_collision_property_changed,
    )

    collision_mask: bpy.props.IntProperty(
        name="Mask",
        description="Collision mask bitmask (1 = layer 1 only)",
        default=1,
        min=0,
        update=_on_collision_property_changed,
    )


# ---------------------------------------------------------------------------
#   Operators
# ---------------------------------------------------------------------------


class COLLISION_OT_enable(Operator):
    """Enable collision metadata on the active Empty"""

    bl_idname = "metamagic.collision_enable"
    bl_label = "Enable Collision"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "EMPTY"

    def execute(self, context):
        obj = context.active_object
        obj.collision_config.enabled = True
        # _on_collision_property_changed fires automatically via the update
        self.report(
            {"INFO"},
            SUCCESS_COLLISION_APPLIED.format(name=obj.name),
        )
        return {"FINISHED"}


class COLLISION_OT_disable(Operator):
    """Remove collision metadata from the active Empty"""

    bl_idname = "metamagic.collision_disable"
    bl_label = "Disable Collision"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == "EMPTY"
            and getattr(obj, "collision_config", None) is not None
            and obj.collision_config.enabled
        )

    def execute(self, context):
        obj = context.active_object
        obj.collision_config.enabled = False
        self.report(
            {"INFO"},
            SUCCESS_COLLISION_REMOVED.format(name=obj.name),
        )
        return {"FINISHED"}


class COLLISION_OT_batch_enable(Operator):
    """Enable collision on all selected Empties using the active object's settings"""

    bl_idname = "metamagic.collision_batch_enable"
    bl_label = "Apply to Selected Empties"
    bl_description = (
        "Copy the active Empty's collision settings to all other selected Empties"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != "EMPTY":
            return False
        return any(o.type == "EMPTY" and o != obj for o in context.selected_objects)

    def execute(self, context):
        source = context.active_object
        src_cfg = source.collision_config
        count = 0

        for obj in context.selected_objects:
            if obj == source or obj.type != "EMPTY":
                continue

            dst = obj.collision_config
            dst.enabled = src_cfg.enabled
            dst.shape_type = src_cfg.shape_type
            dst.body_type = src_cfg.body_type
            dst.margin = src_cfg.margin
            dst.collision_layer = src_cfg.collision_layer
            dst.collision_mask = src_cfg.collision_mask
            _sync_custom_property(obj)
            count += 1

        self.report({"INFO"}, f"Collision settings applied to {count} Empty(s)")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
#   UI Panel
# ---------------------------------------------------------------------------


# Shape icons for the info display
_SHAPE_ICONS = {
    COLLISION_SHAPE_BOX: "MESH_CUBE",
    COLLISION_SHAPE_SPHERE: "MESH_UVSPHERE",
    COLLISION_SHAPE_CAPSULE: "MESH_CAPSULE",
    COLLISION_SHAPE_CYLINDER: "MESH_CYLINDER",
    COLLISION_SHAPE_RAY: "EMPTY_SINGLE_ARROW",
    COLLISION_SHAPE_WORLD_BOUNDARY: "MESH_PLANE",
}


class METAMAGIC_PT_collision(Panel):
    """Panel for configuring collision shapes on Empty objects"""

    bl_label = "Collision Shape"
    bl_idname = "METAMAGIC_PT_collision"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Metamagic"
    bl_order = 1  # Just after Bone Attachment (order 0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "EMPTY"

    def draw_header(self, context):
        obj = context.active_object
        config = obj.collision_config
        self.layout.prop(config, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        config = obj.collision_config

        layout.active = config.enabled

        if not config.enabled:
            layout.operator(
                "metamagic.collision_enable",
                text="Enable Collision Shape",
                icon="PHYSICS",
            )
            return

        # --- Shape configuration ---
        box = layout.box()
        box.label(text="Shape", icon="PHYSICS")

        box.prop(config, "shape_type")

        # Show the resolved shape when AUTO is selected
        if config.shape_type == COLLISION_SHAPE_AUTO:
            resolved = resolve_shape(obj)
            icon = _SHAPE_ICONS.get(resolved, "DOT")
            box.label(
                text=f"  → {resolved}  (from '{obj.empty_display_type}')",
                icon=icon,
            )

        # --- Body type ---
        box.separator()
        box.prop(config, "body_type")

        # --- Size info ---
        box.separator()
        box.label(text=f"Display Size: {obj.empty_display_size:.3f}", icon="INFO")

        # --- Advanced ---
        adv = layout.box()
        adv.label(text="Advanced", icon="PREFERENCES")
        adv.prop(config, "margin")

        row = adv.row(align=True)
        row.prop(config, "collision_layer")
        row.prop(config, "collision_mask")

        # --- Batch ---
        selected_empties = [
            o for o in context.selected_objects if o.type == "EMPTY" and o != obj
        ]
        if selected_empties:
            layout.separator()
            layout.operator(
                "metamagic.collision_batch_enable",
                icon="DUPLICATE",
                text=f"Apply to {len(selected_empties)} Selected Empty(s)",
            )

        # --- Status ---
        status = layout.box()
        if COLLISION_CONFIG_KEY in obj:
            status.label(text="✓ Metadata saved on object", icon="CHECKMARK")
        else:
            status.label(text="No metadata written yet", icon="ERROR")


# ---------------------------------------------------------------------------
#   Load-post handler: re-sync custom properties on file open
# ---------------------------------------------------------------------------

from bpy.app.handlers import persistent  # noqa: E402


@persistent
def _on_load_post(_filepath):
    """Re-sync collision custom properties after a .blend file is loaded.

    This ensures the JSON custom property matches the property-group state
    for every tagged Empty, in case the user saved while the property was
    out of date.
    """
    for obj in bpy.data.objects:
        if obj.type != "EMPTY":
            continue
        config = getattr(obj, "collision_config", None)
        if config is None:
            continue
        if config.enabled:
            _sync_custom_property(obj)


# ---------------------------------------------------------------------------
#   Registration
# ---------------------------------------------------------------------------


def register():
    bpy.types.Object.collision_config = bpy.props.PointerProperty(
        type=CollisionProperty
    )

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    del bpy.types.Object.collision_config
