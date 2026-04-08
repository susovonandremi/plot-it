
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

# ── List of functions to surgically fix ──────────────────────
# Note: These regex patterns are designed to be extremely robust to previous mangling.
FUNCS = [
    'render_room_fills', 'render_room_polygons', 'render_walls_with_junctions',
    'render_bathroom_fixtures', 'render_kitchen_counter', 'render_furniture_symbols',
    'render_wall_boundary_polygon', 'render_doors', 'render_windows',
    'render_staircase_symbol', 'render_lift_symbol', 'render_entry_marker',
    'render_room_labels_architectural', 'render_dimension_lines', 'render_structural_columns',
    'draw_site_context'
]

def sanitize_signatures(code):
    new_code = code
    for func in FUNCS:
        # Match 'def <func>(' followed by anything until '):' or ') -> None:'
        # We target the parameter block and replace it with a clean one.
        
        if func == 'render_bathroom_fixtures':
            # def render_bathroom_fixtures(placed_rooms: List[Dict], doors: List[Dict], scale, offset_x, offset_y, dwg, parent_group=None)
            pattern = re.compile(rf'def {func}\(.*?\):')
            replacement = f'def {func}(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):'
            new_code = pattern.sub(replacement, new_code, count=1)
            
        elif func == 'render_rooms_clip': # or similar
             pass # Add as needed

        # Generic pattern for others
        pattern = re.compile(rf'def {func}\(.*?scale.*?,.*?,.*?dwg.*?\):')
        # We only apply if it looks mangled or uses 'margin'
        
        # Actually, let's just be explicit for the most important ones to avoid regex greediness issues
    
    # ── Surgical Manual String Replaces for Signatures ─────
    # This is more reliable than regex for complex parameter lists
    
    replacements = {
        'def render_room_polygons(placed_rooms, scale, margin, dwg):': 'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):',
        'def render_room_polygons(placed_rooms: List[Dict], scale: int, margin: int, dwg) -> None:': 'def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg):',
        'def render_walls_with_junctions(wall_segments: dict, scale: int, margin: int, dwg,': 'def render_walls_with_junctions(wall_segments, scale, offset_x, offset_y, dwg,',
        'def render_doors(doors, scale, margin, dwg):': 'def render_doors(doors, scale, offset_x, offset_y, dwg):',
        'def render_windows(windows, scale, margin, dwg):': 'def render_windows(windows, scale, offset_x, offset_y, dwg):',
        'def render_staircase_symbol(placement_data, scale, margin, dwg):': 'def render_staircase_symbol(placement_data, scale, offset_x, offset_y, dwg):',
        'def render_room_labels_architectural(placed_rooms, scale, margin, dwg,': 'def render_room_labels_architectural(placed_rooms, scale, offset_x, offset_y, dwg,',
        'def render_structural_columns(columns: list, scale: int, margin: int, dwg) -> None:': 'def render_structural_columns(columns, scale, offset_x, offset_y, dwg):',
    }
    
    for old, new in replacements.items():
        new_code = new_code.replace(old, new)

    # ── Add the Shims ──────────────────────────────────────────
    # We want to insert 'margin = offset_x' after every standardized signature
    for func in FUNCS:
        pattern = rf'def {func}\(.*?offset_x, offset_y, dwg.*?\):\n'
        match = re.search(pattern, new_code)
        if match:
            insertion_point = match.end()
            # Find the start of the next line (handle docstrings)
            # If the next line is a docstring, we insert after it.
            doc_pattern = re.compile(r'\s+"""[\s\S]*?"""')
            doc_match = doc_pattern.match(new_code, insertion_point)
            if doc_match:
                insertion_point = doc_match.end()
            
            # Check if shim already exists
            if 'margin = offset_x' not in new_code[insertion_point:insertion_point+100]:
                 new_code = new_code[:insertion_point] + "\n    margin = offset_x # Legacy shim" + new_code[insertion_point:]

    return new_code

final_code = sanitize_signatures(content)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Surgical Signature Restoration & Shim Injection Complete")
