
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

# Remove the broken shims
content = content.replace('    margin = offset_x # Mandatory Legacy shim', '')
# Remove any accidental variants
content = content.replace('    margin = offset_x # Legacy shim', '')

def inject_safely(code):
    # This pattern find function definitions and captures the signature and the colon
    # Then we replace the signature with signature + shim inserted after the next newline with indentation.
    
    # We'll do it more simply:
    # Find every function that takes offset_x and add 'margin = offset_x' as the FIRST line of the body.
    
    lines = code.split('\n')
    new_lines = []
    
    for i in range(len(lines)):
        line = lines[i]
        new_lines.append(line)
        if line.startswith('def ') and 'offset_x' in line:
            # Look ahead for the colon
            target_i = i
            while ':' not in lines[target_i]:
                target_i += 1
            
            # Now target_i is the line with the colon. 
            # We want to insert AFTER this line (or it might be a multi-line def)
            # Actually, let's just use a state machine.
            pass

    # Actually, the simplest way is to manually fix the 2-3 functions that actually use 'margin'
    # and were missing 'offset_x' or forgot the shim.
    return code

# Just clean up for now
with open('services/professional_svg_renderer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Cleanup of broken shims complete")
