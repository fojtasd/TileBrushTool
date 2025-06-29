import bpy
import math
import mathutils
from bpy_extras import view3d_utils

from .objects import (
    ObjectLoaderMixin,
    PLANE_NAMES,
    CUBE_NAMES,
    CUBE_NAMES_INVERTED,
    TILE_SIZES,
    CUBE_FACES,
)
from .utils import UtilsMixin
from .ui import UIMixin


class VIEW3D_OT_tile_brush(ObjectLoaderMixin, UtilsMixin, UIMixin, bpy.types.Operator):
    """Keyboard and mouse controlled tile placement tool"""
    bl_idname = "view3d.tile_brush"
    bl_label = "Tile Brush"
    bl_options = {'REGISTER', 'UNDO'}
    def invoke(self, context, event):
        print("[TileBrush] Invoked")
        
        # Initialize all attributes that might be accessed during cleanup
        self.draw_handler = None
        self.original_shading_type = None
        self.preview = None
        self.master_object = None
        self.placed_tiles = set()
        self.undo_history = []
        self.undo_positions = []
        self.plane_templates = []
        self.cube_templates = []
        self.cube_templates_inverted = []
        self.rotation_icon_areas = {}
        
        # Initialize movement speed first (needed for grid snapping)
        self.movement_speed = 1.0  # Movement multiplier: 1.0 = normal, 2.0 = fast
        self.auto_mode = False  # Auto-mode: automatically place tiles when moving
        self.previous_speed = 1.0  # Store speed before auto-mode for restoration
        self.inverted_mode = False  # Inverted mode: use inverted cubes with opposite face orientation
        
        # Initialize rotation icon click areas
        self.rotation_icon_areas = {}
        
        # Load objects from external .blend file
        if not self.load_tile_objects():
            # Clean up any partially loaded objects
            self.cleanup_tool(context)
            return {'CANCELLED'}
        
        # Initialize tile size settings
        self.tile_size_index = 2  # Start with 2x2 units (index 2)
        self.current_tile_size = TILE_SIZES[self.tile_size_index]
    
        # Create preview by copying the appropriate cube based on size and inverted mode
        cube_template = self.get_current_cube_template()
        self.preview = cube_template.copy()
        self.preview.data = cube_template.data.copy()
        self.preview.name = "TileBrush_Preview"
        
        # Ensure preview is visible (template might be hidden)
        self.preview.hide_viewport = False
        self.preview.hide_render = True
        self.preview.hide_select = True
        self.preview.display_type = 'SOLID'
        self.preview.show_in_front = True
        
        # Start at 3D cursor location, but snap to grid
        cursor_loc = context.scene.cursor.location.copy()
        # Snap to grid based on current tile size
        snapped_loc = self.snap_to_grid(cursor_loc)
        self.preview.location = snapped_loc
        self.base_location = snapped_loc.copy()  # Store base position for cube face calculations
        
        print(f"[TileBrush] Snapped from {cursor_loc} to {snapped_loc} (tile size: {self.current_tile_size}x{self.current_tile_size})")
        self.rotation_state = 0
        self.last_placed_position = None  # Track last placement to prevent double-placement
        self.placed_tiles = set()  # Track all placed tile positions globally
        self.master_object = None  # Single connected object for all placed tiles
        self.undo_history = []  # Store mesh snapshots for undo (max 20)
        self.undo_positions = []  # Store placement tracking for each undo state
        self.draw_handler = None  # Visual indicator draw handler
        self.original_shading_type = None  # Store original viewport shading to restore later
    
        # Store original shading and switch to material view
        self.switch_to_material_view(context)
    
        # Materials come from the pre-made cube
    
        context.collection.objects.link(self.preview)
        context.view_layer.objects.active = None
        
        # Force viewport update
        context.view_layer.update()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        # Set up status bar text and visual indicator
        self.update_status_text(context)
        self.setup_visual_indicator(context)
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def change_tile_size(self, context, direction):
        """Change tile size by direction (+1 = next size, -1 = previous size)"""
        try:
            # Calculate new size index
            old_index = self.tile_size_index
            if direction > 0:
                # Increase size (scroll up)
                new_index = (self.tile_size_index + 1) % len(TILE_SIZES)
            else:
                # Decrease size (scroll down)
                new_index = (self.tile_size_index - 1) % len(TILE_SIZES)
            
            # If size didn't actually change, don't do anything
            if new_index == old_index:
                return
            
            old_rotation = self.preview.rotation_euler.copy()
            old_location = self.preview.location.copy()
            
            # Get the current green face position - this is the actual placement height we want to preserve
            try:
                current_green_face_position = self.get_green_face_world_position()
                preserve_height = current_green_face_position.z
                print(f"[TileBrush] Preserving green face height: Z={preserve_height:.3f}")
            except:
                # Fallback to preview center height
                preserve_height = old_location.z
                print(f"[TileBrush] Fallback: preserving cube center height: Z={preserve_height:.3f}")
            
            # Remove old preview
            bpy.data.objects.remove(self.preview, do_unlink=True)
            
            # Switch to new size
            self.tile_size_index = new_index
            self.current_tile_size = TILE_SIZES[self.tile_size_index]
            
            # Create new preview with new size and current inverted mode
            cube_template = self.get_current_cube_template()
            self.preview = cube_template.copy()
            self.preview.data = cube_template.data.copy()
            self.preview.name = "TileBrush_Preview"
            
            # Ensure preview is visible (template might be hidden)
            self.preview.hide_viewport = False
            self.preview.hide_render = True
            self.preview.hide_select = True
            self.preview.display_type = 'SOLID'
            self.preview.show_in_front = True
            
            # Calculate new cube center position to maintain green face at preserve_height
            # Green face offset for new cube size
            new_half_size = self.current_tile_size / 2.0
            
            # Position cube center so green face (bottom face in default rotation) is at preserve_height
            new_cube_center_z = preserve_height + new_half_size
            
            # Handle X and Y positioning based on speed mode
            if self.movement_speed == 1.0:
                # Normal mode: snap X/Y to 0.5-unit grid (consistent with movement)
                snapped_base = mathutils.Vector((
                    round(old_location.x * 2) / 2,  # 0.5-unit grid snapping
                    round(old_location.y * 2) / 2,  # 0.5-unit grid snapping
                    new_cube_center_z  # Calculated to preserve green face height
                ))
            else:
                # Fast mode: no snapping, preserve exact X/Y position
                snapped_base = mathutils.Vector((
                    old_location.x,  # Keep exact X
                    old_location.y,  # Keep exact Y
                    new_cube_center_z   # Calculated to preserve green face height
                ))
            
            self.base_location = snapped_base
            
            # Restore rotation and position
            self.preview.rotation_euler = old_rotation
            self.preview.location = self.base_location
            self.last_placed_position = None  # Reset placement lock when changing size
            
            # Link new preview to scene
            context.collection.objects.link(self.preview)
            
            size_change = "increased" if direction > 0 else "decreased"
            print(f"[TileBrush] Scroll {size_change} size to {self.current_tile_size}x{self.current_tile_size} units")
            print(f"[TileBrush] Cube center positioned at {snapped_base} to maintain green face at Z={preserve_height:.3f}")
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    
        except Exception as e:
            print(f"[TileBrush] Error changing tile size: {e}")
    
    def update_preview_from_mouse(self, context, event):
    def update_preview_from_mouse(self, context, event):
        """Update preview position based on mouse cursor location in 3D space"""
        try:
            # Get 3D viewport region and region_3d
            region = context.region
            region_3d = context.region_data
            
            if not region or not region_3d:
                return
            
            # Get mouse coordinates
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            
            # Check if this is precision mode (Shift held)
            precision_mode = event.shift
            
            if precision_mode:
                # Precision mode: Use discrete 0.1-unit steps based on mouse movement direction
                # Store last mouse position for direction calculation
                if not hasattr(self, 'last_mouse_x'):
                    self.last_mouse_x = mouse_x
                    self.last_mouse_y = mouse_y
                    return
                
                # Calculate mouse movement delta
                delta_x = mouse_x - self.last_mouse_x
                delta_y = mouse_y - self.last_mouse_y
                
                # Only move if there's significant mouse movement (avoid jitter)
                movement_threshold = 10  # pixels
                if abs(delta_x) < movement_threshold and abs(delta_y) < movement_threshold:
                    return
                
                # Get view-relative movement vectors for consistent direction
                forward_vec, right_vec = self.get_view_relative_vectors(context)
                
                # Convert mouse delta to world movement direction
                step_size = 0.1  # Same as Shift+WASD precision
                current_location = self.preview.location.copy()
                
                # Apply movement based on predominant mouse direction
                if abs(delta_y) > abs(delta_x):
                    # Vertical mouse movement = forward/backward
                    if delta_y > 0:  # Mouse moved down = move forward
                        new_location = current_location + forward_vec * step_size
                    else:  # Mouse moved up = move backward
                        new_location = current_location - forward_vec * step_size
                else:
                    # Horizontal mouse movement = left/right
                    if delta_x > 0:  # Mouse moved right = move right
                        new_location = current_location + right_vec * step_size
                    else:  # Mouse moved left = move left
                        new_location = current_location - right_vec * step_size
                
                # Preserve original Z coordinate (no vertical change from mouse X/Y)
                new_location.z = current_location.z
                
                # Update position (no grid snapping in precision mode)
                self.preview.location = new_location
                self.base_location = new_location.copy()
                self.last_placed_position = None
                
                # Update last mouse position
                self.last_mouse_x = mouse_x
                self.last_mouse_y = mouse_y
                
                # Auto-place tile if auto-mode is enabled
                if hasattr(self, 'auto_mode') and self.auto_mode:
                    tile_placed = self.place_tile_at_current_position(context)
                    if tile_placed:
                        print(f"[TileBrush] AUTO-PLACED tile during precision mouse movement")
                
            else:
                # Normal/Fast mode: Use cursor-to-3D conversion with grid snapping
                # Convert mouse position to 3D coordinate
                # Cast a ray from camera through mouse position
                view_vector = view3d_utils.region_2d_to_vector_3d(region, region_3d, (mouse_x, mouse_y))
                ray_origin = view3d_utils.region_2d_to_origin_3d(region, region_3d, (mouse_x, mouse_y))
                
                # Calculate intersection with horizontal plane at current preview height
                # If we don't have a current height, use cursor height
                if hasattr(self, 'preview') and self.preview:
                    target_height = self.preview.location.z
                else:
                    target_height = context.scene.cursor.location.z
                
                # Ray-plane intersection: find where ray hits plane at target_height
                if abs(view_vector.z) > 0.0001:  # Avoid division by zero
                    # t = (target_height - ray_origin.z) / view_vector.z
                    t = (target_height - ray_origin.z) / view_vector.z
                    intersection = ray_origin + t * view_vector
                    
                    # Apply grid snapping based on current movement mode
                    if self.movement_speed == 1.0:
                        # Normal mode: snap to 0.5-unit grid (matches keyboard normal step)
                        snapped_location = mathutils.Vector((
                            round(intersection.x * 2) / 2,  # 0.5-unit grid
                            round(intersection.y * 2) / 2,  # 0.5-unit grid
                            intersection.z
                        ))
                    else:
                        # Fast mode: snap to cube-side grid (matches keyboard fast step)
                        cube_size = self.current_tile_size  # 0.5, 1.0, 2.0, or 4.0
                        grid_factor = 1.0 / cube_size  # Grid divisions per unit
                        snapped_location = mathutils.Vector((
                            round(intersection.x * grid_factor) / grid_factor,  # Cube-size grid
                            round(intersection.y * grid_factor) / grid_factor,  # Cube-size grid  
                            intersection.z
                        ))
                    
                    # Update preview position
                    if hasattr(self, 'preview') and self.preview:
                        old_location = self.preview.location.copy()
                        self.preview.location = snapped_location
                        self.base_location = snapped_location.copy()
                        self.last_placed_position = None  # Reset placement lock when moving
                        
                        # Auto-place tile if auto-mode is enabled and position actually changed
                        if (hasattr(self, 'auto_mode') and self.auto_mode and 
                            (old_location - snapped_location).length > 0.1):  # Minimum movement threshold
                            tile_placed = self.place_tile_at_current_position(context)
                            if tile_placed:
                                print(f"[TileBrush] AUTO-PLACED tile during mouse movement")
                
        except Exception as e:
            # Silently fail on mouse movement errors to avoid spam
            pass
    
    def modal(self, context, event):
    def modal(self, context, event):
        # Safety check: if preview object has been removed, exit immediately
        if not hasattr(self, 'preview') or not self.preview or self.preview.name not in bpy.data.objects:
            return {'CANCELLED'}
        
        # Handle mouse clicks
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # Check if click is on any rotation icon first
            mouse_x = event.mouse_region_x
            mouse_y = event.mouse_region_y
            
            # Check rotation icons first (priority over tile placement)
            for face_index, (x, y, width, height) in self.rotation_icon_areas.items():
                if (x <= mouse_x <= x + width and y <= mouse_y <= y + height):
                    # Click detected on rotation icon
                    self.rotation_state = face_index
                    rotation, face_name = CUBE_FACES[self.rotation_state]
                    
                    # Apply rotation (cube stays at base location, just rotates)
                    self.preview.rotation_euler = rotation
                    self.preview.location = self.base_location
                    self.last_placed_position = None  # Reset placement lock when rotating
                    
                    print(f"[TileBrush] Clicked rotation icon: {face_name} face (preset {self.rotation_state})")
                    # Update status text
                    self.update_status_text(context)
                    # Force viewport refresh
                    context.view_layer.update()
                    for area in context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                    return {'RUNNING_MODAL'}
            
            # If not clicking on rotation icons, place tile at current mouse position
            if self.place_tile_at_current_position(context):
                # Update status text after placement
                self.update_status_text(context)
                # Force viewport refresh
                context.view_layer.update()
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            return {'RUNNING_MODAL'}
        
        # Handle mouse movement to update preview position
        if event.type == 'MOUSEMOVE':
            self.update_preview_from_mouse(context, event)
            return {'RUNNING_MODAL'}
        
        # Handle Ctrl + Mouse Scroll for size changes
        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.ctrl:
            # Ctrl + Scroll changes cube size
            if event.type == 'WHEELUPMOUSE':
                # Scroll up = increase size
                self.change_tile_size(context, 1)
            else:
                # Scroll down = decrease size  
                self.change_tile_size(context, -1)
            return {'RUNNING_MODAL'}
        
        # Pass through events we don't handle to allow viewport navigation
        handled_keys = {'W', 'S', 'A', 'D', 'UP_ARROW', 'DOWN_ARROW', 'LEFT_ARROW', 'RIGHT_ARROW', 
                       'Q', 'E', 'PAGE_UP', 'PAGE_DOWN', 'TAB', 'T', 'C', 'Z', 'V', 'X', 'I', 'R', 'SPACE', 'ESC', 'RIGHTMOUSE', 'LEFTMOUSE',
                       'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3', 'NUMPAD_4', 'NUMPAD_5', 'NUMPAD_6'}
        
        if event.type not in handled_keys:
            return {'PASS_THROUGH'}
        
        # Movement system: normal uses 0.5 units, fast uses cube side, precision uses 0.1 units
        precision_mode = event.shift  # Shift key enables precision mode
        
        if precision_mode:
            # Precision mode: very small steps with no grid snapping (for edge-to-edge placement)
            step = 0.1  # Fine precision for rotated tile alignment
        elif self.movement_speed == 1.0:
            # Normal speed: always 0.5 units (smallest cube side = minimal grid unit for 32x32 textures)
            step = 0.5  # Always 0.5 units regardless of cube size
        else:
            # Fast speed: each cube moves by its own side length
            step = self.current_tile_size  # 0.5, 1.0, 2.0, or 4.0 units
        loc = self.preview.location.copy()
        key = event.type
        
        # Only handle key press events, not release
        if event.value != 'PRESS':
            return {'RUNNING_MODAL'}
    
        moved_horizontal = False
        moved_vertical = False
        
        # Get view-relative movement vectors
        forward_vec, right_vec = self.get_view_relative_vectors(context)
        
        # Store original Z coordinate to preserve height
        original_z = loc.z
        
        if key in {'W', 'UP_ARROW'}:
            # Move forward relative to view (horizontal only)
            loc += forward_vec * step
            loc.z = original_z  # Preserve original height
            moved_horizontal = True
        elif key in {'S', 'DOWN_ARROW'}:
            # Move backward relative to view (horizontal only)
            loc -= forward_vec * step
            loc.z = original_z  # Preserve original height
            moved_horizontal = True
        elif key in {'A', 'LEFT_ARROW'}:
            # Move left relative to view (horizontal only)
            loc -= right_vec * step
            loc.z = original_z  # Preserve original height
            moved_horizontal = True
        elif key in {'D', 'RIGHT_ARROW'}:
            # Move right relative to view (horizontal only)
            loc += right_vec * step
            loc.z = original_z  # Preserve original height
            moved_horizontal = True
        elif key in {'Q', 'PAGE_UP'}:
            # Vertical movement uses same grid system as horizontal
            vertical_step = step  # Same as horizontal: 0.5 or 1.0 grid units
            loc.z += vertical_step
            moved_vertical = True
        elif key in {'E', 'PAGE_DOWN'}:
            # Vertical movement uses same grid system as horizontal
            vertical_step = step  # Same as horizontal: 0.5 or 1.0 grid units
            loc.z -= vertical_step
            moved_vertical = True
        
        if moved_horizontal:
            # Horizontal movement: different snapping based on mode
            if precision_mode:
                # Precision mode: NO SNAPPING - use exact position for precise edge alignment
                snapped_loc = loc
            elif self.movement_speed == 1.0:
                # Normal mode: snap to 0.5-unit grid (matches 0.5 unit movement)
                snapped_loc = mathutils.Vector((
                    round(loc.x * 2) / 2,  # Snap to 0.5-unit grid
                    round(loc.y * 2) / 2,  # Snap to 0.5-unit grid
                    loc.z  # Preserve Z
                ))
            else:
                # Fast mode: NO SNAPPING - use exact position for edge-to-edge movement
                snapped_loc = loc
            
            self.preview.location = snapped_loc
            self.base_location = snapped_loc.copy()
            self.last_placed_position = None
            
            # Auto-place tile if auto-mode is enabled
            if self.auto_mode:
                tile_placed = self.place_tile_at_current_position(context)
                if tile_placed:
                    print(f"[TileBrush] AUTO-PLACED tile during keyboard movement")
            
            mode_text = "PRECISION" if precision_mode else ("NORMAL" if self.movement_speed == 1.0 else "FAST")
            print(f"[TileBrush] Moved horizontally by {step} units to {snapped_loc} ({mode_text} mode)")
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        elif moved_vertical:
            # Vertical movement: different snapping based on mode
            if precision_mode:
                # Precision mode: NO SNAPPING - use exact position
                snapped_loc = loc
            elif self.movement_speed == 1.0:
                # Normal mode: snap X/Y to 0.5-unit grid, keep exact Z
                snapped_loc = mathutils.Vector((
                    round(loc.x * 2) / 2,  # Snap to 0.5-unit grid
                    round(loc.y * 2) / 2,  # Snap to 0.5-unit grid
                    loc.z  # Keep exact Z position
                ))
            else:
                # Fast mode: NO SNAPPING - use exact position
                snapped_loc = loc
            
            self.preview.location = snapped_loc
            self.base_location = snapped_loc.copy()
            self.last_placed_position = None
            
            # Auto-place tile if auto-mode is enabled
            if self.auto_mode:
                tile_placed = self.place_tile_at_current_position(context)
                if tile_placed:
                    print(f"[TileBrush] AUTO-PLACED tile during keyboard vertical movement")
            
            mode_text = "PRECISION" if precision_mode else ("NORMAL" if self.movement_speed == 1.0 else "FAST")
            print(f"[TileBrush] Moved vertically by {step} units to {snapped_loc} ({mode_text} mode)")
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        if key == 'TAB':
            self.rotation_state = (self.rotation_state + 1) % len(CUBE_FACES)
            rotation, face_name = CUBE_FACES[self.rotation_state]
            
            # Apply rotation (cube stays at base location, just rotates)
            self.preview.rotation_euler = rotation
            self.preview.location = self.base_location
            self.last_placed_position = None  # Reset placement lock when rotating
            
            print(f"[TileBrush] Rotated to {face_name} face (preset {self.rotation_state})")
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        # Direct face selection with number keys (1-6)
        face_number = None
        if key in {'ONE', 'NUMPAD_1'}:
            face_number = 0  # Bottom
        elif key in {'TWO', 'NUMPAD_2'}:
            face_number = 1  # Top
        elif key in {'THREE', 'NUMPAD_3'}:
            face_number = 2  # Front
        elif key in {'FOUR', 'NUMPAD_4'}:
            face_number = 3  # Back
        elif key in {'FIVE', 'NUMPAD_5'}:
            face_number = 4  # Right
        elif key in {'SIX', 'NUMPAD_6'}:
            face_number = 5  # Left
        
        if face_number is not None:
            # Set rotation to specific face
            self.rotation_state = face_number
            rotation, face_name = CUBE_FACES[self.rotation_state]
            
            # Apply rotation (cube stays at base location, just rotates)
            self.preview.rotation_euler = rotation
            self.preview.location = self.base_location
            self.last_placed_position = None  # Reset placement lock when rotating
            
            print(f"[TileBrush] Hotkey {key}: Rotated to {face_name} face (preset {self.rotation_state + 1})")
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        if key == 'R':
            # Rotate cube around Z-axis by 45 degrees (or -45 with Ctrl)
            rotation_angle = math.radians(-45) if event.ctrl else math.radians(45)
            
            # Apply Z-axis rotation to current rotation
            current_rotation = self.preview.rotation_euler.copy()
            current_rotation.z += rotation_angle
            
            # Apply new rotation (cube stays at base location, just rotates)
            self.preview.rotation_euler = current_rotation
            self.preview.location = self.base_location
            self.last_placed_position = None  # Reset placement lock when rotating
            
            direction_text = "counter-clockwise" if event.ctrl else "clockwise"
            angle_text = "-45°" if event.ctrl else "+45°"
            print(f"[TileBrush] R key: Rotated {direction_text} by {angle_text} around Z-axis")
            
            # Update status text
            self.update_status_text(context)
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        if key == 'T':
            # Toggle tile size (same as Ctrl+Scroll Up)
            self.change_tile_size(context, 1)
    
        if key == 'I':
            # Toggle inverted mode (if inverted cubes are available)
            if hasattr(self, 'cube_templates_inverted') and len(self.cube_templates_inverted) > 0:
                old_rotation = self.preview.rotation_euler.copy()
                old_location = self.preview.location.copy()
                
                # Toggle inverted mode
                self.inverted_mode = not self.inverted_mode
                
                # Remove old preview
                bpy.data.objects.remove(self.preview, do_unlink=True)
                
                # Create new preview with inverted mode
                cube_template = self.get_current_cube_template()
                self.preview = cube_template.copy()
                self.preview.data = cube_template.data.copy()
                self.preview.name = "TileBrush_Preview"
                
                # Ensure preview is visible
                self.preview.hide_viewport = False
                self.preview.hide_render = True
                self.preview.hide_select = True
                self.preview.display_type = 'SOLID'
                self.preview.show_in_front = True
                
                # Restore rotation and position
                self.preview.rotation_euler = old_rotation
                self.preview.location = old_location
                self.base_location = old_location.copy()
                self.last_placed_position = None  # Reset placement lock when toggling inversion
                
                # Link new preview to scene
                context.collection.objects.link(self.preview)
                
                mode_text = "INVERTED" if self.inverted_mode else "NORMAL"
                print(f"[TileBrush] Switched to {mode_text} mode")
                
                # Update status text
                self.update_status_text(context)
                # Force viewport refresh
                context.view_layer.update()
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            else:
                print("[TileBrush] Inverted cubes not available - cannot toggle inverted mode")
    
        if key == 'V':
            # Toggle movement speed (disabled in auto-mode)
            if self.auto_mode:
                print("[TileBrush] Speed change disabled in AUTO-MODE - use X to exit auto-mode first")
                return {'RUNNING_MODAL'}
            
            if self.movement_speed == 1.0:
                self.movement_speed = 2.0
                fast_step = self.current_tile_size
                print(f"[TileBrush] Movement speed: FAST ({fast_step} units = cube side, no grid snapping)")
            else:
                self.movement_speed = 1.0
                normal_step = 0.5
                print(f"[TileBrush] Movement speed: NORMAL (0.5 units = minimal grid, with grid snapping)")
            # Update status text to show new speed
            self.update_status_text(context)
            # Force viewport refresh to update visual indicator
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        if key == 'X':
            # Toggle auto-mode
            if not self.auto_mode:
                # Enable auto-mode
                self.auto_mode = True
                self.previous_speed = self.movement_speed  # Store current speed
                self.movement_speed = 2.0  # Force fast speed in auto-mode
                print("[TileBrush] AUTO-MODE enabled: fast speed + auto-place tiles when moving")
            else:
                # Disable auto-mode
                self.auto_mode = False
                self.movement_speed = self.previous_speed  # Restore previous speed
                print(f"[TileBrush] AUTO-MODE disabled: restored speed {'FAST' if self.movement_speed == 2.0 else 'NORMAL'}")
            
            # Update status text and visual indicator
            self.update_status_text(context)
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
        if key == 'C':
            # Delete tile at current position
            self.delete_tile_at_current_position(context)
    
        if key == 'Z' and event.ctrl:
            # Undo last tile placement
            if self.undo_placement():
                # Update status text after undo
                self.update_status_text(context)
                # Force viewport refresh after undo
                context.view_layer.update()
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
    
        if key == 'SPACE':
            # Place tile at current position
            if self.place_tile_at_current_position(context):
                # Update status text after placement
                self.update_status_text(context)
                # Force viewport refresh
                context.view_layer.update()
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
    
        if key in {'ESC', 'RIGHTMOUSE'}:
            self.cleanup_tool(context)
            return {'CANCELLED'}
    
        return {'RUNNING_MODAL'}
    
    def get_green_face_world_position(self):
    def store_undo_snapshot(self):
        """Store current mesh state for undo functionality"""
        if self.master_object is None:
            # No structure yet, store empty state
            self.undo_history.append(None)
            self.undo_positions.append(self.placed_tiles.copy())
        else:
            try:
                # Store a copy of the current mesh data
                mesh_copy = self.master_object.data.copy()
                self.undo_history.append(mesh_copy)
                self.undo_positions.append(self.placed_tiles.copy())
                
                # Limit history to 20 entries
                if len(self.undo_history) > 20:
                    old_mesh = self.undo_history.pop(0)
                    if old_mesh:
                        bpy.data.meshes.remove(old_mesh, do_unlink=True)
                    self.undo_positions.pop(0)
                    
                print(f"[TileBrush] Stored undo snapshot ({len(self.undo_history)}/20)")
            except Exception as e:
                print(f"[TileBrush] Error storing undo snapshot: {e}")
    
    def undo_placement(self):
        """Undo the last tile placement"""
        if not self.undo_history:
            print("[TileBrush] Nothing to undo")
            return False
        
        try:
            # Get the last snapshot
            last_mesh = self.undo_history.pop()
            last_positions = self.undo_positions.pop()
            
            if last_mesh is None:
                # Going back to no structure state
                if self.master_object and self.master_object.name in bpy.data.objects:
                    bpy.data.objects.remove(self.master_object, do_unlink=True)
                self.master_object = None
                self.placed_tiles = set()
                print("[TileBrush] Undid to empty structure")
            else:
                # Restore previous mesh state
                if self.master_object and self.master_object.name in bpy.data.objects:
                    # Replace current mesh with the snapshot
                    old_mesh = self.master_object.data
                    self.master_object.data = last_mesh
                    
                    # Remove the old mesh
                    bpy.data.meshes.remove(old_mesh, do_unlink=True)
                    
                    # Restore placement tracking
                    self.placed_tiles = last_positions
                    
                    print(f"[TileBrush] Undid last placement - {len(self.placed_tiles)} tiles remaining")
                else:
                    print("[TileBrush] Error: Master object not found for undo")
                    return False
            
            # Reset last placement to allow re-placement
            self.last_placed_position = None
            return True
            
        except Exception as e:
            print(f"[TileBrush] Error during undo: {e}")
            return False
    
    def delete_tile_at_current_position(self, context):
        """Delete tile at current preview position"""
        try:
            # Calculate where the tile would be placed (same logic as placement)
            current_face_position = self.get_green_face_world_position()
            
            # Create position key (same format as placement tracking)
            # Use higher precision to match placement logic
            pos_key = (
                round(current_face_position.x, 6),
                round(current_face_position.y, 6), 
                round(current_face_position.z, 6),
                round(self.preview.rotation_euler.x, 6),
                round(self.preview.rotation_euler.y, 6),
                round(self.preview.rotation_euler.z, 6),
                self.tile_size_index,
                self.inverted_mode  # Include inverted mode in position key
            )
            
            # Check if a tile exists at this position
            if pos_key in self.placed_tiles:
                # Store undo snapshot before deletion
                self.store_undo_snapshot()
                
                # Remove from tracking
                self.placed_tiles.remove(pos_key)
                
                print(f"[TileBrush] Deleted tile at {current_face_position} - {len(self.placed_tiles)} tiles remaining")
                
                # Rebuild the visual mesh to match tracking data
                self.rebuild_structure_mesh(context)
                
                # Update status text to show new tile count
                self.update_status_text(context)
                
                # Reset placement lock 
                self.last_placed_position = None
                
            else:
                print(f"[TileBrush] No tile found at current position {current_face_position}")
            
        except Exception as e:
            print(f"[TileBrush] Error deleting tile: {e}")
            import traceback
            traceback.print_exc()
    
    def rebuild_structure_mesh(self, context):
        """Rebuild the entire structure mesh from tracking data"""
        try:
            # Remove existing master object if it exists
            if self.master_object and self.master_object.name in bpy.data.objects:
                bpy.data.objects.remove(self.master_object, do_unlink=True)
                self.master_object = None
            
            # If no tiles remain, we're done
            if not self.placed_tiles:
                print("[TileBrush] No tiles to rebuild - structure cleared")
                return
            
            # Recreate all tiles from tracking data
            temp_objects = []
            
            for pos_key in self.placed_tiles:
                try:
                    # Unpack position key (handle both old and new formats)
                    if len(pos_key) == 8:
                        # New format with inverted mode
                        pos_x, pos_y, pos_z, rot_x, rot_y, rot_z, size_index, inverted_mode = pos_key
                    else:
                        # Old format without inverted mode (backward compatibility)
                        pos_x, pos_y, pos_z, rot_x, rot_y, rot_z, size_index = pos_key
                        inverted_mode = False
                    
                    # Create tile at this position
                    plane_template = self.plane_templates[size_index]
                    tile_obj = plane_template.copy()
                    tile_obj.data = plane_template.data.copy()
                    
                    # Set position and rotation
                    tile_obj.location = (pos_x, pos_y, pos_z)
                    tile_obj.rotation_euler = (rot_x, rot_y, rot_z)
                    tile_obj.name = f"TileBrush_Temp_{len(temp_objects)}"
                    
                    # Make visible
                    tile_obj.hide_viewport = False
                    tile_obj.hide_render = False
                    tile_obj.hide_select = False
                    
                    # Link to scene
                    context.collection.objects.link(tile_obj)
                    temp_objects.append(tile_obj)
                    
                except Exception as e:
                    print(f"[TileBrush] Error recreating tile at {pos_key}: {e}")
                    continue
            
            # Join all tiles into master object
            if temp_objects:
                # First object becomes master
                self.master_object = temp_objects[0]
                self.master_object.name = "TileBrush_Structure"
                
                # Select all objects for joining
                context.view_layer.objects.active = self.master_object
                for obj in temp_objects:
                    obj.select_set(True)
                
                # Join objects
                if len(temp_objects) > 1:
                    bpy.ops.object.join()
                    
                    # Merge overlapping vertices with better threshold for edge connection
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.remove_doubles(threshold=0.01)
                    bpy.ops.object.mode_set(mode='OBJECT')
                
                # Clear selection
                bpy.ops.object.select_all(action='DESELECT')
                context.view_layer.objects.active = None
                
                print(f"[TileBrush] Rebuilt structure with {len(self.placed_tiles)} tiles")
            
            # Force viewport refresh
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                    
        except Exception as e:
            print(f"[TileBrush] Error rebuilding structure: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup_tool(self, context):
        """Clean up preview and template objects when exiting tool"""
        # Ensure all critical attributes exist
        if not hasattr(self, 'draw_handler'):
            self.draw_handler = None
        if not hasattr(self, 'original_shading_type'):
            self.original_shading_type = None
        if not hasattr(self, 'preview'):
            self.preview = None
        if not hasattr(self, 'master_object'):
            self.master_object = None
        if not hasattr(self, 'placed_tiles'):
            self.placed_tiles = set()
        if not hasattr(self, 'undo_history'):
            self.undo_history = []
        if not hasattr(self, 'plane_templates'):
            self.plane_templates = []
        if not hasattr(self, 'cube_templates'):
            self.cube_templates = []
        if not hasattr(self, 'cube_templates_inverted'):
            self.cube_templates_inverted = []
            
        # Clear status text and visual indicator first  
        try:
            self.clear_status_text(context)
        except Exception as e:
            print(f"[TileBrush] Error clearing status text: {e}")
            
        try:
            if self.draw_handler:
                self.remove_visual_indicator()
        except Exception as e:
            print(f"[TileBrush] Error removing visual indicator: {e}")
            
        # Restore original viewport shading
        try:
            if self.original_shading_type:
                self.restore_original_shading(context)
        except Exception as e:
            print(f"[TileBrush] Error restoring viewport shading: {e}")
        
        try:
            # Remove preview
            if hasattr(self, 'preview') and self.preview and self.preview.name in bpy.data.objects:
                bpy.data.objects.remove(self.preview, do_unlink=True)
                print("[TileBrush] Preview removed")
        except Exception as e:
            print(f"[TileBrush] Error removing preview: {e}")
        
        # Clean up template objects more thoroughly
        templates_to_remove = []
        
        # Collect all template objects
        if hasattr(self, 'plane_templates'):
            templates_to_remove.extend(self.plane_templates)
            print(f"[TileBrush] Cleaning up {len(self.plane_templates)} plane templates")
        if hasattr(self, 'cube_templates'):
            templates_to_remove.extend(self.cube_templates)
            print(f"[TileBrush] Cleaning up {len(self.cube_templates)} cube templates")
        if hasattr(self, 'cube_templates_inverted'):
            templates_to_remove.extend(self.cube_templates_inverted)
            print(f"[TileBrush] Cleaning up {len(self.cube_templates_inverted)} inverted cube templates")
        
        # Remove each template object and its data
        for template in templates_to_remove:
            try:
                if template and template.name in bpy.data.objects:
                    template_name = template.name
                    template_data = template.data
                    
                    # Remove object first
                    bpy.data.objects.remove(template, do_unlink=True)
                    
                    # Also remove the mesh data if it's not used by other objects
                    if template_data and template_data.users == 0:
                        bpy.data.meshes.remove(template_data, do_unlink=True)
                        print(f"[TileBrush] Removed template object and data: {template_name}")
                    else:
                        print(f"[TileBrush] Removed template object: {template_name}")
                        
            except Exception as e:
                print(f"[TileBrush] Error removing template: {e}")
        
        # Also clean up any leftover template objects by name pattern (fallback)
        all_template_names = PLANE_NAMES + CUBE_NAMES + CUBE_NAMES_INVERTED
        for name_list in PLANE_PATTERNS + CUBE_PATTERNS + CUBE_PATTERNS_INVERTED:
            all_template_names.extend(name_list)
        
        # Remove duplicates
        all_template_names = list(set(all_template_names))
        
        for obj_name in all_template_names:
            try:
                obj = bpy.data.objects.get(obj_name)
                if obj and obj not in [self.master_object]:  # Don't remove user's structure
                    obj_data = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    
                    # Clean up its data if unused
                    if obj_data and obj_data.users == 0:
                        bpy.data.meshes.remove(obj_data, do_unlink=True)
                    
                    print(f"[TileBrush] Cleaned up leftover template: {obj_name}")
            except Exception as e:
                print(f"[TileBrush] Error cleaning leftover template {obj_name}: {e}")
        
        # Clean up the imported collection if it exists
        try:
            imported_collection = bpy.data.collections.get(OBJECTS_COLLECTION)
            if imported_collection:
                # Check if the collection is empty or only contains objects we want to remove
                remaining_objects = []
                for obj in imported_collection.objects:
                    if (obj != self.master_object and 
                        obj.name not in all_template_names and
                        obj.name != "TileBrush_Structure"):  # Don't count our structure
                        remaining_objects.append(obj)
                
                if len(remaining_objects) == 0:
                    # Collection is empty or only has template objects, safe to remove
                    print(f"[TileBrush] Removing empty collection: {OBJECTS_COLLECTION}")
                    
                    # Simple approach: unlink from scene collection
                    try:
                        context.scene.collection.children.unlink(imported_collection)
                    except:
                        pass
                    
                    # Try to unlink from all parent collections
                    collections_to_check = list(bpy.data.collections)
                    for parent_collection in collections_to_check:
                        try:
                            if imported_collection in parent_collection.children.values():
                                parent_collection.children.unlink(imported_collection)
                        except:
                            pass
                    
                    # Remove the collection data
                    bpy.data.collections.remove(imported_collection)
                    print(f"[TileBrush] Removed imported collection: {OBJECTS_COLLECTION}")
                else:
                    print(f"[TileBrush] Kept collection '{OBJECTS_COLLECTION}' - contains {len(remaining_objects)} other objects")
                    
        except Exception as e:
            print(f"[TileBrush] Error cleaning up collection: {e}")
            import traceback
            traceback.print_exc()
        
        # Final aggressive cleanup: search for any objects that look like templates
        print("[TileBrush] Performing final cleanup scan...")
        objects_removed = 0
        try:
            # Get all objects currently in the scene
            all_objects = list(bpy.data.objects)
            
            for obj in all_objects:
                # Skip if this is the user's structure
                if obj == self.master_object:
                    continue
                    
                # Check if object name matches any template pattern
                is_template = False
                for template_name in all_template_names:
                    if obj.name == template_name or obj.name.startswith(template_name + "."):
                        is_template = True
                        break
                
                # Also check if it's a copy of template objects (like Plane1x1.001)
                if not is_template:
                    for base_name in ["Plane0.5x0.5", "Plane1x1", "Plane2x2", "Plane4x4", 
                                    "Cube0.5x0.5", "Cube1x1", "Cube2x2", "Cube4x4",
                                    "Cube0.5x0.5_I", "Cube1x1_I", "Cube2x2_I", "Cube4x4_I"]:
                        if obj.name.startswith(base_name + ".") or obj.name == base_name:
                            is_template = True
                            break
                
                if is_template:
                    try:
                        obj_name = obj.name
                        obj_data = obj.data
                        
                        # Remove the object
                        bpy.data.objects.remove(obj, do_unlink=True)
                        
                        # Clean up its data if unused
                        if obj_data and obj_data.users == 0:
                            if hasattr(bpy.data, 'meshes') and obj_data.name in bpy.data.meshes:
                                bpy.data.meshes.remove(obj_data, do_unlink=True)
                        
                        objects_removed += 1
                        print(f"[TileBrush] Final cleanup removed: {obj_name}")
                        
                    except Exception as e:
                        print(f"[TileBrush] Error in final cleanup of {obj.name}: {e}")
                        
        except Exception as e:
            print(f"[TileBrush] Error in final cleanup scan: {e}")
        
        if objects_removed > 0:
            print(f"[TileBrush] Final cleanup removed {objects_removed} template objects")
        else:
            print("[TileBrush] Final cleanup: no template objects found")
        
        # Clean up undo history meshes
        if hasattr(self, 'undo_history'):
            for mesh in self.undo_history:
                if mesh and mesh.name in bpy.data.meshes:
                    try:
                        bpy.data.meshes.remove(mesh, do_unlink=True)
                    except:
                        pass
            print(f"[TileBrush] Cleaned up {len(self.undo_history)} undo snapshots")
        
        # Keep the master object - it's the user's structure
        if hasattr(self, 'master_object') and self.master_object:
            structure_name = self.master_object.name
            tile_count = len(self.placed_tiles) if hasattr(self, 'placed_tiles') else 0
            print(f"[TileBrush] Structure '{structure_name}' remains in scene with {tile_count} tiles")
        
        # Summary
        total_templates_cleaned = len([t for t in templates_to_remove if t])
        print(f"[TileBrush] Tool cleanup completed - removed {total_templates_cleaned} template objects total")
        
        # Force viewport refresh
        try:
            context.view_layer.update()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        except:
            pass
    
    def __del__(self):
        """Fallback cleanup in case tool is destroyed unexpectedly"""
        try:
            # Remove visual indicator if it exists
            if hasattr(self, 'draw_handler') and self.draw_handler:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
                except:
                    pass
            
            # This cleanup is more conservative - only removes objects we're sure about
            if hasattr(self, 'preview') and self.preview:
                try:
                    if self.preview.name in bpy.data.objects:
                        bpy.data.objects.remove(self.preview, do_unlink=True)
                except:
                    pass
        except:
            pass  # Ignore all errors during fallback cleanup
    
    def place_tile_at_current_position(self, context):
        """Place a tile at the current preview position"""
        try:
            # Calculate where the tile would be placed
            current_face_position = self.get_green_face_world_position()
            
            # Create a position key that's rounded to avoid floating point precision issues
            # Use higher precision for position (6 decimal places) to allow closer placement
            pos_key = (
                round(current_face_position.x, 6),
                round(current_face_position.y, 6), 
                round(current_face_position.z, 6),
                round(self.preview.rotation_euler.x, 6),
                round(self.preview.rotation_euler.y, 6),
                round(self.preview.rotation_euler.z, 6),
                self.tile_size_index,
                self.inverted_mode  # Include inverted mode in position key
            )
            
            # Check if a tile already exists at this position
            if pos_key in self.placed_tiles:
                print("[TileBrush] Cannot place tile - position already occupied!")
                return False
            
            # Store undo snapshot before placing tile
            self.store_undo_snapshot()
            
            # Create actual plane at preview location
            plane_template = self.plane_templates[self.tile_size_index]
            placed = plane_template.copy()
            placed.data = plane_template.data.copy()
            
            # Place the tile and make it visible (template might be hidden)
            placed.location = current_face_position
            placed.rotation_euler = self.preview.rotation_euler.copy()
            placed.name = f"{PLANE_NAMES[self.tile_size_index]}_temp"
            placed.hide_viewport = False  # Ensure placed tile is visible
            placed.hide_render = False   # Allow rendering
            placed.hide_select = False   # Allow selection
            context.collection.objects.link(placed)
            
            # Join to master object or create master object
            if self.master_object is None:
                # First tile becomes the master object
                self.master_object = placed
                self.master_object.name = "TileBrush_Structure"
                print(f"[TileBrush] Created master structure object")
            else:
                # Join new tile to master object
                try:
                    context.view_layer.objects.active = self.master_object
                    placed.select_set(True)
                    self.master_object.select_set(True)
                    
                    # Join objects (placed will be merged into master_object)
                    bpy.ops.object.join()
                    
                    # Enter edit mode to merge overlapping vertices
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    
                    # Merge vertices that are very close together (larger threshold for better edge connection)
                    bpy.ops.mesh.remove_doubles(threshold=0.01)
                    
                    # Return to object mode
                    bpy.ops.object.mode_set(mode='OBJECT')
                    
                    # Clear selection
                    bpy.ops.object.select_all(action='DESELECT')
                    context.view_layer.objects.active = None
                    
                    print(f"[TileBrush] Tile joined and connected to structure")
                except Exception as e:
                    print(f"[TileBrush] Error joining tile to structure: {e}")
                    # If join fails, at least the tile is still placed
                    try:
                        bpy.ops.object.mode_set(mode='OBJECT')
                    except:
                        pass
                    bpy.ops.object.select_all(action='DESELECT')
                    context.view_layer.objects.active = None
            
            # Add to placed tiles set to prevent future placement at this spot
            self.placed_tiles.add(pos_key)
            
            # Also update last placement for immediate double-click protection
            current_state = (current_face_position, tuple(self.preview.rotation_euler), self.tile_size_index)
            self.last_placed_position = current_state
            
            print(f"[TileBrush] Tile placed at {current_face_position} (size: {int(self.current_tile_size)}x{int(self.current_tile_size)}) - Total tiles: {len(self.placed_tiles)}")
            return True
            
        except Exception as e:
            print(f"[TileBrush] Error placing tile: {e}")
            return False
    
    
    
    


def menu_func(self, context):
    self.layout.operator(VIEW3D_OT_tile_brush.bl_idname, text="Tile Brush")


