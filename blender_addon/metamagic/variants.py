"""Object Variants data model for the Metamagic Blender addon.

Allows grouping multiple objects (typically empties parenting meshes)
as variants of each other.  On every edit the variant metadata is
written as a JSON custom‑property on each member object so that it
survives the glTF round‑trip and can be read by Godot's post‑import
plugin to set up runtime variant switching.

Scene‑level ``VariantConfigProperty`` keeps the authoritative list of
groups and is used by the UI panel.  Per‑object custom properties
(``metamagic_variant``) are derived/synced automatically.

Visibility
----------
We deliberately use ``obj.hide_set()`` (the temporary "H‑key" hide)
instead of ``obj.hide_viewport`` / ``obj.hide_render``.  The latter two
modify the depsgraph evaluation flags, which causes Blender to skip
computing transforms and modifiers for hidden objects.  glTF then
exports them with stale / zeroed‑out data.

``hide_set()`` is purely visual – the depsgraph still fully evaluates
every object, so transforms, modifiers, and constraints are always
correct, and glTF exports everything properly.  Godot's post‑import
plugin handles hiding non‑default variants on that side.

Because ``hide_set()`` state does not persist across file save/load, we
install a ``load_post`` app handler that re‑applies the preview
visibility whenever a .blend file is opened.
"""

import json
from typing import Optional, Set, Tuple

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    CollectionProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

__all__ = [
    "VARIANT_CONFIG_KEY",
    "VariantMemberProperty",
    "VariantGroupProperty",
    "VariantConfigProperty",
    "sync_variant_custom_properties",
    "update_viewport_visibility",
    "find_group_for_object",
    "register",
    "unregister",
]

# Key used to persist per‑object metadata so it appears in glTF extras.
VARIANT_CONFIG_KEY = "metamagic_variant"


# ---------------------------------------------------------------------------
#   Helpers
# ---------------------------------------------------------------------------


def _set_subtree_visibility(obj: bpy.types.Object, hidden: bool) -> None:
    """Temporarily hide or show *obj* and all its descendants using
    ``hide_set()``.

    Unlike ``hide_viewport`` / ``hide_render`` this does **not** affect
    the dependency graph – transforms, modifiers and constraints are
    still evaluated normally, which means glTF export always gets
    correct data.
    """
    try:
        obj.hide_set(hidden)
    except RuntimeError:
        # hide_set() can fail if the object is not in the current view
        # layer.  Silently skip – the object simply won't be toggled.
        pass

    for child in obj.children:
        _set_subtree_visibility(child, hidden)


def _unhide_subtree(obj: bpy.types.Object) -> None:
    """Convenience wrapper – make *obj* and all descendants visible."""
    _set_subtree_visibility(obj, hidden=False)


def _collect_tracked_names(config) -> Set[str]:
    """Return a set of object names currently referenced by any variant group."""
    names: Set[str] = set()
    for group in config.groups:
        for member in group.members:
            if member.obj:
                names.add(member.obj.name)
    return names


def sync_variant_custom_properties(scene: bpy.types.Scene) -> None:
    """Write per‑object ``metamagic_variant`` custom properties that mirror
    the scene‑level *variant_config*.  Any object that is no longer part of
    a group has its custom property removed."""

    if not hasattr(scene, "variant_config"):
        return

    config = scene.variant_config
    tracked: Set[str] = set()

    for group in config.groups:
        # Determine which member is the default.
        default_name = ""
        if 0 <= group.default_index < len(group.members):
            default_member = group.members[group.default_index]
            if default_member.obj:
                default_name = default_member.obj.name

        # Build an ordered list of all member names for this group so that
        # Godot can reconstruct the full list from any single node.
        variant_names = []
        for m in group.members:
            if m.obj:
                variant_names.append(m.obj.name)

        for member in group.members:
            if not member.obj:
                continue

            tracked.add(member.obj.name)

            data = {
                "group": group.name,
                "is_default": member.obj.name == default_name,
                "variants": variant_names,
                "default": default_name,
            }
            member.obj[VARIANT_CONFIG_KEY] = json.dumps(data)

    # Remove stale custom properties from objects that left all groups.
    for obj in scene.objects:
        if obj.name not in tracked and VARIANT_CONFIG_KEY in obj:
            del obj[VARIANT_CONFIG_KEY]


def update_viewport_visibility(scene: bpy.types.Scene) -> None:
    """For every variant group, show only the *default* variant and hide
    all other members (including their children) in the viewport.

    Uses ``hide_set()`` so the depsgraph is **not** affected – transforms
    and modifiers remain fully evaluated for every object.
    """

    if not hasattr(scene, "variant_config"):
        return

    config = scene.variant_config

    for group in config.groups:
        default_idx = group.default_index
        for i, member in enumerate(group.members):
            if member.obj:
                _set_subtree_visibility(member.obj, hidden=(i != default_idx))


def find_group_for_object(
    config, obj: bpy.types.Object
) -> Tuple[Optional["VariantGroupProperty"], Optional[int], Optional[int]]:
    """Return ``(group, group_index, member_index)`` if *obj* belongs to a
    variant group, or ``(None, None, None)`` otherwise."""

    if obj is None:
        return None, None, None

    for gi, group in enumerate(config.groups):
        for mi, member in enumerate(group.members):
            if member.obj == obj:
                return group, gi, mi

    return None, None, None


# ---------------------------------------------------------------------------
#   App handlers
# ---------------------------------------------------------------------------


