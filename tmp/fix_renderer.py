# Fix room polygons in professional_svg_renderer.py
import sys

filepath = r'e:\Project\plot-ai\backend\services\professional_svg_renderer.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'def render_room_polygons(' in line:
        new_lines.append(line)
        # Advance till we find the next function or the end of current one's loop
        skip = True
        continue
    
    if skip:
        # We find the next function
        if line.startswith('def _shift_label_clear_of_walls('):
            new_lines.append('\n')
            # Insert the new code!
            new_code = [
                '    """\n',
                '    **Draft Layer 2 — Room dividers** (v2.0).\n',
                '\n',
                '    Draws each room rectangle with a minimal semi-transparent white stroke\n',
                '    and a very subtle dark room fill for consistency.\n',
                '    """\n',
                '    for room in placed_rooms:\n',
                '        x = margin + room[\'x\'] * scale\n',
                '        y = margin + room[\'y\'] * scale\n',
                '        w = room[\'width\'] * scale\n',
                '        h = room[\'height\'] * scale\n',
                '\n',
                '        # Base translucent dark fill (Minimalist UI)\n',
                '        dwg.add(dwg.rect(\n',
                '            insert=(x, y), size=(w, h),\n',
                '            fill="white", opacity=0.03,\n',
                '            stroke="#FFFFFF", stroke_width=1,\n',
                '            stroke_opacity=0.12\n',
                '        ))\n'
            ]
            new_lines.extend(new_code)
            new_lines.append('\n\n')
            new_lines.append(line)
            skip = False
        continue
    
    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Function updated successfully via Python script override.")
