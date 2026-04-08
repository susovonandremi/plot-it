import logging
"""
SVG Renderer Service
Professional-grade SVG blueprint renderer.
Generates architectural blueprints with all standard elements.
"""

import svgwrite
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def render_blueprint(
    placement_data: List[Dict[str, Any]], 
    plot_width: float, 
    plot_height: float, 
    vastu_score: Dict[str, Any], 
    user_tier: str = "free",
    original_unit_system: Optional[Dict[str, Any]] = None,
    heavy_elements: Optional[List[Dict[str, Any]]] = None 
) -> str:
    """
    Renders a professional-grade architectural blueprint as SVG.
    
    Includes all standard architectural elements:
    - Plot boundary
    - Vastu zones (3×3 grid overlay)
    - Room rectangles with fills
    - Room labels and dimensions
    - Doors (arcs)
    - Windows (triple lines)
    - Compass rose
    - Scale bar
    - Vastu score badge
    - Watermark (free tier)
    """
    
    # ═══════════════════════════════════════════════════════════
    # CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    
    SCALE = 10  # 10 pixels per foot for rendering
    MARGIN = 50  # Margin around blueprint for labels/compass/etc.
    
    canvas_width = int(plot_width * SCALE) + (MARGIN * 2)
    canvas_height = int(plot_height * SCALE) + (MARGIN * 2)
    
    # Room fill colors (pastel, professional)
    ROOM_COLORS = {
        'bedroom': '#E8F4FD',    # Light blue
        'bathroom': '#E8F8F5',   # Light cyan
        'kitchen': '#FEF9E7',    # Light yellow
        'dining': '#FEF5E4',     # Light peach
        'living': '#F9EBEA',     # Light pink
        'pooja': '#EAF2FF',      # Light lavender
        'study': '#E8F5E9',      # Light green
        'garage': '#F5F5F5',     # Light gray
        'other': '#F2F3F4'       # Neutral gray
    }
    
    # ═══════════════════════════════════════════════════════════
    # CREATE SVG CANVAS
    # ═══════════════════════════════════════════════════════════
    
    dwg = svgwrite.Drawing(size=(f"{canvas_width}px", f"{canvas_height}px"))
    
    # Add CSS for fonts
    dwg.defs.add(dwg.style("""
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400&display=swap');
    """))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 1: PLOT BOUNDARY
    # ═══════════════════════════════════════════════════════════
    
    dwg.add(dwg.rect(
        insert=(MARGIN, MARGIN),
        size=(plot_width * SCALE, plot_height * SCALE),
        fill="white",
        stroke="#1E293B",  # Slate-900
        stroke_width=4
    ))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 2: VASTU ZONES (3×3 GRID) — SUBTLE OVERLAY
    # ═══════════════════════════════════════════════════════════
    
    zone_width = (plot_width * SCALE) / 3
    zone_height = (plot_height * SCALE) / 3
    
    zones = [
        ['NW', 'N', 'NE'],
        ['W',  'C', 'E'],
        ['SW', 'S', 'SE']
    ]
    
    for row_idx, row in enumerate(zones):
        for col_idx, zone in enumerate(row):
            x = MARGIN + (col_idx * zone_width)
            y = MARGIN + (row_idx * zone_height)
            
            # Subtle dashed zone outline
            dwg.add(dwg.rect(
                insert=(x, y),
                size=(zone_width, zone_height),
                fill="none",
                stroke="#CBD5E1",  # Slate-300
                stroke_width=1,
                stroke_dasharray="5,5",
                opacity=0.3
            ))
            
            # Tiny zone label in corner
            dwg.add(dwg.text(
                zone,
                insert=(x + 8, y + 18),
                font_size="11px",
                font_family="JetBrains Mono, monospace",
                fill="#94A3B8",  # Slate-400
                opacity=0.5,
                font_weight="400"
            ))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 3: ROOM RECTANGLES WITH FILLS
    # ═══════════════════════════════════════════════════════════
    
    for room in placement_data:
        x = MARGIN + (room['x'] * SCALE)
        y = MARGIN + (room['y'] * SCALE)
        w = room['width'] * SCALE
        h = room['height'] * SCALE
        
        fill_color = ROOM_COLORS.get(room['type'], '#F2F3F4')
        
        # Room rectangle (Fill only, stroke replaced by solid wall shapes)
        dwg.add(dwg.rect(
            insert=(x, y),
            size=(w, h),
            fill=fill_color,
            stroke="none"
        ))
        
        # Draw bathroom fixtures (toilet, sink, shower) before walls
        if room['type'] in ('BATHROOM', 'bathroom'):
            draw_bathroom_fixtures(room, SCALE, MARGIN, dwg)
        
        # Room name (formatted nicely)
        room_name = room['id'].replace('_', ' ').title()
        # Clean up names for display
        parts = room['id'].split('_')
        base_type = parts[0]
        if base_type == 'bedroom':
            if len(parts) > 1 and parts[1] == '0':
                 room_name = "Master Bedroom"
            else:
                 room_name = f"Bedroom {int(parts[1])+1}" if len(parts)>1 else "Bedroom"
        elif base_type == 'bathroom':
             room_name = "Bath"
        elif base_type == 'kitchen':
             room_name = "Kitchen"
        elif base_type == 'living':
             room_name = "Living Hall"
        elif base_type == 'dining':
             room_name = "Dining"
        
        # Room label (centered, bold)
        dwg.add(dwg.text(
            room_name,
            insert=(x + w/2, y + h/2 - 8),
            text_anchor="middle",
            font_size="14px",
            font_family="Archivo, sans-serif",
            font_weight="600",
            fill="#1E293B"  # Slate-900
        ))
        
        # Dimensions (below room name)
        dims = f"{room['width']:.1f}' × {room['height']:.1f}'"
        dwg.add(dwg.text(
            dims,
            insert=(x + w/2, y + h/2 + 10),
            text_anchor="middle",
            font_size="11px",
            font_family="JetBrains Mono, monospace",
            fill="#64748B",  # Slate-500
            font_weight="400"
        ))
    
    # Render Walls as Solids (Thick black lines)
    # This must be done AFTER fills to ensure walls are on top
    render_walls_as_solids(placement_data, SCALE, MARGIN, dwg)
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 4: DOORS (Intelligent Placement)
    # ═══════════════════════════════════════════════════════════
    
    hallways = [r for r in placement_data if r.get('is_circulation') or r['type'] == 'HALLWAY']
    rooms_with_doors = set()
    
    for room in placement_data:
        # Skip hallways/staircases for door placement target
        if  room.get('is_circulation') or room.get('is_entrance') or room['type'] in ['HALLWAY', 'STAIRCASE']: continue
        
        rx = room['x']
        ry = room['y']
        rw = room['width']
        rh = room['height']
        
        rx_px = MARGIN + (rx * SCALE)
        ry_px = MARGIN + (ry * SCALE)
        rw_px = rw * SCALE
        rh_px = rh * SCALE
        
        door_drawn = False
        
        # 1. Check Adjacency with Hallways
        for hw in hallways:
            hx, hy, h_w, h_h = hw['x'], hw['y'], hw['width'], hw['height']
            
            # Tolerance for touching
            tol = 1.0 
            door_rect = None
            door_drawn = False
            
            # Check Right of Hallway (Left of Room)
            if abs(rx - (hx + h_w)) < tol and (max(ry, hy) < min(ry+rh, hy+h_h)):
                # Door on Left side of Room (Right side of Hallway)
                door_x = hx + h_w
                door_y = ry + rh/2 - 1.5
                door_rect = (door_x, door_y, 0.5, 3)
                door_drawn = True

            # Check Left of Hallway (Right of Room)
            elif abs((rx + rw) - hx) < tol and (max(ry, hy) < min(ry+rh, hy+h_h)):
                # Door on Right side of Room (Left side of Hallway)
                door_x = hx - 0.5
                door_y = ry + rh/2 - 1.5
                door_rect = (door_x, door_y, 0.5, 3)
                door_drawn = True

            # Check Bottom of Hallway (Top of Room)
            elif abs(ry - (hy + h_h)) < tol and (max(rx, hx) < min(rx+rw, hx+h_w)):
                # Door on Top side of Room
                door_x = rx + rw/2 - 1.5
                door_y = hy + h_h
                door_rect = (door_x, door_y, 3, 0.5)
                door_drawn = True

            # Check Top of Hallway (Bottom of Room)
            elif abs((ry + rh) - hy) < tol and (max(rx, hx) < min(rx+rw, hx+h_w)):
                # Door on Bottom side of Room
                door_x = rx + rw/2 - 1.5
                door_y = hy - 0.5
                door_rect = (door_x, door_y, 3, 0.5)
                door_drawn = True
            
            if door_drawn and door_rect:
                dx, dy, dw, dh = door_rect
                dwg.add(dwg.rect(
                    insert=(MARGIN + dx * SCALE, MARGIN + dy * SCALE),
                    size=(dw * SCALE, dh * SCALE),
                    fill="white",
                    stroke="#0EA5E9",
                    stroke_width=2
                ))
                # 'D' Label
                dwg.add(dwg.text("D", 
                    insert=(MARGIN + dx * SCALE + (dw*SCALE/2) - 3, MARGIN + dy * SCALE + (dh*SCALE/2) + 3),
                    font_size="8px", font_family="JetBrains Mono", fill="#0EA5E9"))
                rooms_with_doors.add(room['id'])
                break 

        # 2. If no hallway door, AND it's a Living Room/Entrance, add Main Entrance
        if not door_drawn and room['type'] in ['LIVING', 'ENTRANCE', 'FOYER']:
             # Draw distinct main door on the 'front' (assume bottom for now or nearest plot edge)
             # Default to bottom center of room
             cx = rx_px + rw_px/2
             cy = ry_px + rh_px
             dwg.add(dwg.line(start=(cx-20, cy), end=(cx+20, cy), stroke="#0EA5E9", stroke_width=5)) # Thicker main door
             dwg.add(dwg.path(d=f"M {cx-20},{cy} Q {cx},{cy-20} {cx+20},{cy}", stroke="#0EA5E9", stroke_width=2, fill="none"))

    # ═══════════════════════════════════════════════════════════
    # LAYER 5: WINDOWS (Exterior Walls)
    # ═══════════════════════════════════════════════════════════
    
    for room in placement_data:
        if room['type'] in ['BEDROOM', 'LIVING', 'DINING', 'KITCHEN', 'MASTER_BEDROOM', 'STUDY']:
            rx, ry, rw, rh = room['x'], room['y'], room['width'], room['height']
            
            rx_px = MARGIN + (rx * SCALE)
            ry_px = MARGIN + (ry * SCALE)
            rw_px = rw * SCALE
            rh_px = rh * SCALE
            
            # Check against Plot Boundaries (coordinates 0, 0, plot_width, plot_height)
            tol = 0.5
            
            # Top Wall (ry near 0)
            if abs(ry) < tol:
                 # Draw Window
                 start = (rx_px + rw_px*0.25, ry_px)
                 end = (rx_px + rw_px*0.75, ry_px)
                 # Triple line
                 for off in [-2, 0, 2]:
                     dwg.add(dwg.line(start=(start[0], start[1]+off), end=(end[0], end[1]+off), stroke="#475569", stroke_width=2))
            
            # Bottom Wall (ry + rh near plot_height)
            if abs((ry + rh) - plot_height) < tol:
                 start = (rx_px + rw_px*0.25, ry_px + rh_px)
                 end = (rx_px + rw_px*0.75, ry_px + rh_px)
                 for off in [-2, 0, 2]:
                     dwg.add(dwg.line(start=(start[0], start[1]+off), end=(end[0], end[1]+off), stroke="#475569", stroke_width=2))

            # Left Wall (rx near 0)
            if abs(rx) < tol:
                 start = (rx_px, ry_px + rh_px*0.25)
                 end = (rx_px, ry_px + rh_px*0.75)
                 for off in [-2, 0, 2]:
                     dwg.add(dwg.line(start=(start[0]+off, start[1]), end=(end[0]+off, end[1]), stroke="#475569", stroke_width=2))

            # Right Wall (rx + rw near plot_width)
            if abs((rx + rw) - plot_width) < tol:
                 start = (rx_px + rw_px, ry_px + rh_px*0.25)
                 end = (rx_px + rw_px, ry_px + rh_px*0.75)
                 for off in [-2, 0, 2]:
                     dwg.add(dwg.line(start=(start[0]+off, start[1]), end=(end[0]+off, end[1]), stroke="#475569", stroke_width=2))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 6: COMPASS ROSE (Top-right corner)
    # ═══════════════════════════════════════════════════════════
    
    compass_x = canvas_width - 60
    compass_y = 50
    
    # Outer circle
    dwg.add(dwg.circle(
        center=(compass_x, compass_y),
        r=28,
        fill="white",
        stroke="#1E293B",
        stroke_width=2.5
    ))
    
    # Inner decorative circle
    dwg.add(dwg.circle(
        center=(compass_x, compass_y),
        r=22,
        fill="none",
        stroke="#CBD5E1",
        stroke_width=1
    ))
    
    # North arrow (pointing up)
    dwg.add(dwg.polygon(
        points=[
            (compass_x, compass_y - 18),      # Top point
            (compass_x - 6, compass_y + 2),   # Left base
            (compass_x + 6, compass_y + 2)    # Right base
        ],
        fill="#DC2626",  # Red-600
        stroke="#1E293B",
        stroke_width=1.5
    ))
    
    # South indicator (opposite side, darker)
    dwg.add(dwg.polygon(
        points=[
            (compass_x, compass_y + 18),      # Bottom point
            (compass_x - 6, compass_y - 2),   # Left base
            (compass_x + 6, compass_y - 2)    # Right base
        ],
        fill="#64748B",  # Slate-500
        stroke="#1E293B",
        stroke_width=1.5
    ))
    
    # Cardinal direction labels
    dwg.add(dwg.text(
        "N",
        insert=(compass_x, compass_y - 35),
        text_anchor="middle",
        font_size="13px",
        font_family="Archivo, sans-serif",
        font_weight="700",
        fill="#DC2626"
    ))
    
    dwg.add(dwg.text(
        "S",
        insert=(compass_x, compass_y + 42),
        text_anchor="middle",
        font_size="10px",
        font_family="Archivo, sans-serif",
        font_weight="600",
        fill="#64748B"
    ))
    
    dwg.add(dwg.text(
        "E",
        insert=(compass_x + 35, compass_y + 5),
        text_anchor="middle",
        font_size="10px",
        font_family="Archivo, sans-serif",
        font_weight="600",
        fill="#64748B"
    ))
    
    dwg.add(dwg.text(
        "W",
        insert=(compass_x - 35, compass_y + 5),
        text_anchor="middle",
        font_size="10px",
        font_family="Archivo, sans-serif",
        font_weight="600",
        fill="#64748B"
    ))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 7: SCALE BAR (Bottom-left)
    # ═══════════════════════════════════════════════════════════
    
    scale_x = MARGIN
    scale_y = canvas_height - 35
    scale_length = 10 * SCALE  # 10 feet reference
    
    # Main scale line
    dwg.add(dwg.line(
        start=(scale_x, scale_y),
        end=(scale_x + scale_length, scale_y),
        stroke="#1E293B",
        stroke_width=3
    ))
    
    # Tick marks at 0, 5, 10 feet
    for i in [0, 5, 10]:
        tick_x = scale_x + (i * SCALE)
        dwg.add(dwg.line(
            start=(tick_x, scale_y - 6),
            end=(tick_x, scale_y + 6),
            stroke="#1E293B",
            stroke_width=2
        ))
    
    # Scale labels
    dwg.add(dwg.text(
        "0",
        insert=(scale_x, scale_y + 22),
        text_anchor="middle",
        font_size="11px",
        font_family="JetBrains Mono, monospace",
        fill="#64748B"
    ))
    
    dwg.add(dwg.text(
        "5'",
        insert=(scale_x + 5 * SCALE, scale_y + 22),
        text_anchor="middle",
        font_size="11px",
        font_family="JetBrains Mono, monospace",
        fill="#64748B"
    ))
    
    dwg.add(dwg.text(
        "10'",
        insert=(scale_x + scale_length, scale_y + 22),
        text_anchor="middle",
        font_size="11px",
        font_family="JetBrains Mono, monospace",
        fill="#64748B"
    ))
    
    # Scale label
    dwg.add(dwg.text(
        "SCALE",
        insert=(scale_x + scale_length/2, scale_y - 15),
        text_anchor="middle",
        font_size="9px",
        font_family="Archivo, sans-serif",
        font_weight="600",
        fill="#94A3B8",
        letter_spacing="1px"
    ))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 8: VASTU SCORE BADGE (Top-left)
    # ═══════════════════════════════════════════════════════════
    
    badge_x = MARGIN
    badge_y = 25
    
    # Badge colors
    badge_color_map = {
        'green': '#16A34A',   # Green-600
        'yellow': '#CA8A04',  # Yellow-600
        'orange': '#EA580C',  # Orange-600
        'red': '#DC2626'      # Red-600
    }
    
    badge_color = badge_color_map.get(vastu_score.get('color', 'green'), '#64748B')
    
    # Badge background (rounded rectangle)
    dwg.add(dwg.rect(
        insert=(badge_x, badge_y),
        size=(200, 35),
        rx=8,
        ry=8,
        fill=badge_color,
        opacity=0.95
    ))
    
    # Badge text
    badge_text = f"Vastu: {vastu_score.get('score', 0)}% • {vastu_score.get('label', 'Unknown')}"
    dwg.add(dwg.text(
        badge_text,
        insert=(badge_x + 100, badge_y + 23),
        text_anchor="middle",
        font_size="13px",
        font_family="Archivo, sans-serif",
        font_weight="600",
        fill="white"
    ))
    
    # ═══════════════════════════════════════════════════════════
    # LAYER 9: WATERMARK (Bottom-right) — FREE TIER ONLY
    # ═══════════════════════════════════════════════════════════
    
    if user_tier == "free":
        watermark_text = "PlotAI.com · Free Plan"
        watermark_x = canvas_width - 165
        watermark_y = canvas_height - 25
        
        # Semi-transparent background
        dwg.add(dwg.rect(
            insert=(watermark_x - 8, watermark_y - 18),
            size=(160, 24),
            rx=5,
            ry=5,
            fill="white",
            opacity=0.85
        ))
        
        # Watermark text
        dwg.add(dwg.text(
            watermark_text,
            insert=(watermark_x, watermark_y),
            font_size="12px",
            font_family="Inter, sans-serif",
            font_weight="500",
            fill="#64748B"
        ))
    
    # ═══════════════════════════════════════════════════════════
    # RETURN COMPLETE SVG
    # ═══════════════════════════════════════════════════════════
    
    return dwg.tostring()


