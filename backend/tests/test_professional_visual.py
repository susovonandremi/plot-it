"""
Visual test: Generates a professional blueprint using BSP + professional renderer.
Run this script and open the output HTML file to verify.
"""

import sys
import os
import math
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_spatial_reasoner import get_spatial_plan
from services.strip_layout_engine import generate_strip_layout
from services.vastu_engine import assign_vastu_zones, calculate_vastu_score
from services.layout_engine import calculate_room_sizes
from services.professional_svg_renderer import (
    render_blueprint_professional,
    extract_wall_segments,
    find_door_positions,
    find_window_positions,
)


def main():
    # ── Simulate: 2000 sqft, 3 bed, 2 bath, kitchen, dining, living ──
    plot_size = 2000
    raw_rooms = [
        {"type": "kitchen", "count": 1},
        {"type": "bedroom", "count": 3},
        {"type": "bathroom", "count": 2},
        {"type": "living", "count": 1},
        {"type": "dining", "count": 1},
    ]

    # Step 1: Vastu
    vastu_assignments = assign_vastu_zones(raw_rooms)
    vastu_results = calculate_vastu_score(vastu_assignments)

    # Step 2: Size rooms
    expanded_rooms = calculate_room_sizes(plot_size, raw_rooms)
    for room in expanded_rooms:
        room['zone'] = vastu_assignments.get(room['id'], 'C')

    # Step 3: Hybrid Layout
    plot_side = round(math.sqrt(plot_size), 1)
    num_rooms = len(expanded_rooms)

    plan = get_spatial_plan("test layout", plot_side, plot_side, 1, "S", expanded_rooms)
    placed = generate_strip_layout(plot_side, plot_side, plan, expanded_rooms, "S")

    print(f"\n🏗️  Hybrid Layout: {num_rooms} rooms on {plot_side}×{plot_side} plot")
    for r in placed:
        # Avoid KeyError for missing zone by omitting it from print, or fetching from Vastu
        print(f"  {r['id']:15s}  "
              f"({r['x']:5.1f}, {r['y']:5.1f})  "
              f"{r['width']:5.1f} × {r['height']:5.1f}")

    # Step 4: Extract wall info for debug
    bounds = {'min_x': 0, 'min_y': 0, 'max_x': plot_side, 'max_y': plot_side}
    walls = extract_wall_segments(placed, bounds)
    doors = find_door_positions(placed)
    windows = find_window_positions(placed, bounds)
    
    print(f"\n📐 Wall segments: {len(walls['horizontal'])} horizontal, {len(walls['vertical'])} vertical")
    print(f"   Exterior walls: {len(walls['exterior'])}")
    print(f"🚪 Doors: {len(doors)}")
    for d in doors:
        print(f"   {d['room1_id']} ↔ {d['room2_id']}  ({d['orientation']})")
    print(f"🪟 Windows: {len(windows)}")
    for w in windows:
        print(f"   {w['room_id']}  ({w['side']} wall)")

    # Step 5: Render professional SVG
    svg = render_blueprint_professional(
        placement_data=placed,
        plot_width=plot_side,
        plot_height=plot_side,
        vastu_score=vastu_results,
        user_tier="free"
    )

    # Step 6: Save as HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Professional Blueprint Test — PlotAI</title>
    <style>
        body {{
            background: #0F172A;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            font-family: system-ui;
            padding: 20px;
        }}
        .container {{
            background: white;
            padding: 32px;
            border-radius: 16px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.3);
        }}
        h2 {{
            margin: 0 0 8px;
            color: #1e293b;
            font-size: 18px;
        }}
        .subtitle {{
            font-size: 13px;
            color: #64748b;
            margin-bottom: 16px;
        }}
        .checks {{
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
            font-size: 12px;
            color: #475569;
        }}
        .checks span {{
            background: #F1F5F9;
            padding: 4px 10px;
            border-radius: 6px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>📐 Professional Blueprint Renderer</h2>
        <div class="subtitle">
            {num_rooms} rooms | {plot_side}×{plot_side} ft |
            Vastu: {vastu_results['score']}% {vastu_results['label']} |
            {len(doors)} doors | {len(windows)} windows
        </div>
        <div class="checks">
            <span>✅ Thick walls (0.5ft)</span>
            <span>✅ No junction gaps</span>
            <span>✅ Door arcs</span>
            <span>✅ Window symbols</span>
            <span>✅ Dimension lines</span>
        </div>
        {svg}
    </div>
</body>
</html>"""

    output_path = os.path.join(os.path.dirname(__file__), 'professional_test_output.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ Professional blueprint saved to: {output_path}")
    print("   Open this file in a browser to verify.")


if __name__ == "__main__":
    main()
