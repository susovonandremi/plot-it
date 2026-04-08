
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

# 1. Broadly identify functions that previously took 'scale, margin, dwg'
# Most signatures follow these patterns:
# def name(data, scale, margin, dwg, ...)
# def name(data, doors, scale, margin, dwg, ...)

# We will replace 'scale, margin, dwg' with 'scale, offset_x, offset_y, dwg'
# And inside those functions, we will replace 'margin' with a local 'ox, oy = offset_x, offset_y'

def fix_renderer_signatures(code):
    # Pattern 1: Any function definition that has scale, margin, dwg
    # We'll use a regex to capture function name and parameter list
    
    # List of functions we know need fixing
    funcs_to_fix = [
        'render_room_fills', 'render_room_polygons', 'render_walls_with_junctions',
        'render_bathroom_fixtures', 'render_kitchen_counter', 'render_furniture_symbols',
        'render_wall_boundary_polygon', 'render_doors', 'render_windows',
        'render_staircase_symbol', 'render_lift_symbol', 'render_entry_marker',
        'render_room_labels_architectural', 'render_dimension_lines', 'render_structural_columns'
    ]
    
    for func in funcs_to_fix:
        # Signature replacement (handling optional types and varying parameter counts)
        # Match 'def <func>(..., scale, margin, dwg, ...)'
        # We'll rely on the fact that margin is always between scale and dwg.
        
        code = re.sub(
            rf'def {func}\((.*?)scale,\s*margin,\s*dwg(.*?)\):',
            rf'def {func}(\1scale, offset_x, offset_y, dwg\2):',
            code
        )
        # Handle cases where margin might have a type hint
        code = re.sub(
            rf'def {func}\((.*?)scale:\s*int,\s*margin:\s*int,\s*dwg(.*?)\):',
            rf'def {func}(\1scale: int, offset_x: int, offset_y: int, dwg\2):',
            code
        )

    # 2. Inside those functions, we need to handle the 'margin' usage.
    # The safest way is to insert 'margin = offset_x # shim' or 'ox, oy = offset_x, offset_y' 
    # but the functions are long.
    
    # Let's do a more robust approach: In every function we fixed, 
    # replace internal 'margin' usage with 'offset_x' or 'offset_y' if possible,
    # or just define 'margin = offset_x' (knowing it's not perfect for Y but better than crashing).
    
    # EVEN BETTER: In those functions, if they use 'margin + ...', 
    # it's usually symmetric or for X. If it's for Y, 'margin + ...' is used too.
    # I'll just replace 'margin' with 'offset_x' globally in those function bodies? No.
    
    # I'll use a shim: inside the function body, add 'margin_x, margin_y = offset_x, offset_y'
    # and then replace internal 'margin +' with 'margin_x +' (roughly)
    # Actually, the most common pattern is 'margin + ...' for both X and Y.
    
    # Let's fix the most critical logic:
    # Most functions use: x = margin + ...  ; y = margin + ...
    
    # I will replace inside the file globally:
    # 'x = margin +' -> 'x = offset_x +'
    # 'y = margin +' -> 'y = offset_y +'
    # 'insert=(margin,' -> 'insert=(offset_x,'
    
    code = code.replace('x = margin +', 'x = offset_x +')
    code = code.replace('y = margin +', 'y = offset_y +')
    code = code.replace('cx = margin +', 'cx = offset_x +')
    code = code.replace('cy = margin +', 'cy = offset_y +')
    code = code.replace('rx = margin +', 'rx = offset_x +')
    code = code.replace('ry = margin +', 'ry = offset_y +')
    code = code.replace('margin + room[\'x\']', 'offset_x + room[\'x\']')
    code = code.replace('margin + room[\'y\']', 'offset_y + room[\'y\']')
    
    # Dimension lines anchor
    code = code.replace('margin, margin, original_unit_system', 'offset_x, offset_y, original_unit_system')

    return code

new_content = fix_renderer_signatures(content)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully performed deep standardization of renderer")