def render_walls_as_solids(placement_data: list, scale: int, margin: int, dwg) -> None:
    """
    Renders room walls as thick solid black rectangles (not strokes).
    
    This is the KEY difference between amateur and professional blueprints.
    Walls are SOLID SHAPES, not just borders around rooms.
    
    Args:
        placement_data: Placed rooms
        scale: Pixels per foot
        margin: Canvas margin
        dwg: SVG drawing object
    """
    
    WALL_THICKNESS = 0.5  # 6 inches = 0.5 feet (standard wall thickness)
    WALL_COLOR = "#000000"  # Pure black
    
    # Track all wall segments to avoid drawing same wall twice
    horizontal_walls = []
    vertical_walls = []
    
    for room in placement_data:
        # Note: Hallways also have walls in professional plans, but thinner?
        # For now, apply same thickness to all for consistency
        
        x = room['x']
        y = room['y']
        w = room['width']
        h = room['height']
        
        # Top wall
        horizontal_walls.append({
            'x1': x,
            'y1': y,
            'x2': x + w,
            'y2': y,
            'thickness': WALL_THICKNESS
        })
        
        # Bottom wall
        horizontal_walls.append({
            'x1': x,
            'y1': y + h,
            'x2': x + w,
            'y2': y + h,
            'thickness': WALL_THICKNESS
        })
        
        # Left wall
        vertical_walls.append({
            'x1': x,
            'y1': y,
            'x2': x,
            'y2': y + h,
            'thickness': WALL_THICKNESS
        })
        
        # Right wall
        vertical_walls.append({
            'x1': x + w,
            'y1': y,
            'x2': x + w,
            'y2': y + h,
            'thickness': WALL_THICKNESS
        })
    
    # Merge overlapping walls (where rooms share a wall)
    # This prevents double-thick walls between adjacent rooms
    horizontal_walls = merge_overlapping_walls(horizontal_walls, axis='horizontal')
    vertical_walls = merge_overlapping_walls(vertical_walls, axis='vertical')
    
    # Draw horizontal walls as rectangles
    for wall in horizontal_walls:
        wall_x = margin + (wall['x1'] * scale)
        wall_y = margin + (wall['y1'] * scale) - (wall['thickness']/2 * scale)
        wall_width = (wall['x2'] - wall['x1']) * scale
        wall_height = wall['thickness'] * scale
        
        dwg.add(dwg.rect(
            insert=(wall_x, wall_y),
            size=(wall_width, wall_height),
            fill=WALL_COLOR,
            stroke="none"
        ))
    
    # Draw vertical walls as rectangles
    for wall in vertical_walls:
        wall_x = margin + (wall['x1'] * scale) - (wall['thickness']/2 * scale)
        wall_y = margin + (wall['y1'] * scale)
        wall_width = wall['thickness'] * scale
        wall_height = (wall['y2'] - wall['y1']) * scale
        
        dwg.add(dwg.rect(
            insert=(wall_x, wall_y),
            size=(wall_width, wall_height),
            fill=WALL_COLOR,
            stroke="none"
        ))


