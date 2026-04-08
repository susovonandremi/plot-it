
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

def absolute_cleanup(code):
    # 1. Manually specify the correct standardized signatures
    correct_sigs = {
        'render_room_polygons': 'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):',
        'render_room_fills': 'def render_room_fills(placed_rooms, scale, offset_x, offset_y, dwg, palette=None):',
        'render_walls_with_junctions': 'def render_walls_with_junctions(wall_segments, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=False):',
        'render_bathroom_fixtures': 'def render_bathroom_fixtures(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):',
        'render_kitchen_counter': 'def render_kitchen_counter(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):',
        'render_furniture_symbols': 'def render_furniture_symbols(items, scale, offset_x, offset_y, dwg, parent_group=None):',
        'render_wall_boundary_polygon': 'def render_wall_boundary_polygon(wall_boundary, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=True):',
        'def render_doors(': 'def render_doors(doors, scale, offset_x, offset_y, dwg):',
        'def render_windows(': 'def render_windows(windows, scale, offset_x, offset_y, dwg):',
        'def render_staircase_symbol(': 'def render_staircase_symbol(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_lift_symbol(': 'def render_lift_symbol(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_entry_marker(': 'def render_entry_marker(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_room_labels_architectural(': 'def render_room_labels_architectural(placed_rooms, scale, offset_x, offset_y, dwg, original_unit_system=None):',
        'def render_dimension_lines(': 'def render_dimension_lines(dwg, placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, original_unit_system=None):',
        'render_structural_columns': 'def render_structural_columns(columns, scale, offset_x, offset_y, dwg):',
        'draw_site_context': 'def draw_site_context(placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, dwg, building_program=None):'
    }

    # 2. Match function name and docstring/body start
    for func_key, correct_sig in correct_sigs.items():
        # func_key can be a name or a signature start
        func_name = func_key.replace('def ', '').split('(')[0] if '(' in func_key else func_key
        
        # Pattern to find 'def <func_name>( ... ) -> ... :\n' followed by optional shims and docstring
        # We replace the whole block until the docstring or first line of code.
        pattern = rf'def {func_name}\s*\(.*?\)\s*(->\s*.*?)?\s*:(.*?)(?=\n\s+(?:"""|\'\'\'|return|if|for|x =|y =))'
        
        replacement = f'{correct_sig}\n    margin = offset_x # Legacy shim\n'
        
        code = re.sub(pattern, replacement, code, flags=re.DOTALL)

    return code

final_code = absolute_cleanup(content)

# Special fix for _polygon_to_svg_path which doesn't follow the pattern
final_code = re.sub(r'def _polygon_to_svg_path\(.*?\)(.*?)offset_x', 
                    r'def _polygon_to_svg_path(poly, scale, offset_x, offset_y)\1offset_x', final_code, flags=re.DOTALL)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Absolute Surgical Cleanup Complete")
