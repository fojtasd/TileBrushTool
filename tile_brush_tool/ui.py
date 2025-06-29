import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from .objects import CUBE_FACES

class UIMixin:
    """User interface helpers for status text and on-screen indicators."""
    def update_status_text(self, context):
        """Update the status bar text with current tool info and hotkeys"""
        try:
            # Get current face name
            _, face_name = CUBE_FACES[self.rotation_state]
            
            # Build status text with hotkeys
            # Get movement speed text with shift description
            if self.auto_mode:
                speed_text = f"Speed: AUTO ({self.current_tile_size} units, auto-place)"
            elif self.movement_speed == 2.0:
                speed_text = f"Speed: FAST ({self.current_tile_size} units, no-grid)"
            else:
                speed_text = f"Speed: NORMAL (0.5 units, with-grid)"
            
            # Get movement info
            if self.movement_speed == 1.0:
                # Normal speed: always 0.5 units (smallest cube side = minimal grid unit for 32x32 textures)
                movement_step = 0.5
            else:
                movement_step = self.current_tile_size
            movement_info = f"±{movement_step}"
            
            # Get inverted mode text
            inverted_text = "INVERTED" if self.inverted_mode else "NORMAL"
            
            status_text = (
                f"Tile Brush: {int(self.current_tile_size)}x{int(self.current_tile_size)} {inverted_text} | "
                f"Face: {face_name} ({self.rotation_state + 1}) | "
                f"{speed_text} | "
                f"Tiles: {len(self.placed_tiles)} | "
                f"Mouse: Move+Click | Shift+Mouse/WASD: Precision (0.1) | Ctrl+Scroll: Size | 1-6: Faces | WASD/QE: Move ({movement_info}) | TAB/Click: Rotate | R: Z-Rotate | T: Size | I: Invert | V: Speed | X: Auto | Space: Place | Ctrl+Z: Undo | C: Delete | Esc: Exit"
            )
            
            # Set status text in header
            context.workspace.status_text_set(status_text)
            print(f"[TileBrush] Status updated: {len(self.placed_tiles)} tiles, {face_name} face")
            
        except Exception as e:
            print(f"[TileBrush] Error updating status: {e}")
    
    def clear_status_text(self, context):
        """Clear the status bar text"""
        try:
            context.workspace.status_text_set(None)
            print("[TileBrush] Status text cleared")
        except Exception as e:
            print(f"[TileBrush] Error clearing status: {e}")
    
    def setup_visual_indicator(self, context):
        """Set up the visual indicator that shows tool is active"""
        try:
            # Add draw handler for visual indicator
            self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_visual_indicator, 
                (context,), 
                'WINDOW', 
                'POST_PIXEL'
            )
            print("[TileBrush] Visual indicator enabled")
        except Exception as e:
            print(f"[TileBrush] Error setting up visual indicator: {e}")
    
    def draw_visual_indicator(self, context):
        """Draw the tile brush active indicator in center-bottom of viewport with height display"""
        try:
            # Get the current region
            region = context.region
            if not region:
                return
            
            # Set up main text
            font_id = 0
            main_text = "■ TILE BRUSH MODE ■"
            
            # Get current Z coordinate from where tile will be placed (green face position)
            if hasattr(self, 'preview') and self.preview:
                try:
                    green_face_position = self.get_green_face_world_position()
                    current_z = green_face_position.z
                except:
                    current_z = self.preview.location.z
            elif hasattr(self, 'base_location') and self.base_location:
                current_z = self.base_location.z
            else:
                # Fallback to cursor location
                current_z = context.scene.cursor.location.z
            
            height_text = f"Height: Z = {current_z:.1f}"
            
            # Get movement speed text with shift description
            if self.auto_mode:
                speed_text = f"Speed: AUTO ({self.current_tile_size} units, auto-place)"
            elif self.movement_speed == 2.0:
                speed_text = f"Speed: FAST ({self.current_tile_size} units, no-grid)"
            else:
                speed_text = f"Speed: NORMAL (0.5 units, with-grid)"
            
            # Get current cube size text
            size_text = f"Size: {int(self.current_tile_size)}"
            
            # Get inverted mode text
            mode_text = f"Mode: {'INVERTED' if self.inverted_mode else 'NORMAL'}"
            
            # Combine height, speed, size, and mode on same line with spacing
            info_text = f"{height_text}    {speed_text}    {size_text}    {mode_text}"
            
            # Auto-mode notification (red text)
            auto_text = "AUTO ACTIVE" if self.auto_mode else None
            
            # Set font sizes and get dimensions
            blf.size(font_id, 24)
            main_text_width = blf.dimensions(font_id, main_text)[0]
            main_text_height = 30
            
            blf.size(font_id, 18)
            info_text_width = blf.dimensions(font_id, info_text)[0]
            info_text_height = 25
            
            # Auto text dimensions (if active)
            auto_text_width = 0
            auto_text_height = 20
            if auto_text:
                blf.size(font_id, 16)
                auto_text_width = blf.dimensions(font_id, auto_text)[0]
            
            # Calculate positions
            main_x = (region.width - main_text_width) // 2
            info_x = (region.width - info_text_width) // 2
            auto_x = (region.width - auto_text_width) // 2 if auto_text else 0
            
            # Position calculations with auto text
            if auto_text:
                main_y = 150  # From bottom with padding for all three texts
                info_y = main_y - info_text_height - 10  # Below main text
                auto_y = info_y - auto_text_height - 10  # Below info text
            else:
                main_y = 120  # From bottom with padding for both texts
                info_y = main_y - info_text_height - 10  # Below main text
                auto_y = 0  # Not used
            
            # Ensure positions are valid
            if main_x < 0 or main_y < 0 or info_y < 0:
                return
            
            # Calculate combined background area
            bg_padding = 20
            bg_left = min(main_x, info_x)
            bg_right = max(main_x + main_text_width, info_x + info_text_width)
            
            if auto_text:
                bg_left = min(bg_left, auto_x)
                bg_right = max(bg_right, auto_x + auto_text_width)
                bg_top = main_y + main_text_height + 10
                bg_bottom = auto_y - 10
            else:
                bg_top = main_y + main_text_height + 10
                bg_bottom = info_y - 10
            
            bg_left -= bg_padding
            bg_right += bg_padding
            
            # Draw bright orange background with border
            gpu.state.blend_set('ALPHA')
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            shader.bind()
            
            # Main background (bright orange) - covers both texts
            bg_vertices = [
                (bg_left, bg_bottom),
                (bg_right, bg_bottom),
                (bg_right, bg_top),
                (bg_left, bg_top)
            ]
            
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": bg_vertices})
            shader.uniform_float("color", (1.0, 0.5, 0.0, 0.9))  # Bright orange
            batch.draw(shader)
            
            # Border (darker orange)
            border_width = 3
            border_vertices = [
                # Top border
                (bg_left - border_width, bg_top),
                (bg_right + border_width, bg_top),
                (bg_right + border_width, bg_top + border_width),
                (bg_left - border_width, bg_top + border_width),
                # Bottom border  
                (bg_left - border_width, bg_bottom - border_width),
                (bg_right + border_width, bg_bottom - border_width),
                (bg_right + border_width, bg_bottom),
                (bg_left - border_width, bg_bottom),
                # Left border
                (bg_left - border_width, bg_bottom),
                (bg_left, bg_bottom),
                (bg_left, bg_top),
                (bg_left - border_width, bg_top),
                # Right border
                (bg_right, bg_bottom),
                (bg_right + border_width, bg_bottom),
                (bg_right + border_width, bg_top),
                (bg_right, bg_top)
            ]
            
            # Draw border in chunks
            border_quads = [
                border_vertices[0:4],   # Top
                border_vertices[4:8],   # Bottom  
                border_vertices[8:12],  # Left
                border_vertices[12:16]  # Right
            ]
            
            for quad in border_quads:
                batch_border = batch_for_shader(shader, 'TRI_FAN', {"pos": quad})
                shader.uniform_float("color", (0.6, 0.2, 0.0, 1.0))  # Dark orange border
                batch_border.draw(shader)
            
            gpu.state.blend_set('NONE')
            
            # Draw main text (bright white with shadow effect)
            blf.size(font_id, 24)
            # Shadow
            blf.color(font_id, 0.0, 0.0, 0.0, 0.8)  # Black shadow
            blf.position(font_id, main_x + 2, main_y - 2, 0)
            blf.draw(font_id, main_text)
            
            # Main text
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)  # Bright white
            blf.position(font_id, main_x, main_y, 0)
            blf.draw(font_id, main_text)
            
            # Draw info text (height + speed) (bright yellow with shadow effect)
            blf.size(font_id, 18)
            # Shadow
            blf.color(font_id, 0.0, 0.0, 0.0, 0.8)  # Black shadow
            blf.position(font_id, info_x + 2, info_y - 2, 0)
            blf.draw(font_id, info_text)
            
            # Info text
            blf.color(font_id, 1.0, 1.0, 0.0, 1.0)  # Bright yellow
            blf.position(font_id, info_x, info_y, 0)
            blf.draw(font_id, info_text)
            
            # Auto text (if active) with shadow effect
            if auto_text:
                blf.size(font_id, 16)
                # Shadow
                blf.color(font_id, 0.0, 0.0, 0.0, 0.8)  # Black shadow
                blf.position(font_id, auto_x + 2, auto_y - 2, 0)
                blf.draw(font_id, auto_text)
                
                # Main auto text
                blf.color(font_id, 1.0, 0.0, 0.0, 1.0)  # Bright red
                blf.position(font_id, auto_x, auto_y, 0)
                blf.draw(font_id, auto_text)
            
            # Draw rotation icons above the main indicator
            self.draw_rotation_icons(context, region, bg_left, bg_right, bg_top + 20)
            
        except Exception as e:
            print(f"[TileBrush] Error drawing visual indicator: {e}")
            import traceback
            traceback.print_exc()
            self.remove_visual_indicator()
    
    def draw_rotation_icons(self, context, region, indicator_left, indicator_right, icons_y):
        """Draw clickable rotation icons for the 6 cube faces"""
        try:
            # Clear previous icon areas
            self.rotation_icon_areas.clear()
            
            # Icon settings - BIGGER ICONS!
            icon_size = 60  # Increased from 40 to 60
            icon_spacing = 15  # Increased spacing too
            total_icons = 6
            total_width = (icon_size * total_icons) + (icon_spacing * (total_icons - 1))
            
            # Center the icons horizontally
            start_x = (region.width - total_width) // 2
            
            # Face names and colors for each rotation with numbers
            face_info = [
                ("1\nBTM", (0.3, 0.8, 0.3, 0.9)),  # Bottom - Green
                ("2\nTOP", (0.8, 0.3, 0.3, 0.9)),  # Top - Red  
                ("3\nFRT", (0.3, 0.3, 0.8, 0.9)),  # Front - Blue
                ("4\nBCK", (0.8, 0.8, 0.3, 0.9)),  # Back - Yellow
                ("5\nRGT", (0.8, 0.3, 0.8, 0.9)),  # Right - Magenta
                ("6\nLFT", (0.3, 0.8, 0.8, 0.9)),  # Left - Cyan
            ]
            
            # Set up GPU drawing
            gpu.state.blend_set('ALPHA')
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            shader.bind()
            
            font_id = 0
            blf.size(font_id, 12)
            
            for i, (face_text, face_color) in enumerate(face_info):
                # Calculate icon position
                icon_x = start_x + i * (icon_size + icon_spacing)
                icon_y = icons_y
                
                # Store click area for mouse detection
                self.rotation_icon_areas[i] = (icon_x, icon_y, icon_size, icon_size)
                
                # Determine if this is the active rotation
                is_active = (i == self.rotation_state)
                
                # Draw icon background
                if is_active:
                    # Active icon: brighter and with border
                    bg_color = (face_color[0] * 1.2, face_color[1] * 1.2, face_color[2] * 1.2, 1.0)
                    border_color = (1.0, 1.0, 1.0, 1.0)  # White border for active
                else:
                    # Inactive icon: dimmer
                    bg_color = (face_color[0] * 0.7, face_color[1] * 0.7, face_color[2] * 0.7, 0.8)
                    border_color = (0.4, 0.4, 0.4, 0.8)  # Gray border for inactive
                
                # Draw main icon background
                icon_vertices = [
                    (icon_x, icon_y),
                    (icon_x + icon_size, icon_y),
                    (icon_x + icon_size, icon_y + icon_size),
                    (icon_x, icon_y + icon_size)
                ]
                
                batch = batch_for_shader(shader, 'TRI_FAN', {"pos": icon_vertices})
                shader.uniform_float("color", bg_color)
                batch.draw(shader)
                
                # Draw border
                border_width = 3 if is_active else 2
                border_vertices = [
                    # Top border
                    (icon_x - border_width, icon_y + icon_size),
                    (icon_x + icon_size + border_width, icon_y + icon_size),
                    (icon_x + icon_size + border_width, icon_y + icon_size + border_width),
                    (icon_x - border_width, icon_y + icon_size + border_width),
                    # Bottom border
                    (icon_x - border_width, icon_y - border_width),
                    (icon_x + icon_size + border_width, icon_y - border_width),
                    (icon_x + icon_size + border_width, icon_y),
                    (icon_x - border_width, icon_y),
                    # Left border
                    (icon_x - border_width, icon_y),
                    (icon_x, icon_y),
                    (icon_x, icon_y + icon_size),
                    (icon_x - border_width, icon_y + icon_size),
                    # Right border
                    (icon_x + icon_size, icon_y),
                    (icon_x + icon_size + border_width, icon_y),
                    (icon_x + icon_size + border_width, icon_y + icon_size),
                    (icon_x + icon_size, icon_y + icon_size)
                ]
                
                # Draw border in chunks
                border_quads = [
                    border_vertices[0:4],   # Top
                    border_vertices[4:8],   # Bottom  
                    border_vertices[8:12],  # Left
                    border_vertices[12:16]  # Right
                ]
                
                for quad in border_quads:
                    batch_border = batch_for_shader(shader, 'TRI_FAN', {"pos": quad})
                    shader.uniform_float("color", border_color)
                    batch_border.draw(shader)
                
                # Draw text label (handle two lines: number and face name)
                lines = face_text.split('\n')
                
                # Draw number (larger font)
                number_text = lines[0]
                blf.size(font_id, 16)  # Larger font for number
                number_width = blf.dimensions(font_id, number_text)[0]
                number_x = icon_x + (icon_size - number_width) // 2
                number_y = icon_y + icon_size // 2 + 8  # Upper half
                
                # Number shadow
                blf.color(font_id, 0.0, 0.0, 0.0, 0.8)  # Black shadow
                blf.position(font_id, number_x + 1, number_y - 1, 0)
                blf.draw(font_id, number_text)
                
                # Main number
                text_color = (1.0, 1.0, 1.0, 1.0) if is_active else (0.9, 0.9, 0.9, 1.0)
                blf.color(font_id, *text_color)
                blf.position(font_id, number_x, number_y, 0)
                blf.draw(font_id, number_text)
                
                # Draw face name (smaller font)
                if len(lines) > 1:
                    face_text = lines[1]
                    blf.size(font_id, 12)  # Smaller font for face name
                    face_width = blf.dimensions(font_id, face_text)[0]
                    face_x = icon_x + (icon_size - face_width) // 2
                    face_y = icon_y + icon_size // 2 - 12  # Lower half
                    
                    # Face name shadow
                    blf.color(font_id, 0.0, 0.0, 0.0, 0.8)  # Black shadow
                    blf.position(font_id, face_x + 1, face_y - 1, 0)
                    blf.draw(font_id, face_text)
                    
                    # Main face name
                    blf.color(font_id, *text_color)
                    blf.position(font_id, face_x, face_y, 0)
                    blf.draw(font_id, face_text)
            
            gpu.state.blend_set('NONE')
            
            # Draw title above icons
            title_text = "ROTATION (Click or Press 1-6)"
            blf.size(font_id, 16)  # Bigger title for bigger icons
            title_width = blf.dimensions(font_id, title_text)[0]
            title_x = (region.width - title_width) // 2
            title_y = icons_y + icon_size + 20  # More space for bigger icons
            
            # Title shadow
            blf.color(font_id, 0.0, 0.0, 0.0, 0.8)
            blf.position(font_id, title_x + 1, title_y - 1, 0)
            blf.draw(font_id, title_text)
            
            # Main title
            blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
            blf.position(font_id, title_x, title_y, 0)
            blf.draw(font_id, title_text)
            
        except Exception as e:
            print(f"[TileBrush] Error drawing rotation icons: {e}")
            import traceback
            traceback.print_exc()
    
    
     
    def remove_visual_indicator(self):
        """Remove the visual indicator"""
        try:
            if self.draw_handler:
                bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
                self.draw_handler = None
                print("[TileBrush] Visual indicator removed")
        except Exception as e:
            print(f"[TileBrush] Error removing visual indicator: {e}")
    
    def switch_to_material_view(self, context):
        """Switch viewport to material shading and store original setting"""
        try:
            # Find the 3D viewport space
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            # Store original shading type
                            self.original_shading_type = space.shading.type
                            # Switch to material view
                            space.shading.type = 'MATERIAL'
                            print(f"[TileBrush] Switched from '{self.original_shading_type}' to 'MATERIAL' view")
                            return
        except Exception as e:
            print(f"[TileBrush] Error switching to material view: {e}")
    
    def restore_original_shading(self, context):
        """Restore original viewport shading"""
        try:
            if self.original_shading_type is not None:
                # Find the 3D viewport space
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            if space.type == 'VIEW_3D':
                                # Restore original shading
                                space.shading.type = self.original_shading_type
                                print(f"[TileBrush] Restored viewport shading to '{self.original_shading_type}'")
                                return
        except Exception as e:
            print(f"[TileBrush] Error restoring viewport shading: {e}")
    