def merge_overlapping_walls(walls: list, axis: str) -> list:
    """
    Merges walls that overlap (shared walls between rooms).
    Prevents drawing the same wall twice.
    """
    if not walls:
        return []
        
    merged = []
    used = set()
    
    # Sort walls to make merging easier
    if axis == 'horizontal':
        # Sort by Y then X1
        sorted_walls = sorted(walls, key=lambda w: (w['y1'], w['x1']))
    else:
        # Sort by X then Y1
        sorted_walls = sorted(walls, key=lambda w: (w['x1'], w['y1']))
    
    for i, wall1 in enumerate(sorted_walls):
        if i in used:
            continue
        
        current_wall = dict(wall1)
        
        # Check if any subsequent walls overlap this one
        for j, wall2 in enumerate(sorted_walls[i+1:], start=i+1):
            if j in used:
                continue
            
            if axis == 'horizontal':
                if abs(current_wall['y1'] - wall2['y1']) < 0.1:  # Same line
                    # Check if they overlap or are adjacent
                    if wall2['x1'] <= current_wall['x2'] + 0.1:
                        current_wall['x2'] = max(current_wall['x2'], wall2['x2'])
                        used.add(j + i) # j is relative index if start=i+1? No, start Fixes this.
                        # Wait, j is absolute index because of start=i+1.
                        used.add(j)
                    else:
                        break # Sorted, so no more overlaps possible on this line
                else:
                    break # Next line
            else: # vertical
                if abs(current_wall['x1'] - wall2['x1']) < 0.1:  # Same line
                    if wall2['y1'] <= current_wall['y2'] + 0.1:
                        current_wall['y2'] = max(current_wall['y2'], wall2['y2'])
                        used.add(j)
                    else:
                        break
                else:
                    break
        
        merged.append(current_wall)
    
    return merged


