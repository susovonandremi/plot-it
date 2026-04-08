
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

def final_renderer_fix(code):
    # 1. Standardize signatures to always use offset_x, offset_y
    # We'll find all definitions that currently take 'scale, margin, dwg' or 'scale, offset_x, offset_y, dwg'
    # and make sure they match the actual usage.
    
    # First, let's fix the signatures specifically.
    signatures_to_fix = [
        'render_room_polygons', 'render_room_fills', 'render_walls_with_junctions',
        'render_bathroom_fixtures', 'render_kitchen_counter', 'render_furniture_symbols',
        'render_wall_boundary_polygon', 'render_doors', 'render_windows',
        'render_staircase_symbol', 'render_lift_symbol', 'render_entry_marker',
        'render_room_labels_architectural', 'render_structural_columns',
        '_shift_label_clear_of_walls'
    ]
    
    for func in signatures_to_fix:
        # Regex to find 'def func(..., scale, ..., dwg, ...)'
        # We replace the part from 'scale' to 'dwg'
        pattern = rf'def {func}\((.*?)(scale|scale: int),\s*(margin|margin: int|offset_x|offset_x: int),\s*(dwg|offset_y|offset_y: int)(.*?)\)'
        
        # If the function had offset_x already, we might have partials.
        # Let's just be explicit.
        
        # Replacement that ensures (scale, offset_x, offset_y, dwg)
        if func == 'render_structural_columns':
             # Special case for its specific signature
             code = re.sub(rf'def {func}\(columns: list, scale: int, (margin|offset_x): int, dwg\)', 
                           rf'def {func}(columns: list, scale: int, offset_x: int, offset_y: int, dwg)', code)
        
        code = re.sub(
            rf'def {func}\((.*?)scale(:\s*int)?,\s*(margin|offset_x)(:\s*int)?,\s*(dwg|offset_y)(:\s*int)?(.*?)\)',
            rf'def {func}(\1scale\2, offset_x\4, offset_y: int, dwg\7)',
            code
        )

    # 2. Fix the bodies. 
    # Any function that uses 'margin' internally for coordinates must use 'offset_x' or 'offset_y'.
    # We already did some of this, but let's be more thorough.
    
    # Inside the functions we just fixed, we want to replace 'margin +' with 'offset_x +' or 'offset_y +'.
    # A safe way is to just define a local 'margin = offset_x' shim at the top of these functions.
    
    for func in signatures_to_fix:
        # Find the function body start and insert the shim
        # Pattern: def func(...):\n
        pattern = rf'(def {func}\(.*?\):\n\s+"""[\s\S]*?"""|def {func}\(.*?\):\n)'
        search_match = re.search(pattern, code)
        if search_match:
            header = search_match.group(0)
            if 'margin =' not in code[search_match.end():search_match.end()+100]:
                code = code.replace(header, header + "\n    margin = offset_x # Shim for legacy coordinate logic")

    # 3. Final catch-all for any missed 'margin' name errors
    # In '_shift_label_clear_of_walls'
    code = code.replace('lx_ft = (label_x - margin) / scale', 'lx_ft = (label_x - offset_x) / scale')
    code = code.replace('ly_ft = (label_y - label_h - margin) / scale', 'ly_ft = (label_y - label_h - offset_y) / scale')

    return code

new_content = final_renderer_fix(content)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Final Renderer Recovery Complete")
