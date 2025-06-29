import bpy
import math
import mathutils
import os

OBJECTS_BLEND_FILE = "TileBrushObjects.blend"
OBJECTS_COLLECTION = "BrushHelperObjects"
PLANE_NAMES = ["Plane0.5x0.5", "Plane1x1", "Plane2x2", "Plane4x4"]
CUBE_NAMES = ["Cube0.5x0.5", "Cube1x1", "Cube2x2", "Cube4x4"]
CUBE_NAMES_INVERTED = ["Cube0.5x0.5_I", "Cube1x1_I", "Cube2x2_I", "Cube4x4_I"]
TILE_SIZES = [0.5, 1.0, 2.0, 4.0]

PLANE_PATTERNS = [
    ["Plane0.5x0.5", "Plane1x1", "Plane2x2", "Plane4x4"],
    ["Plane_0.5x0.5", "Plane_1x1", "Plane_2x2", "Plane_4x4"],
    ["Plane.0.5x0.5", "Plane.1x1", "Plane.2x2", "Plane.4x4"],
    ["plane0.5x0.5", "plane1x1", "plane2x2", "plane4x4"],
]

CUBE_PATTERNS = [
    ["Cube0.5x0.5", "Cube1x1", "Cube2x2", "Cube4x4"],
    ["Cube_0.5x0.5", "Cube_1x1", "Cube_2x2", "Cube_4x4"],
    ["Cube.0.5x0.5", "Cube.1x1", "Cube.2x2", "Cube.4x4"],
    ["cube0.5x0.5", "cube1x1", "cube2x2", "cube4x4"],
]

CUBE_PATTERNS_INVERTED = [
    ["Cube0.5x0.5_I", "Cube1x1_I", "Cube2x2_I", "Cube4x4_I"],
    ["Cube_0.5x0.5_I", "Cube_1x1_I", "Cube_2x2_I", "Cube_4x4_I"],
    ["Cube.0.5x0.5_I", "Cube.1x1_I", "Cube.2x2_I", "Cube.4x4_I"],
    ["cube0.5x0.5_i", "cube1x1_i", "cube2x2_i", "cube4x4_i"],
]

CUBE_FACES = [
    ((0, 0, 0), "Bottom"),
    ((math.radians(180), 0, 0), "Top"),
    ((math.radians(90), 0, 0), "Front"),
    ((math.radians(-90), 0, 0), "Back"),
    ((0, math.radians(-90), 0), "Right"),
    ((0, math.radians(90), 0), "Left"),
]

