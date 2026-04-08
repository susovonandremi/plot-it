
import sys

# Try with utf-8 first
try:
    with open('services/professional_svg_renderer.py', 'r', encoding='utf-8') as f:
        content = f.read()
except UnicodeDecodeError:
    # Fallback to latin-1
    with open('services/professional_svg_renderer.py', 'r', encoding='latin-1') as f:
        content = f.read()

# Replace render_title_block signature and body
old_block = """def render_title_block(dwg, canvas_width, canvas_height, margin, plot_width, plot_height, floor_number, vastu_score, building_program=None) -> None:
    \"\"\"Renders the architectural title block/legend at the bottom of the blueprint.\"\"\"
    y_start = canvas_height - 70
    
    # Background
    dwg.add(dwg.rect(
        insert=(margin, y_start), size=(canvas_width - 2*margin, 60),
        fill='#FFFFFF', stroke='#000000', stroke_width=1
    ))
    
    # Title
    floor_names = ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"]
    
    # Check if this is the ROOF 
    # Logic: GF=0, 1F=1. If floors_total=2, then 0 and 1 are residential. 2 is Roof.
    is_roof = False
    if building_program:
        if floor_number >= building_program.floors_total:
             is_roof = True"""

new_block = """def render_title_block(dwg, canvas_width, canvas_height, margin, plot_width, plot_height, floor_number, vastu_score, building_program=None, is_roof=False) -> None:
    \"\"\"Renders the architectural title block/legend at the bottom of the blueprint.\"\"\"
    y_start = canvas_height - 70
    
    # Background
    dwg.add(dwg.rect(
        insert=(margin, y_start), size=(canvas_width - 2*margin, 60),
        fill='#FFFFFF', stroke='#000000', stroke_width=1
    ))
    
    # Title
    floor_names = ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"]
    
    if is_roof:
        title = "ROOF PLAN / TERRACE LEVEL"
    else:
        title = floor_names[floor_number] if floor_number < len(floor_names) else f"FLOOR {floor_number} PLAN\""""

# The above replace might fail because of exact match issues.
# I'll use a more surgical approach.

content = content.replace(
    'def render_title_block(dwg, canvas_width, canvas_height, margin, plot_width, plot_height, floor_number, vastu_score, building_program=None) -> None:',
    'def render_title_block(dwg, canvas_width, canvas_height, margin, plot_width, plot_height, floor_number, vastu_score, building_program=None, is_roof=False) -> None:'
)

# Replace the roof detection logic with simple check
import re
# Find the block of code for floor_names and is_roof detection
pattern = r'# Title\n\s+floor_names = \["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"\]\n\s+\n\s+# Check if this is the ROOF[\s\S]*?if is_roof:\n\s+title = "ROOF PLAN / TERRACE LEVEL"'
replacement = '# Title\n    floor_names = ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"]\n\n    if is_roof:\n        title = "ROOF PLAN / TERRACE LEVEL"'
content = re.sub(pattern, replacement, content)

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully patched render_title_block signature and title logic")