@persistent
def _on_load_post(_filepath):
    """Re‑apply variant preview visibility after a .blend file is loaded.

    ``hide_set()`` state is transient and does not survive save/load, so
    we need to walk every scene's variant config and re‑hide the
    non‑default members.
    """
    for scene in bpy.data.scenes:
        try:
            update_viewport_visibility(scene)
        except Exception as e:
            print(
                f"[Metamagic] Error restoring variant visibility for "
                f"scene '{scene.name}': {e}"
            )


# ---------------------------------------------------------------------------
#   Update callbacks
# ---------------------------------------------------------------------------


def _on_variant_data_changed(self, context):
    """Generic callback – keeps custom properties and viewport in sync."""
    if context and context.scene:
        sync_variant_custom_properties(context.scene)
        update_viewport_visibility(context.scene)


def _on_default_index_changed(self, context):
    """Fires when the user changes which variant is the default."""
    # Clamp to valid range.
    if len(self.members) > 0:
        self["default_index"] = max(0, min(self.default_index, len(self.members) - 1))
    else:
        self["default_index"] = 0

    _on_variant_data_changed(self, context)


# ---------------------------------------------------------------------------
#   Property groups
# ---------------------------------------------------------------------------


class VariantMemberProperty(PropertyGroup):
    """A single object that participates in a variant group.

    Typically this is an **Empty** that parents one or more mesh children,
    mirroring the Blender outliner hierarchy shown in the design reference.
    """

    bl_idname = "metamagic_variant_member"

    obj: PointerProperty(
        name="Object",
        description="Object that is a member of this variant group",
        type=bpy.types.Object,
        update=_on_variant_data_changed,
    )


class VariantGroupProperty(PropertyGroup):
    """A named set of objects that are visual variants of each other.

    Only one variant per group is visible at a time; in Godot the user can
    pick which one via an inspector dropdown generated by the tool script.
    """

    bl_idname = "metamagic_variant_group"

    name: StringProperty(
        name="Group Name",
        description="Human‑readable name for this variant group (also used as the Godot property name)",
        default="VariantGroup",
        update=_on_variant_data_changed,
    )

    members: CollectionProperty(
        type=VariantMemberProperty,
        name="Members",
        description="Objects that are visual variants of each other",
    )

    active_member_index: IntProperty(
        name="Active Member",
        description="UI list selection index",
        default=0,
    )

    default_index: IntProperty(
        name="Default Variant",
        description="Index of the variant that is shown by default in Godot and in the Blender viewport",
        default=0,
        update=_on_default_index_changed,
    )

    # -- helpers --

    def add_member(self, obj: bpy.types.Object) -> Optional[VariantMemberProperty]:
        """Add *obj* to this group if it isn't already a member.

        Returns the new ``VariantMemberProperty``, or ``None`` if the
        object was already present.
        """
        for m in self.members:
            if m.obj == obj:
                return None
        member = self.members.add()
        member.obj = obj
        return member

    def remove_member(self, index: int) -> bool:
        """Remove the member at *index*.  Returns ``True`` on success."""
        if index < 0 or index >= len(self.members):
            return False

        # Un‑hide the subtree before removing so it doesn't stay invisible.
        member = self.members[index]
        if member.obj:
            _unhide_subtree(member.obj)

        self.members.remove(index)

        # Keep default_index in range.
        if self.default_index >= len(self.members):
            self.default_index = max(0, len(self.members) - 1)
        if self.active_member_index >= len(self.members):
            self.active_member_index = max(0, len(self.members) - 1)

        return True

    def to_dict(self) -> dict:
        """Serialise this group to a plain dictionary."""
        default_name = ""
        if 0 <= self.default_index < len(self.members):
            m = self.members[self.default_index]
            if m.obj:
                default_name = m.obj.name

        return {
            "name": self.name,
            "variants": [m.obj.name for m in self.members if m.obj],
            "default": default_name,
        }


class VariantConfigProperty(PropertyGroup):
    """Scene‑level container for all variant groups."""

    bl_idname = "metamagic_variant_config"

    groups: CollectionProperty(
        type=VariantGroupProperty,
        name="Variant Groups",
        description="All variant groups defined in this scene",
    )

    active_group_index: IntProperty(
        name="Active Group",
        description="UI list selection index",
        default=0,
    )

    # -- helpers --

    def add_group(self, name: str = "VariantGroup") -> VariantGroupProperty:
        """Create and return a new empty variant group."""
        group = self.groups.add()
        group.name = name
        return group

    def remove_group(self, index: int) -> bool:
        """Remove the group at *index*.  Returns ``True`` on success."""
        if index < 0 or index >= len(self.groups):
            return False

        # Un‑hide every member before removing the group so objects don't
        # remain invisible after the group is deleted.
        group = self.groups[index]
        for member in group.members:
            if member.obj:
                _unhide_subtree(member.obj)

        self.groups.remove(index)
        if self.active_group_index >= len(self.groups):
            self.active_group_index = max(0, len(self.groups) - 1)
        return True

    def to_json(self) -> str:
        """Return a JSON string describing every group (useful for debugging)."""
        return json.dumps(
            [group.to_dict() for group in self.groups],
            indent=2,
        )

    def object_is_tracked(self, obj: bpy.types.Object) -> bool:
        """Return ``True`` if *obj* already belongs to any group."""
        for group in self.groups:
            for member in group.members:
                if member.obj == obj:
                    return True
        return False


# ---------------------------------------------------------------------------
#   Registration
# ---------------------------------------------------------------------------


def register():
    bpy.types.Scene.variant_config = PointerProperty(type=VariantConfigProperty)

    # Install the load_post handler so variant visibility is restored
    # whenever a .blend file is opened.
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    del bpy.types.Scene.variant_config
