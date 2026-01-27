import json

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .constants import (
    BONE_ATTACHMENT_CONFIG_KEY,
    DEFAULT_DRAG,
    DEFAULT_GRAVITY,
    DEFAULT_RADIUS,
    DEFAULT_STIFFNESS,
    JIGGLE_CONFIG_KEY,
)


def update_chain_property(self, context):
    """
    Callback to update custom properties when chain data changes.

    This is triggered whenever start_bone or end_bone is modified.
    It ensures the armature's custom property 'jiggle_bones_config' is updated
    with the current configuration as JSON.
    """
    # Try to get the object from context first
    obj = context.active_object

    # If that doesn't work, try to get it from the property group path
    if not obj:
        try:
            # Navigate up through property groups to find the object
            prop_path = self.path_from_id()
            if prop_path:
                obj = context.path_resolve(prop_path, False)
                # If we got a property group, get its id_data
                if hasattr(obj, "id_data"):
                    obj = obj.id_data
        except (AttributeError, ValueError):
            pass

    # If we have a valid armature object, update its custom properties
    if obj and obj.type == "ARMATURE" and hasattr(obj, "jiggle_config"):
        try:
            json_string = obj.jiggle_config.to_json()
            obj[JIGGLE_CONFIG_KEY] = json_string
        except Exception as e:
            print(f"[Metamagic] Error updating chain property: {e}")


def update_bone_attachment_property(self, context):
    """Callback to update custom property when bone attachment data changes."""
    # Using id_data to get the object this property group is attached to
    obj = self.id_data
    if obj and hasattr(obj, "bone_attachment_config"):
        try:
            data = {
                "armature": self.armature.name if self.armature else "",
                "bone": self.bone,
            }
            # Only save if we have at least an armature or bone
            if data["armature"] or data["bone"]:
                obj[BONE_ATTACHMENT_CONFIG_KEY] = json.dumps(data)
            elif BONE_ATTACHMENT_CONFIG_KEY in obj:
                del obj[BONE_ATTACHMENT_CONFIG_KEY]
        except Exception as e:
            print(f"[Metamagic] Error updating bone attachment property: {e}")


class JiggleChainProperty(PropertyGroup):
    """Configuration for a single jiggle bone chain"""

    bl_idname = "jiggle_chain"

    start_bone: StringProperty(
        name="Start Bone",
        description="First bone in the jiggle chain",
        default="",
        update=update_chain_property,
    )

    end_bone: StringProperty(
        name="End Bone",
        description="Last bone in the jiggle chain",
        default="",
        update=update_chain_property,
    )

    stiffness: FloatProperty(
        name="Stiffness",
        description="How resistant the bones are to moving",
        default=DEFAULT_STIFFNESS,
        soft_min=0.0,
        soft_max=10.0,
        update=update_chain_property,
    )

    drag: FloatProperty(
        name="Drag",
        description="Air resistance that slows down the jiggle",
        default=DEFAULT_DRAG,
        soft_min=0.0,
        soft_max=10.0,
        update=update_chain_property,
    )

    gravity: FloatProperty(
        name="Gravity",
        description="Magnitude of gravity affecting the chain",
        default=DEFAULT_GRAVITY,
        soft_min=0.0,
        soft_max=100.0,
        update=update_chain_property,
    )

    radius: FloatProperty(
        name="Radius",
        description="Collision radius for the jiggle bones",
        default=DEFAULT_RADIUS,
        soft_min=0.0,
        soft_max=10.0,
        update=update_chain_property,
    )

    extend_end_bone: BoolProperty(
        name="Extend End Bone",
        description="Whether to extend the end bone for the chain",
        default=False,
        update=update_chain_property,
    )

    def to_dict(self):
        """Convert this chain to a dictionary for JSON serialization"""
        return {
            "start_bone": self.start_bone,
            "end_bone": self.end_bone,
            "stiffness": self.stiffness,
            "drag": self.drag,
            "gravity": self.gravity,
            "radius": self.radius,
            "extend_end_bone": self.extend_end_bone,
        }


class JiggleConfigProperty(PropertyGroup):
    """Collection of jiggle bone chains for an armature"""

    bl_idname = "jiggle_config"

    chains: CollectionProperty(
        type=JiggleChainProperty,
        name="Jiggle Chains",
        description="List of jiggle bone chains",
    )

    active_chain_index: bpy.props.IntProperty(name="Active Chain Index", default=0)

    def to_json(self):
        """Convert all chains to JSON string"""
        chains_list = [chain.to_dict() for chain in self.chains]
        return json.dumps(chains_list, indent=2)

    def from_json(self, json_string):
        """Load chains from JSON string

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            chains_data = json.loads(json_string)

            # Validate structure before clearing existing chains
            if not isinstance(chains_data, list):
                return False

            # Validate each chain entry
            for chain_data in chains_data:
                if not isinstance(chain_data, dict):
                    return False

            # Only clear chains if validation passes
            self.chains.clear()
            for chain_data in chains_data:
                chain = self.chains.add()
                chain.start_bone = chain_data.get("start_bone", "")
                chain.end_bone = chain_data.get("end_bone", "")
                chain.stiffness = chain_data.get("stiffness", DEFAULT_STIFFNESS)
                chain.drag = chain_data.get("drag", DEFAULT_DRAG)
                chain.gravity = chain_data.get("gravity", DEFAULT_GRAVITY)
                chain.radius = chain_data.get("radius", DEFAULT_RADIUS)
                chain.extend_end_bone = chain_data.get("extend_end_bone", False)
            return True
        except (json.JSONDecodeError, TypeError, AttributeError):
            return False


class BoneAttachmentProperty(PropertyGroup):
    """Configuration for attaching an object to a bone in Godot"""

    bl_idname = "bone_attachment_config"

    armature: PointerProperty(
        name="Armature",
        description="Armature containing the bone",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == "ARMATURE",
        update=update_bone_attachment_property,
    )

    bone: StringProperty(
        name="Bone",
        description="Bone to attach to",
        default="",
        update=update_bone_attachment_property,
    )
