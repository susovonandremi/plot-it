
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

# 1. Broad Signature Fix
# Match patterns like: def name(..., scale, margin, dwg, ...)
#                     def name(..., scale: int, margin: int, dwg, ...)
#                     def name(..., scale, offset_x, offset_y, dwg, ...) (already partially fixed)

# a) Standardize to (scale, offset_x, offset_y, dwg)
content = re.sub(r'(scale|scale: int|scale: float),\s*(margin|margin: int|margin: float|offset_x|offset_x: int),\s*(dwg|offset_y|offset_y: int)', 
                 r'scale, offset_x, offset_y, dwg', content)

# b) Fix specific utility signatures like _polygon_to_svg_path
content = re.sub(r'def _polygon_to_svg_path\(poly,\s*scale:\s*float,\s*margin:\s*float\)',
                 r'def _polygon_to_svg_path(poly, scale: float, offset_x: float, offset_y: float)', content)

# 2. Body Restoration
# Insert 'margin = offset_x' shim at the start of all likely affected functions.
# We'll target lines starting with 'def ' that now have offset_x, offset_y.
def apply_shims(code):
    lines = code.split('\n')
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if line.strip().startswith('def ') and 'offset_x' in line and 'offset_y' in line and 'dwg' in line:
            # Insert shim
            indent = line[:line.find('def ')] + '    '
            new_lines.append(f"{indent}margin = offset_x # Legacy shim")
    return '\n'.join(new_lines)

# Wait, instead of generic shim, let's fix the specific cases in _polygon_to_svg_path
content = content.replace('margin + x * scale', 'offset_x + x * scale')
content = content.replace('margin + y * scale', 'offset_y + y * scale')

# 3. Fix UnboundLocalErrors/Syntax errors found in previous runs:
# e.g. 'fessional_svg' or 'definitionwg'
content = content.replace('definitionwg', 'dwg')
content = content.replace('fessional_svg', 'professional_svg')

# 4. Final check for render_blueprint_professional signature call consistency
# It calls:
# draw_site_context(placement_data, plot_width, plot_height, SCALE, offset_x, offset_y, dwg, building_program)
# Ensure its definition matches.
content = re.sub(r'def draw_site_context\(.*?\):', 
                 'def draw_site_context(placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, dwg, building_program=None):',
                 content, flags=re.DOTALL | re.MULTILINE)

# AND one last check for the shim:
# I'll just manually add shims to the most frequent ones.
list_of_funcs = [
    'render_room_polygons', 'render_room_fills', 'render_walls_with_junctions',
    'render_bathroom_fixtures', 'render_kitchen_counter', 'render_furniture_symbols',
    'render_wall_boundary_polygon', 'render_doors', 'render_windows',
    'render_staircase_symbol', 'render_lift_symbol', 'render_entry_marker',
    'render_room_labels_architectural', 'render_structural_columns'
]

for func in list_of_funcs:
    # Match definition and docstring end
    pattern = rf'def {func}\(.*?offset_x, offset_y, dwg.*?\):\n\s+"""[\s\S]*?"""'
    m = re.search(pattern, content)
    if m:
        content = content[:m.end()] + "\n    margin = offset_x # Legacy shim" + content[m.end():]

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Double Sledgehammer Fix Complete")
