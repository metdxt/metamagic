"""Constants used across the Metamagic Blender addon."""

__all__ = [
    "JIGGLE_CONFIG_KEY",
    "UI_SPLIT_START_BONE",
    "UI_SPLIT_ARROW",
    "UI_SPLIT_END_BONE",
    "DEFAULT_STIFFNESS",
    "DEFAULT_DRAG",
    "DEFAULT_GRAVITY",
    "DEFAULT_RADIUS",
    "BONE_SUFFIX_PATTERNS",
    "LEFT_SUFFIXES",
    "RIGHT_SUFFIXES",
    "ERROR_NOT_ARMATURE",
    "ERROR_NO_ARMATURE_SELECTED",
    "ERROR_START_BONE_EMPTY",
    "ERROR_END_BONE_EMPTY",
    "ERROR_START_BONE_NOT_FOUND",
    "ERROR_END_BONE_NOT_FOUND",
    "ERROR_INVALID_CHAIN",
    "ERROR_NO_CHAIN_SELECTED",
    "ERROR_NEED_EDIT_MODE",
    "ERROR_MIN_BONES_REQUIRED",
    "ERROR_HIERARCHY_INVALID",
    "ERROR_INVALID_POSE_BONE",
    "SUCCESS_ADDED_CHAIN",
    "SUCCESS_REMOVED_CHAIN",
    "SUCCESS_CHAIN_UPDATED",
    "SUCCESS_ROTATION_CHAIN_CREATED",
    "SUCCESS_CONFIG_UPDATED",
    "SUCCESS_CONFIG_SAVED",
    "SUCCESS_VALID_CHAIN",
    "WARNING_CONFIG_SAVE_FAILED",
    "WARNING_BRANCHES_DETECTED",
    "WARNING_BONES_NOT_IN_CHAIN",
    "WARNING_CONFIG_NOT_SAVED",
    "CONSTRAINT_TYPE",
    "CONSTRAINT_OWNER_SPACE",
    "CONSTRAINT_TARGET_SPACE",
    "CONSTRAINT_INFLUENCE",
    "MODE_EDIT_ARMATURE",
    "MODE_EDIT",
    "MODE_OBJECT",
]

# Custom property key for storing jiggle configuration in armatures
JIGGLE_CONFIG_KEY = "jiggle_bones_config"
# Custom property key for storing bone attachment configuration in objects
BONE_ATTACHMENT_CONFIG_KEY = "metamagic_bone_attachment"

# UI List split factors for chain display
# These define the proportional widths of different sections in the chain list
UI_SPLIT_START_BONE = 0.30  # 30% for start bone name
UI_SPLIT_ARROW = 0.1429  # ~14.3% for arrow icon (0.10 / (1 - 0.30))
UI_SPLIT_END_BONE = 0.9167  # ~91.7% for end bone name (0.55 / (1 - 0.30 - 0.10))

# Default physics parameters
DEFAULT_STIFFNESS = 1.0
DEFAULT_DRAG = 0.4
DEFAULT_GRAVITY = 0.0
DEFAULT_RADIUS = 0.02

# Bone name suffix patterns for mirrored bones
# Common naming conventions for left/right bones in Blender
BONE_SUFFIX_PATTERNS = [
    r"(.+?)\.(L|R)$",  # bone_name.L or bone_name.R
    r"(.+?)_([LR])$",  # bone_name_L or bone_name_R
    r"(.+?)_(left|right)$",  # bone_name_left or bone_name_right
]

# Side suffixes (case-insensitive)
LEFT_SUFFIXES = {"L", "LEFT"}
RIGHT_SUFFIXES = {"R", "RIGHT"}

# Error messages
ERROR_NOT_ARMATURE = "Object is not an armature"
ERROR_NO_ARMATURE_SELECTED = "No armature selected"
ERROR_START_BONE_EMPTY = "Start bone name is empty"
ERROR_END_BONE_EMPTY = "End bone name is empty"
ERROR_START_BONE_NOT_FOUND = "Start bone '{bone}' not found in armature"
ERROR_END_BONE_NOT_FOUND = "End bone '{bone}' not found in armature"
ERROR_INVALID_CHAIN = "Cannot find chain from '{start}' to '{end}'"
ERROR_NO_CHAIN_SELECTED = "No chain selected"
ERROR_NEED_EDIT_MODE = "Select bones in Edit Mode"
ERROR_MIN_BONES_REQUIRED = "Select at least {count} bones"
ERROR_HIERARCHY_INVALID = (
    "Could not determine bone hierarchy - check parent relationships"
)
ERROR_INVALID_POSE_BONE = "Could not find pose bone: {bone}"

# Success messages
SUCCESS_ADDED_CHAIN = "Added new jiggle chain"
SUCCESS_REMOVED_CHAIN = "Removed jiggle chain"
SUCCESS_CHAIN_UPDATED = "Updated chain from '{start}' to '{end}'"
SUCCESS_ROTATION_CHAIN_CREATED = "Created rotation chain with {count} bones"
SUCCESS_CONFIG_UPDATED = "Config updated: {count} chain(s)"
SUCCESS_CONFIG_SAVED = "✓ Config saved to armature"
SUCCESS_VALID_CHAIN = "✓ Valid chain ({count} bones)"

# Warning messages
WARNING_CONFIG_SAVE_FAILED = "Added chain, but failed to save config"
WARNING_BRANCHES_DETECTED = (
    "Multiple branches detected at '{bone}' - rotation chain may not work as expected"
)
WARNING_BONES_NOT_IN_CHAIN = "Selected bones not in chain: {bones}"
WARNING_CONFIG_NOT_SAVED = "No config saved yet"

# Constraint settings for Copy Rotation
CONSTRAINT_TYPE = "COPY_ROTATION"
CONSTRAINT_OWNER_SPACE = "LOCAL"
CONSTRAINT_TARGET_SPACE = "LOCAL"
CONSTRAINT_INFLUENCE = 1.0

# Blender mode constants
# context.mode returns "EDIT_ARMATURE" for edit mode with armature
MODE_EDIT_ARMATURE = "EDIT_ARMATURE"
# bpy.ops.object.mode_set() expects "EDIT" not "EDIT_ARMATURE"
MODE_EDIT = "EDIT"
MODE_OBJECT = "OBJECT"
