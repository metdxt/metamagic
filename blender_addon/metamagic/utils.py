import json
from typing import Any, Dict, List, Optional

import bpy

from .constants import (
    DEFAULT_DRAG,
    DEFAULT_GRAVITY,
    DEFAULT_RADIUS,
    DEFAULT_STIFFNESS,
    ERROR_END_BONE_EMPTY,
    ERROR_END_BONE_NOT_FOUND,
    ERROR_INVALID_CHAIN,
    ERROR_NOT_ARMATURE,
    ERROR_START_BONE_EMPTY,
    ERROR_START_BONE_NOT_FOUND,
    JIGGLE_CONFIG_KEY,
)
from .properties import JiggleConfigProperty


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
        obj[JIGGLE_CONFIG_KEY] = json_string
        return True
    except Exception as e:
        print(f"[Metamagic] Error saving jiggle config to custom properties: {e}")
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

    if JIGGLE_CONFIG_KEY in obj:
        try:
            config.from_json(obj[JIGGLE_CONFIG_KEY])
            return True
        except json.JSONDecodeError as e:
            print(f"[Metamagic] JSON decode error loading jiggle config: {e}")
            return False
        except Exception as e:
            print(
                f"[Metamagic] Error loading jiggle config from custom properties: {e}"
            )
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
    end_bone_obj = armature.bones[end_bone]

    # If bones are the same, return single bone
    if start_bone == end_bone:
        return [start_bone]

    # Walk from end bone up to start bone
    chain = []
    visited = set()  # Track visited bones to detect cycles
    current_bone = end_bone_obj

    while current_bone:
        # Check for circular reference
        if current_bone.name in visited:
            # Circular reference detected, return empty list
            return []
        visited.add(current_bone.name)

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
        return False, ERROR_NOT_ARMATURE

    if not start_bone:
        return False, ERROR_START_BONE_EMPTY

    if not end_bone:
        return False, ERROR_END_BONE_EMPTY

    if start_bone not in obj.data.bones:
        return False, ERROR_START_BONE_NOT_FOUND.format(bone=start_bone)

    if end_bone not in obj.data.bones:
        return False, ERROR_END_BONE_NOT_FOUND.format(bone=end_bone)

    chain = get_bones_in_chain(obj, start_bone, end_bone)
    if not chain:
        return False, ERROR_INVALID_CHAIN.format(start=start_bone, end=end_bone)

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
    # Validate input structure
    if not isinstance(config_dict, dict):
        print("[Metamagic] Error: config_dict must be a dictionary")
        return False

    config = get_jiggle_config(obj)
    if not config:
        print("[Metamagic] Error: No jiggle config found on object")
        return False

    try:
        # Validate and extract chains data
        if "chains" not in config_dict:
            print("[Metamagic] Error: config_dict missing 'chains' key")
            return False

        chains_data = config_dict["chains"]
        if not isinstance(chains_data, list):
            print("[Metamagic] Error: 'chains' must be a list")
            return False

        # Validate each chain entry before clearing existing chains
        for i, chain_data in enumerate(chains_data):
            if not isinstance(chain_data, dict):
                print(f"[Metamagic] Error: Chain at index {i} is not a dictionary")
                return False

        # Only clear chains after validation passes
        config.chains.clear()

        for i, chain_data in enumerate(chains_data):
            chain = config.chains.add()
            chain.start_bone = chain_data.get("start_bone", "")
            chain.end_bone = chain_data.get("end_bone", "")
            chain.stiffness = chain_data.get("stiffness", DEFAULT_STIFFNESS)
            chain.drag = chain_data.get("drag", DEFAULT_DRAG)
            chain.gravity = chain_data.get("gravity", DEFAULT_GRAVITY)
            chain.radius = chain_data.get("radius", DEFAULT_RADIUS)
            chain.extend_end_bone = chain_data.get("extend_end_bone", False)

        if not save_jiggle_config_to_custom_properties(obj):
            print("[Metamagic] Warning: Failed to save config to custom properties")
            return False

        return True
    except Exception as e:
        print(f"[Metamagic] Error importing jiggle config from dict: {e}")
        return False
