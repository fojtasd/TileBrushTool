bl_info = {
    "name": "Tile Brush Tool",
    "author": "David Fójcik",
    "version": (2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Object > Tile Brush",
    "description": "Keyboard-driven tile placement tool with preview and rotation",
    "category": "Object",
}

import bpy
from .operator import VIEW3D_OT_tile_brush, menu_func

classes = [VIEW3D_OT_tile_brush]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

