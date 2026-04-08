
import sys

# Try with utf-8 first
try:
    with open('services/professional_svg_renderer.py', 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    # Fallback to latin-1
    with open('services/professional_svg_renderer.py', 'r', encoding='latin-1') as f:
        content = f.read()

# Replace draw_site_context signature and body
content = content.replace(
    'def draw_site_context(placed_rooms, plot_width, plot_height, scale, margin, dwg, building_program=None):',
    'def draw_site_context(placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, dwg, building_program=None):'
)
content = content.replace(
    '# Use margin directly as offset\n    ox, oy = margin, margin',
    '# Use offset_x/offset_y\n    ox, oy = offset_x, offset_y'
)

# Replace render_room_polygons signature and body
content = content.replace(
    'def render_room_polygons(placed_rooms, scale, margin, dwg):',
    'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):'
)

# Replace internal loop in render_room_polygons
# We need to be careful with indentation and exact string
content = content.replace(
    '        x, y = margin + room[\'x\'] * scale, margin + room[\'y\'] * scale',
    '        x, y = offset_x + room[\'x\'] * scale, offset_y + room[\'y\'] * scale'
)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully patched renderer signatures")
