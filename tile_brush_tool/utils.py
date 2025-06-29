import mathutils

class UtilsMixin:
    """Utility methods for grid snapping and view helpers."""

    def get_green_face_world_position(self):
        half_size = self.current_tile_size / 2.0
        local_face_offset = mathutils.Vector((0, 0, -half_size))
        rotation_matrix = self.preview.rotation_euler.to_matrix()
        rotated_offset = rotation_matrix @ local_face_offset
        return self.preview.location + rotated_offset

    def snap_to_grid(self, location):
        if self.movement_speed == 1.0:
            if self.current_tile_size == 0.5:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         round(location.z * 4) / 4))
            elif self.current_tile_size == 1.0:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         round(location.z * 4) / 4))
            elif self.current_tile_size == 2.0:
                return mathutils.Vector((round(location.x * 2) / 2,
                                         round(location.y * 2) / 2,
                                         round(location.z * 2) / 2))
            else:
                return mathutils.Vector((round(location.x),
                                         round(location.y),
                                         round(location.z)))
        else:
            if self.current_tile_size == 0.5:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         round(location.z * 4) / 4))
            elif self.current_tile_size == 1.0:
                return mathutils.Vector((round(location.x - 0.5) + 0.5,
                                         round(location.y - 0.5) + 0.5,
                                         round(location.z - 0.5) + 0.5))
            elif self.current_tile_size == 2.0:
                return mathutils.Vector((round(location.x),
                                         round(location.y),
                                         round(location.z)))
            else:
                return mathutils.Vector((round(location.x / 2) * 2,
                                         round(location.y / 2) * 2,
                                         round(location.z / 2) * 2))

    def snap_to_grid_horizontal_only(self, location):
        if self.movement_speed == 1.0:
            if self.current_tile_size == 0.5:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         location.z))
            elif self.current_tile_size == 1.0:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         location.z))
            elif self.current_tile_size == 2.0:
                return mathutils.Vector((round(location.x * 2) / 2,
                                         round(location.y * 2) / 2,
                                         location.z))
            else:
                return mathutils.Vector((round(location.x),
                                         round(location.y),
                                         location.z))
        else:
            if self.current_tile_size == 0.5:
                return mathutils.Vector((round(location.x * 4) / 4,
                                         round(location.y * 4) / 4,
                                         location.z))
            elif self.current_tile_size == 1.0:
                return mathutils.Vector((round(location.x - 0.5) + 0.5,
                                         round(location.y - 0.5) + 0.5,
                                         location.z))
            elif self.current_tile_size == 2.0:
                return mathutils.Vector((round(location.x),
                                         round(location.y),
                                         location.z))
            else:
                return mathutils.Vector((round(location.x / 2) * 2,
                                         round(location.y / 2) * 2,
                                         location.z))

    def get_view_relative_vectors(self, context):
        try:
            region_3d = context.region_data
            if not region_3d:
                return mathutils.Vector((0, 1, 0)), mathutils.Vector((1, 0, 0))
            view_matrix = region_3d.view_matrix
            view_rotation = view_matrix.to_3x3().transposed()
            forward_world = view_rotation @ mathutils.Vector((0, 0, -1))
            right_world = view_rotation @ mathutils.Vector((1, 0, 0))
            forward_horizontal = mathutils.Vector((forward_world.x, forward_world.y, 0))
            right_horizontal = mathutils.Vector((right_world.x, right_world.y, 0))
            if abs(forward_horizontal.x) > abs(forward_horizontal.y):
                forward_single_axis = mathutils.Vector((1.0 if forward_horizontal.x > 0 else -1.0, 0.0, 0.0))
            else:
                forward_single_axis = mathutils.Vector((0.0, 1.0 if forward_horizontal.y > 0 else -1.0, 0.0))
            if abs(right_horizontal.x) > abs(right_horizontal.y):
                right_single_axis = mathutils.Vector((1.0 if right_horizontal.x > 0 else -1.0, 0.0, 0.0))
            else:
                right_single_axis = mathutils.Vector((0.0, 1.0 if right_horizontal.y > 0 else -1.0, 0.0))
            return forward_single_axis, right_single_axis
        except Exception:
            return mathutils.Vector((0, 1, 0)), mathutils.Vector((1, 0, 0))

