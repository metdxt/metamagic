import json
from typing import Any, Dict, List, Optional

import bpy

from .properties import JiggleChainProperty, JiggleConfigProperty


def get_jiggle_config(obj: bpy.types.Object) -> Optional[JiggleConfigProperty]:
    """
    Get the jiggle configuration from an armature object.

    Args:
        obj: Blender object (should be an armature)

    Returns:
        JiggleConfigProperty if found, None otherwise
    """
    if obj and obj.type == "ARMATURE" and hasattr(obj, "jiggle_config"):
        return obj.jiggle_config
    return None


def save_jiggle_config_to_custom_properties(obj: bpy.types.Object) -> bool:
    """
    Save the current jiggle configuration to armature's custom properties as JSON.

    Args:
        obj: Blender object (should be an armature)

    Returns:
        True if successful, False otherwise
    """
    if not obj or obj.type != "ARMATURE":
        return False

    config = get_jiggle_config(obj)
    if not config:
        return False

    try:
        json_string = config.to_json()
        obj["jiggle_bones_config"] = json_string
        return True
    except Exception:
        return False


def load_jiggle_config_from_custom_properties(obj: bpy.types.Object) -> bool:
    """
    Load jiggle configuration from armature's custom properties.

    Args:
        obj: Blender object (should be an armature)

    Returns:
        True if successful, False otherwise
    """
    if not obj or obj.type != "ARMATURE":
        return False

    config = get_jiggle_config(obj)
    if not config:
        return False

    if "jiggle_bones_config" in obj:
        try:
            config.from_json(obj["jiggle_bones_config"])
            return True
        except json.JSONDecodeError:
            return False

    return False


def get_bones_in_chain(
    obj: bpy.types.Object, start_bone: str, end_bone: str
) -> List[str]:
    """
    Get the list of bones in a chain from start to end bone.

    Args:
        obj: Blender object (should be an armature)
        start_bone: Name of the starting bone
        end_bone: Name of the ending bone

    Returns:
        List of bone names in the chain, empty list if chain is invalid
    """
    if not obj or obj.type != "ARMATURE":
        return []

    armature = obj.data
    if not armature:
        return []

    # Check if both bones exist
    if start_bone not in armature.bones or end_bone not in armature.bones:
        return []

    # Get bone objects
    start_bone_obj = armature.bones[start_bone]
    end_bone_obj = armature.bones[end_bone]

    # If bones are the same, return single bone
    if start_bone == end_bone:
        return [start_bone]

    # Walk from end bone up to start bone
    chain = []
    current_bone = end_bone_obj

    while current_bone:
        chain.append(current_bone.name)

        if current_bone.name == start_bone:
            # Found start bone, reverse chain and return
            return list(reversed(chain))

        # Move to parent
        current_bone = current_bone.parent

    # If we get here, start_bone is not a parent of end_bone
    return []


def validate_jiggle_chain(
    obj: bpy.types.Object, start_bone: str, end_bone: str
) -> tuple[bool, str]:
    """
    Validate if a jiggle chain is valid for the given armature.

    Args:
        obj: Blender object (should be an armature)
        start_bone: Name of the starting bone
        end_bone: Name of the ending bone

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not obj or obj.type != "ARMATURE":
        return False, "Object is not an armature"

    if not start_bone:
        return False, "Start bone name is empty"

    if not end_bone:
        return False, "End bone name is empty"

    if start_bone not in obj.data.bones:
        return False, f"Start bone '{start_bone}' not found in armature"

    if end_bone not in obj.data.bones:
        return False, f"End bone '{end_bone}' not found in armature"

    chain = get_bones_in_chain(obj, start_bone, end_bone)
    if not chain:
        return False, f"Cannot find chain from '{start_bone}' to '{end_bone}'"

    return True, ""


def export_jiggle_config_to_dict(obj: bpy.types.Object) -> Dict[str, Any]:
    """
    Export jiggle configuration to a dictionary.

    Args:
        obj: Blender object (should be an armature)

    Returns:
        Dictionary containing the jiggle configuration
    """
    config = get_jiggle_config(obj)
    if not config:
        return {"chains": []}

    return {"chains": [chain.to_dict() for chain in config.chains]}


def import_jiggle_config_from_dict(
    obj: bpy.types.Object, config_dict: Dict[str, Any]
) -> bool:
    """
    Import jiggle configuration from a dictionary.

    Args:
        obj: Blender object (should be an armature)
        config_dict: Dictionary containing the jiggle configuration

    Returns:
        True if successful, False otherwise
    """
    config = get_jiggle_config(obj)
    if not config:
        return False

    try:
        chains_data = config_dict.get("chains", [])
        config.chains.clear()
        for chain_data in chains_data:
            chain = config.chains.add()
            chain.start_bone = chain_data.get("start_bone", "")
            chain.end_bone = chain_data.get("end_bone", "")
            chain.stiffness = chain_data.get("stiffness", 1.0)
            chain.drag = chain_data.get("drag", 0.4)
            chain.gravity = chain_data.get("gravity", 0.0)
            chain.radius = chain_data.get("radius", 0.02)
            chain.extend_end_bone = chain_data.get("extend_end_bone", False)

        save_jiggle_config_to_custom_properties(obj)
        return True
    except Exception:
        return False
