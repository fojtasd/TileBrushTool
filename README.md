# Tile Brush Tool for Blender

A powerful keyboard-driven tile placement tool for Blender with preview and rotation capabilities. This addon provides an intuitive way to place tiles in your 3D scene with precise control and immediate visual feedback.

## Features

- **Keyboard + Mouse Control**: Intuitive tile placement with single-axis view-relative movement
- **Multiple Tile Sizes**: Supports 4 tile sizes (0.5x0.5, 1x1, 2x2, and 4x4 units)
- **Real-time Preview**: Visual preview that follows cursor with grid snapping
- **Face Orientation**: Support for 6 different face orientations with direct selection
- **Inverted Mode**: Optional inverted cube mode for opposite face orientation
- **Connected Structure**: Places all tiles as parts of a single connected structure object
- **Visual Feedback**: Shows hotkey hints in status bar + orange "ACTIVE" indicator
- **Material Preview**: Auto-switches to Material view for immediate visual feedback
- **Undo Support**: Built-in undo functionality for tile placement

## Requirements

- Blender 4.0.0 or newer
- The `TileBrushObjects.blend` file must be in the same directory as the script

## Installation

1. Download the `tile_brush_tool` folder and `TileBrushObjects.blend`
2. Zip the entire `tile_brush_tool` directory
3. In Blender, go to Edit > Preferences > Add-ons
4. Click "Install" and choose the zipped addon
5. Enable the addon and ensure `TileBrushObjects.blend` sits inside the addon folder

## Controls

### Basic Movement
- **Mouse**: Move preview
- **WASD**: Move along view-relative axes (0.5 units in normal mode, cube-side in fast mode)
- **QE**: Additional movement controls
- **Shift + Mouse/WASD/QE**: Precision move (0.1 units, no snap)
- **Left Click**: Place tile
- **Space**: Place tile (alternative)

### Face and Rotation
- **1-6**: Direct face selection (1=Bottom, 2=Top, 3=Front, 4=Back, 5=Right, 6=Left)
- **TAB**: Rotate face
- **R**: Rotate Z-axis +45°
- **Ctrl+R**: Rotate Z-axis -45°

### Tool Settings
- **T**: Toggle size
- **I**: Toggle invert mode
- **V**: Toggle speed mode
- **X**: Toggle auto-mode
- **Ctrl+Scroll**: Change size

### Actions
- **Ctrl+Z**: Undo
- **C**: Delete tile at current position
- **Esc**: Cancel/Exit tool

## Movement Modes

- **Normal Mode**: 0.5 unit movement with grid snapping
- **Fast Mode**: Movement by cube-side length with snapping
- **Precision Mode**: 0.1 unit movement without snapping (Shift modifier)
- **Auto Mode**: Enables fast speed + automatically places tiles when moving

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

David Fójcik 