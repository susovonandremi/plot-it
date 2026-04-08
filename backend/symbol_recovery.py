
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

def symbol_recovery(code):
    # 1. Fix draw_door_symbol signature and body
    code = re.sub(r'def draw_door_symbol\(dwg, door_dict, scale, margin\)', 
                  r'def draw_door_symbol(dwg, door_dict, scale, offset_x, offset_y)', code)
    
    # 2. Fix draw_window_symbol signature and body
    code = re.sub(r'def draw_window_symbol\(dwg, win_dict, scale, margin\)', 
                  r'def draw_window_symbol(dwg, win_dict, scale, offset_x, offset_y)', code)
    
    # Actually most of these were already using offset_x internally but missing them in signature.
    # Let's check internal usage:
    # If it uses 'margin + ...' it needs 'offset_x + ...'
    code = code.replace('L {margin + x * scale:.2f},{margin + y * scale:.2f}', 'L {offset_x + x * scale:.2f},{offset_y + y * scale:.2f}')
    
    # 3. Fix the calls inside render_doors and render_windows
    # Pattern: draw_door_symbol(dwg, item, scale, margin) -> (dwg, item, scale, offset_x, offset_y)
    code = code.replace('draw_door_symbol(dwg, d, scale, margin)', 'draw_door_symbol(dwg, d, scale, offset_x, offset_y)')
    code = code.replace('draw_window_symbol(dwg, w, scale, margin)', 'draw_window_symbol(dwg, w, scale, offset_x, offset_y)')

    return code

final_code = symbol_recovery(content)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Symbol Function Recovery Complete")