def draw_bathroom_fixtures(room: dict, scale: int, margin: int, dwg) -> None:
    """
    Draws toilet, sink, and shower symbols inside bathroom.
    
    Standard Indian bathroom layout:
    - Toilet (WC) in one corner
    - Sink (wash basin) on opposite wall
    - Shower area (if space allows)
    """
    
    x = margin + (room['x'] * scale)
    y = margin + (room['y'] * scale)
    w = room['width'] * scale
    h = room['height'] * scale
    
    # TOILET SYMBOL (rectangular shape)
    toilet_width = 1.5 * scale   # 1.5 feet
    toilet_height = 2.0 * scale  # 2 feet
    
    # Position toilet in back-left corner
    toilet_x = x + (0.5 * scale)
    toilet_y = y + (0.5 * scale)
    
    # Toilet bowl (rectangle with rounded top)
    dwg.add(dwg.rect(
        insert=(toilet_x, toilet_y),
        size=(toilet_width, toilet_height),
        fill="white",
        stroke="#000000",
        stroke_width=1.5,
        rx=toilet_width/2,
        ry=toilet_width/2
    ))
    
    # Toilet tank (smaller rectangle behind bowl)
    dwg.add(dwg.rect(
        insert=(toilet_x + toilet_width*0.2, toilet_y - 0.8*scale),
        size=(toilet_width*0.6, 0.8*scale),
        fill="white",
        stroke="#000000",
        stroke_width=1.5
    ))
    
    # SINK SYMBOL (oval shape)
    sink_width = 1.5 * scale
    sink_height = 1.0 * scale
    
    # Position sink on right wall
    sink_x = x + w - (2 * scale)
    sink_y = y + h - (2 * scale)
    
    # Sink basin (ellipse)
    dwg.add(dwg.ellipse(
        center=(sink_x, sink_y),
        r=(sink_width/2, sink_height/2),
        fill="white",
        stroke="#000000",
        stroke_width=1.5
    ))
    
    # Tap/faucet (small circle)
    dwg.add(dwg.circle(
        center=(sink_x, sink_y - sink_height*0.7),
        r=0.2*scale,
        fill="#64748B",
        stroke="#000000",
        stroke_width=1
    ))
    
    # Optional: Shower area (if bathroom is large enough, > 36 sqft)
    if room['width'] > 6 and room['height'] > 6:
        # Shower corner (square outline)
        shower_size = 2.5 * scale
        shower_x = x + (0.5 * scale)
        shower_y = y + h - shower_size - (0.5 * scale)
        
        dwg.add(dwg.rect(
            insert=(shower_x, shower_y),
            size=(shower_size, shower_size),
            fill="none",
            stroke="#64748B",
            stroke_width=1.5,
            stroke_dasharray="3,3"
        ))
        
        # Shower head symbol
        dwg.add(dwg.circle(
            center=(shower_x + shower_size/2, shower_y + 0.3*scale),
            r=0.3*scale,
            fill="#64748B"
        ))