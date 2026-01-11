@tool
extends EditorPlugin

var jiggle_plugin := preload("res://addons/metamagic/jiggle_post_process.gd").new()

func _enable_plugin() -> void:
	# Add autoloads here.
	pass


func _disable_plugin() -> void:
	# Remove autoloads here.
	pass


func _enter_tree() -> void:
	# Initialization of the plugin goes here.
	add_scene_post_import_plugin(jiggle_plugin, false)


func _exit_tree() -> void:
	# Clean-up of the plugin goes here.
	remove_scene_post_import_plugin(jiggle_plugin)
