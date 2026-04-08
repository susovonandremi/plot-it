
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

def inject_global_shims(code):
    lines = code.split('\n')
    new_lines = []
    
    # Track which functions we've seen
    current_func = None
    
    for line in lines:
        new_lines.append(line)
        if line.strip().startswith('def '):
            # Check if it has offset_x
            if 'offset_x' in line:
                 indent = line[:line.find('def ')] + '    '
                 new_lines.append(f"{indent}margin = offset_x # Mandatory Legacy shim")

    return '\n'.join(new_lines)

final_code = inject_global_shims(content)

# Clean up any potential double-shims
final_code = final_code.replace('margin = offset_x # Legacy shim\n    margin = offset_x # Mandatory Legacy shim', 'margin = offset_x # Legacy shim')

with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(final_code)

print("Global Shim Injection Complete")
