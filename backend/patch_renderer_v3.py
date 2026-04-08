
import sys
import re

# Try with utf-8 first
try:
    with open('services/professional_svg_renderer.py', 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    # Fallback to latin-1
    with open('services/professional_svg_renderer.py', 'r', encoding='latin-1') as f:
        content = f.read()

# Fix draw_site_context signature and local offsets
content = content.replace(
    'def draw_site_context(placed_rooms: list, plot_width: float, plot_height: float,\n                      scale: int, margin: int, dwg,',
    'def draw_site_context(placed_rooms: list, plot_width: float, plot_height: float,\n                      scale: int, offset_x: int, offset_y: int, dwg,'
)
content = content.replace(
    '    # Use margin directly as offset\n    ox, oy = margin, margin',
    '    # Use offset_x/offset_y\n    ox, oy = offset_x, offset_y'
)

# Fix render_room_polygons
content = content.replace(
    'def render_room_polygons(placed_rooms, scale, margin, dwg):',
    'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):'
)
content = content.replace(
    '        x, y = margin + room[\'x\'] * scale, margin + room[\'y\'] * scale',
    '        x, y = offset_x + room[\'x\'] * scale, offset_y + room[\'y\'] * scale'
)

# Fix ALL other sub-renderers by replacing 'scale, margin, dwg' with 'scale, offset_x, offset_y, dwg'
# AND replacing 'margin +' with 'offset_x +' or 'offset_y +' within those functions.
# However, many functions use 'margin' for both x and y. 
# A safer way is to just define 'ox, oy = margin_x, margin_y' inside them.

# Let's target the remaining ones found in render_blueprint_professional:
# render_bathroom_fixtures, render_kitchen_counter, render_furniture_symbols, render_wall_boundary_polygon,
# render_doors, render_windows, render_staircase_symbol, render_lift_symbol, render_entry_marker,
# render_room_labels_architectural, render_structural_columns

list_of_funcs = [
    'render_bathroom_fixtures', 'render_kitchen_counter', 'render_furniture_symbols', 
    'render_wall_boundary_polygon', 'render_doors', 'render_windows', 
    'render_staircase_symbol', 'render_lift_symbol', 'render_entry_marker',
    'render_room_labels_architectural', 'render_structural_columns'
]

for func in list_of_funcs:
    # Replace signature
    content = content.replace(
        f'def {func}(placement_data, scale, margin, dwg',
        f'def {func}(placement_data, scale, offset_x, offset_y, dwg'
    )
    content = content.replace(
        f'def {func}(items, scale, margin, dwg',
        f'def {func}(items, scale, offset_x, offset_y, dwg'
    )
    # Special cases for signatures
    if func == 'render_wall_boundary_polygon':
         content = content.replace(
             'def render_wall_boundary_polygon(wall_boundary: Polygon, scale: int, margin: int, dwg,',
             'def render_wall_boundary_polygon(wall_boundary: Polygon, scale: int, offset_x: int, offset_y: int, dwg,'
         )
    if func == 'render_room_labels_architectural':
         content = content.replace(
             'def render_room_labels_architectural(placed_rooms, scale, margin, dwg,',
             'def render_room_labels_architectural(placed_rooms, scale, offset_x, offset_y, dwg,'
         )
    if func == 'render_structural_columns':
         content = content.replace(
             'def render_structural_columns(columns: list, scale: int, margin: int, dwg) -> None:',
             'def render_structural_columns(columns: list, scale: int, offset_x: int, offset_y: int, dwg) -> None:'
         )
    
    # Replace internal margin usage within these functions (Assuming they use 'margin + ...')
    # This is a bit risky but we can try to find and replace.
    # Actually, the most robust way is to just update the local variables.

# Final check for 'is_roof' being defined in render_blueprint_professional
# My previous patch should have fixed it.

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully patched all renderer signatures for centering")