class ObjectLoaderMixin:
    """Functions for loading helper objects from the bundled blend file."""

    def load_tile_objects(self):
        addon_dir = os.path.dirname(os.path.realpath(__file__))
        blend_path = os.path.join(addon_dir, OBJECTS_BLEND_FILE)
        print(f"[TileBrush] Looking for blend file at: {blend_path}")
        if not os.path.exists(blend_path):
            error_msg = f"'{OBJECTS_BLEND_FILE}' not found in addon directory: {addon_dir}"
            self.report({'ERROR'}, error_msg)
            print(f"[TileBrush] ERROR: {error_msg}")
            return False
        try:
            all_objects_exist = True
            all_names = PLANE_NAMES + CUBE_NAMES
            for obj_name in all_names:
                if not bpy.data.objects.get(obj_name):
                    all_objects_exist = False
                    break
            if not all_objects_exist:
                print(f"[TileBrush] Loading collection '{OBJECTS_COLLECTION}' from {blend_path}")
                bpy.ops.wm.append(
                    filepath=os.path.join(blend_path, "Collection", OBJECTS_COLLECTION),
                    directory=os.path.join(blend_path, "Collection"),
                    filename=OBJECTS_COLLECTION,
                )
            self.plane_templates = []
            self.cube_templates = []
            self.cube_templates_inverted = []
            missing_objects = []
            plane_names_found = None
            for pattern in PLANE_PATTERNS:
                if all(bpy.data.objects.get(name) for name in pattern):
                    plane_names_found = pattern
                    break
            if plane_names_found:
                for plane_name in plane_names_found:
                    obj = bpy.data.objects.get(plane_name)
                    obj.hide_viewport = True
                    obj.hide_render = True
                    self.plane_templates.append(obj)
                print(f"[TileBrush] Found planes: {plane_names_found}")
            else:
                missing_objects.extend(PLANE_NAMES)
            cube_names_found = None
            for pattern in CUBE_PATTERNS:
                if all(bpy.data.objects.get(name) for name in pattern):
                    cube_names_found = pattern
                    break
            if cube_names_found:
                for cube_name in cube_names_found:
                    obj = bpy.data.objects.get(cube_name)
                    obj.hide_viewport = True
                    obj.hide_render = True
                    self.cube_templates.append(obj)
                print(f"[TileBrush] Found cubes: {cube_names_found}")
            else:
                missing_objects.extend(CUBE_NAMES)
            cube_names_inverted_found = None
            for pattern in CUBE_PATTERNS_INVERTED:
                if all(bpy.data.objects.get(name) for name in pattern):
                    cube_names_inverted_found = pattern
                    break
            if cube_names_inverted_found:
                for cube_name in cube_names_inverted_found:
                    obj = bpy.data.objects.get(cube_name)
                    obj.hide_viewport = True
                    obj.hide_render = True
                    self.cube_templates_inverted.append(obj)
                print(f"[TileBrush] Found inverted cubes: {cube_names_inverted_found}")
            else:
                print(f"[TileBrush] No inverted cubes found - inverted mode will be disabled")
            if missing_objects:
                missing_str = ", ".join(missing_objects)
                available_objs = [name for name in bpy.data.objects.keys() if any(expected in name.lower() for expected in ['plane', 'cube'])]
                available_str = ", ".join(available_objs) if available_objs else "None found"
                error_msg = f"""Missing required objects: {missing_str}
Available objects: {available_str}
The collection '{OBJECTS_COLLECTION}' in {OBJECTS_BLEND_FILE} should contain:
- 4 plane objects (0.5x0.5, 1x1, 2x2, and 4x4 sizes)
- 4 cube objects (0.5x0.5, 1x1, 2x2, and 4x4 sizes)
Supported naming patterns:
- Plane0.5x0.5, Plane1x1, Plane2x2, Plane4x4, Cube0.5x0.5, Cube1x1, Cube2x2, Cube4x4
- Plane_0.5x0.5, Plane_1x1, Plane_2x2, Plane_4x4, Cube_0.5x0.5, Cube_1x1, Cube_2x2, Cube_4x4
- Plane.0.5x0.5, Plane.1x1, Plane.2x2, Plane.4x4, Cube.0.5x0.5, Cube.1x1, Cube.2x2, Cube.4x4
- plane0.5x0.5, plane1x1, plane2x2, plane4x4, cube0.5x0.5, cube1x1, cube2x2, cube4x4"""
                self.report({'ERROR'}, error_msg)
                print(f"[TileBrush] ERROR: {error_msg}")
                return False
            print(
                f"[TileBrush] Loaded {len(self.plane_templates)} planes, {len(self.cube_templates)} cubes, and {len(self.cube_templates_inverted)} inverted cubes from collection '{OBJECTS_COLLECTION}' (sizes: {', '.join([f'{size}x{size}' for size in TILE_SIZES])})"
            )
            return True
        except Exception as e:
            self.report({'ERROR'}, f"Error loading collection: {str(e)}")
            return False

    def get_current_cube_template(self):
        if self.inverted_mode and hasattr(self, 'cube_templates_inverted') and len(self.cube_templates_inverted) > self.tile_size_index:
            return self.cube_templates_inverted[self.tile_size_index]
        else:
            return self.cube_templates[self.tile_size_index]
