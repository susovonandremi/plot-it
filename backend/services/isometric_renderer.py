"""
Isometric 3D Renderer — 2.5D SVG Extrusion
=============================================
Projects 2D room layouts into a 30° isometric view.

Each room is extruded as:
  1. Floor plane (projected parallelogram)
  2. Two visible side walls (right + bottom faces)
  3. Top edge lines
  4. Window/door indicators on walls

The output is a second SVG string that can be displayed alongside the plan view.
"""
import logging

import math
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── ISOMETRIC PROJECTION ─────────────────────────────────────────────────────

# Isometric angles (30°)
ISO_ANGLE = math.radians(30)
COS_A = math.cos(ISO_ANGLE)
SIN_A = math.sin(ISO_ANGLE)

# Wall height in feet for different building types
WALL_HEIGHTS = {
    "residential": 10,
    "traditional": 12,
    "modern": 10,
    "villa": 11,
    "apartment": 9,
}

# Room colors (slightly darker than plan view for depth)
ISO_ROOM_COLORS = {
    'bedroom':        ('#C8D8E8', '#A8B8C8', '#E0ECFA'),
    'master_bedroom': ('#C8D8E8', '#A8B8C8', '#E0ECFA'),
    'bathroom':       ('#C8E8E0', '#A8C8C0', '#E0F5EE'),
    'kitchen':        ('#E8E0C8', '#C8C0A8', '#FAF0DD'),
    'dining':         ('#E8D8C0', '#C8B8A0', '#FFF0DD'),
    'living':         ('#E0C8C0', '#C0A8A0', '#F5DDD5'),
    'pooja':          ('#D0D8F0', '#B0B8D0', '#E8F0FF'),
    'study':          ('#C8E0C8', '#A8C0A8', '#E0F5E0'),
    'foyer':          ('#E8E0D0', '#C8C0B0', '#FFF5E8'),
    'verandah':       ('#D0E8D0', '#B0C8B0', '#E8FFE8'),
}

DEFAULT_COLORS = ('#D8D8D8', '#B8B8B8', '#F0F0F0')


def iso_project(x: float, y: float, z: float = 0, scale: float = 8) -> Tuple[float, float]:
    """
    Project 3D coordinates (x, y, z) to 2D isometric screen coordinates.
    x = east, y = south (into screen), z = up
    """
    sx = (x - y) * COS_A * scale
    sy = (x + y) * SIN_A * scale - z * scale
    return (sx, sy)


def render_isometric(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    wall_height: float = 10,
    style: str = "residential",
) -> str:
    """
    Renders an isometric 3D view of the floor plan as SVG.

    Args:
        placed_rooms: List of placed room dicts
        plot_width: Plot width in feet
        plot_height: Plot height in feet
        wall_height: Wall height in feet
        style: Building style (affects wall height)

    Returns:
        SVG string
    """
    import svgwrite

    wh = WALL_HEIGHTS.get(style, wall_height)
    SCALE = 6

    # Canvas sizing
    max_x = plot_width + 5
    max_y = plot_height + 5

    # Project corners to find canvas bounds
    corners = [
        iso_project(0, 0, 0, SCALE),
        iso_project(max_x, 0, 0, SCALE),
        iso_project(0, max_y, 0, SCALE),
        iso_project(max_x, max_y, 0, SCALE),
        iso_project(0, 0, wh, SCALE),
        iso_project(max_x, 0, wh, SCALE),
    ]
    min_sx = min(c[0] for c in corners) - 40
    max_sx = max(c[0] for c in corners) + 40
    min_sy = min(c[1] for c in corners) - 40
    max_sy = max(c[1] for c in corners) + 80

    canvas_w = int(max_sx - min_sx)
    canvas_h = int(max_sy - min_sy)
    ox = -min_sx  # Offset X
    oy = -min_sy  # Offset Y

    dwg = svgwrite.Drawing(size=(f"{canvas_w}px", f"{canvas_h}px"))

    # Google Fonts
    dwg.defs.add(dwg.style("""
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap');
    """))

    # White background
    dwg.add(dwg.rect(insert=(0, 0), size=(canvas_w, canvas_h), fill="white"))

    # Sort rooms by Y+X (back to front for painter's algorithm)
    sorted_rooms = sorted(placed_rooms, key=lambda r: r['y'] + r['x'])

    for room in sorted_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']
        rtype = room['type'].lower().replace(' ', '_')

        right_color, front_color, top_color = ISO_ROOM_COLORS.get(rtype, DEFAULT_COLORS)

        # 8 corners of the room box
        # Floor corners
        f_tl = iso_project(rx, ry, 0, SCALE)
        f_tr = iso_project(rx + rw, ry, 0, SCALE)
        f_bl = iso_project(rx, ry + rh, 0, SCALE)
        f_br = iso_project(rx + rw, ry + rh, 0, SCALE)

        # Ceiling corners
        c_tl = iso_project(rx, ry, wh, SCALE)
        c_tr = iso_project(rx + rw, ry, wh, SCALE)
        c_bl = iso_project(rx, ry + rh, wh, SCALE)
        c_br = iso_project(rx + rw, ry + rh, wh, SCALE)

        # Apply offset
        def ofs(p):
            return (p[0] + ox, p[1] + oy)

        # Draw top face (ceiling/roof)
        top_points = [ofs(c_tl), ofs(c_tr), ofs(c_br), ofs(c_bl)]
        dwg.add(dwg.polygon(
            points=top_points,
            fill=top_color, stroke='#666', stroke_width=0.5
        ))

        # Draw right wall (visible right face: E wall)
        right_points = [ofs(f_tr), ofs(f_br), ofs(c_br), ofs(c_tr)]
        dwg.add(dwg.polygon(
            points=right_points,
            fill=right_color, stroke='#666', stroke_width=0.5
        ))

        # Draw front wall (visible front face: S wall)
        front_points = [ofs(f_bl), ofs(f_br), ofs(c_br), ofs(c_bl)]
        dwg.add(dwg.polygon(
            points=front_points,
            fill=front_color, stroke='#666', stroke_width=0.5
        ))

        # Room label on top face
        label_pos = iso_project(rx + rw / 2, ry + rh / 2, wh, SCALE)
        label_pos = ofs(label_pos)

        display_name = room.get('type', 'Room').upper()
        dwg.add(dwg.text(
            display_name,
            insert=(label_pos[0], label_pos[1] + 3),
            text_anchor='middle',
            font_size='7px',
            font_family='Inter, sans-serif',
            font_weight='500',
            fill='#333'
        ))

    # Title
    dwg.add(dwg.text(
        "ISOMETRIC VIEW",
        insert=(canvas_w / 2, canvas_h - 15),
        text_anchor='middle',
        font_size='11px',
        font_family='Inter, sans-serif',
        font_weight='500',
        fill='#666',
        letter_spacing='2px'
    ))

    return dwg.tostring()