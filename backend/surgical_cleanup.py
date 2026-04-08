
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

def cleanup_corrupted_file(code):
    # 1. Fix the duplicate/mangled dwg arguments
    # Look for patterns like: offset_y, dwg: int, dwg
    code = re.sub(r'offset_y,\s*dwg:\s*int,\s*dwg', 'offset_x, offset_y, dwg', code)
    code = re.sub(r'offset_x,\s*offset_y,\s*dwg:\s*int,\s*dwg', 'offset_x, offset_y, dwg', code)
    
    # Let's just fix the signatures the old fashioned way - find and replace the whole line.
    
    # 2. Define the correct signatures
    sig_map = {
        'def render_room_polygons(': 'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):',
        'def render_room_fills(': 'def render_room_fills(placed_rooms, scale, offset_x, offset_y, dwg, palette=None):',
        'def render_walls_with_junctions(': 'def render_walls_with_junctions(wall_segments, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=False):',
        'def render_bathroom_fixtures(': 'def render_bathroom_fixtures(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):',
        'def render_kitchen_counter(': 'def render_kitchen_counter(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):',
        'def render_furniture_symbols(': 'def render_furniture_symbols(items, scale, offset_x, offset_y, dwg, parent_group=None):',
        'def render_wall_boundary_polygon(': 'def render_wall_boundary_polygon(wall_boundary, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=True):',
        'def render_doors(': 'def render_doors(doors, scale, offset_x, offset_y, dwg):',
        'def render_windows(': 'def render_windows(windows, scale, offset_x, offset_y, dwg):',
        'def render_staircase_symbol(': 'def render_staircase_symbol(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_lift_symbol(': 'def render_lift_symbol(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_entry_marker(': 'def render_entry_marker(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_room_labels_architectural(': 'def render_room_labels_architectural(placed_rooms, scale, offset_x, offset_y, dwg, original_unit_system=None):',
        'def render_dimension_lines(': 'def render_dimension_lines(dwg, placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, original_unit_system=None):',
        'def render_structural_columns(': 'def render_structural_columns(columns, scale, offset_x, offset_y, dwg):',
        'def draw_site_context(': 'def draw_site_context(placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, dwg, building_program=None):'
    }

    lines = code.split('\n')
    new_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
            
        stripped = line.strip()
        replaced = False
        for prefix, correct_sig in sig_map.items():
            if stripped.startswith(prefix):
                indent = line[:line.find('def ')]
                new_lines.append(f"{indent}{correct_sig}")
                # If the original line didn't end with a colon (multi-line), we skip until colon
                curr_line = line
                while i < len(lines) - 1 and ':' not in curr_line:
                     i += 1
                     curr_line = lines[i]
                     skip_next = True # Not really skip, but we advance i
                
                # Add legacy shim
                new_lines.append(f"{indent}    margin = offset_x # Legacy shim")
                replaced = True
                break
        
        if not replaced:
            new_lines.append(line)

    return '\n'.join(new_lines)

# Run cleanup twice to handle nested messes
final_code = cleanup_corrupted_file(content)
final_code = cleanup_corrupted_file(final_code)

# One more fix: _polygon_to_svg_path
final_code = final_code.replace('margin + x * scale', 'offset_x + x * scale')
final_code = final_code.replace('margin + y * scale', 'offset_y + y * scale')

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Final Surgical Cleanup Complete")
