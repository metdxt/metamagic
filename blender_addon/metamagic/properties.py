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
            obj["jiggle_bones_config"] = json_string
        except Exception as e:
            pass


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
        default=1.0,
        soft_min=0.0,
        soft_max=10.0,
        update=update_chain_property,
    )

    drag: FloatProperty(
        name="Drag",
        description="Air resistance that slows down the jiggle",
        default=0.4,
        soft_min=0.0,
        soft_max=10.0,
        update=update_chain_property,
    )

    gravity: FloatProperty(
        name="Gravity",
        description="Magnitude of gravity affecting the chain",
        default=0.0,
        soft_min=0.0,
        soft_max=100.0,
        update=update_chain_property,
    )

    radius: FloatProperty(
        name="Radius",
        description="Collision radius for the jiggle bones",
        default=0.02,
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
        """Load chains from JSON string"""
        try:
            chains_data = json.loads(json_string)
            self.chains.clear()
            for chain_data in chains_data:
                chain = self.chains.add()
                chain.start_bone = chain_data.get("start_bone", "")
                chain.end_bone = chain_data.get("end_bone", "")
                chain.stiffness = chain_data.get("stiffness", 1.0)
                chain.drag = chain_data.get("drag", 0.4)
                chain.gravity = chain_data.get("gravity", 0.0)
                chain.radius = chain_data.get("radius", 0.02)
                chain.extend_end_bone = chain_data.get("extend_end_bone", False)
        except json.JSONDecodeError:
            pass
