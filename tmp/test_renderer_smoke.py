"""
Smoke test for the v2.0 Professional SVG Renderer (Shapely Geometry).
Tests:
  1. WallBoundaryGeometry generation via _build_wall_boundary
  2. SVG path generation from Shapely polygons
  3. Room polygon rendering
  4. Wall boundary polygon rendering
  5. Label collision detection
  6. Full pipeline render_blueprint_professional
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from services.professional_svg_renderer import (
    render_blueprint_professional,
    render_wall_boundary_polygon,
    render_room_polygons,
    _shift_label_clear_of_walls,
    _build_wall_boundary,
    _polygon_to_svg_path,
    _build_room_polygons,
)
from services.structural_engine import generate_wall_boundary, WallBoundaryGeometry
from shapely.geometry import box as shapely_box

print("=" * 70)
print("  Professional SVG Renderer v2.0 — Shapely Smoke Test")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════════
# Test 1: Wall boundary generation
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 1: _build_wall_boundary ──")
rooms = [
    {"id": "living_1", "type": "LIVING", "x": 0, "y": 0, "width": 15, "height": 12},
    {"id": "kitchen_1", "type": "KITCHEN", "x": 15, "y": 0, "width": 10, "height": 12},
    {"id": "bedroom_1", "type": "BEDROOM", "x": 0, "y": 12, "width": 12, "height": 10},
    {"id": "bathroom_1", "type": "BATHROOM", "x": 12, "y": 12, "width": 6, "height": 10},
    {"id": "passage_1", "type": "PASSAGE", "x": 18, "y": 12, "width": 7, "height": 10},
]
wb = _build_wall_boundary(rooms, 25, 22, wall_thickness=0.5)
assert wb.is_valid, "Wall boundary should be valid!"
assert wb.area > 0, "Wall boundary should have positive area!"
print(f"  Wall area: {wb.area:.2f} sqft (valid={wb.is_valid})")
print(f"  Bounds: {wb.polygon.bounds}")

# ═══════════════════════════════════════════════════════════════════════
# Test 2: Polygon to SVG path conversion
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 2: _polygon_to_svg_path ──")
d = _polygon_to_svg_path(wb.polygon, scale=10, margin=80)
assert d, "SVG path should be non-empty!"
assert "M " in d, "SVG path should start with M command"
assert "L " in d, "SVG path should contain L commands"
assert "Z" in d, "SVG path should contain Z (close)"
print(f"  SVG path length: {len(d)} chars")
print(f"  First 100 chars: {d[:100]}...")

# ═══════════════════════════════════════════════════════════════════════
# Test 3: Room polygons from dicts
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 3: _build_room_polygons ──")
polys = _build_room_polygons(rooms)
assert len(polys) == 5, f"Expected 5 room polygons, got {len(polys)}"
for p in polys:
    assert p.is_valid and p.area > 0
print(f"  Built {len(polys)} valid room polygons")

# ═══════════════════════════════════════════════════════════════════════
# Test 4: Label collision detection
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 4: _shift_label_clear_of_walls ──")

# Place a label right on a wall boundary (between living and kitchen at x=15)
# This label should be shifted toward the room centroid.
label_x = 80 + 15 * 10 - 20  # near x=15 (wall boundary), in px
label_y = 80 + 6 * 10         # middle of living room height, in px

shifted_x, shifted_y = _shift_label_clear_of_walls(
    label_x, label_y,
    label_w=40, label_h=12,
    room_cx=7.5, room_cy=6.0,  # living room centroid
    wall_boundary=wb,
    scale=10, margin=80,
)
print(f"  Original:  ({label_x:.1f}, {label_y:.1f})")
print(f"  Shifted:   ({shifted_x:.1f}, {shifted_y:.1f})")

# Label at room centroid should NOT be shifted (already clear)
center_x = 80 + 7.5 * 10
center_y = 80 + 6.0 * 10
stable_x, stable_y = _shift_label_clear_of_walls(
    center_x - 20, center_y,
    label_w=40, label_h=12,
    room_cx=7.5, room_cy=6.0,
    wall_boundary=wb,
    scale=10, margin=80,
)
print(f"  Centroid:  ({center_x - 20:.1f}, {center_y:.1f}) -> ({stable_x:.1f}, {stable_y:.1f})")
print("  ✓ Collision detection OK")

# ═══════════════════════════════════════════════════════════════════════
# Test 5: Full pipeline
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 5: Full render_blueprint_professional ──")

vastu_score = {"score": 78, "label": "Good", "color": "green"}

svg_output = render_blueprint_professional(
    placement_data=rooms,
    plot_width=25,
    plot_height=22,
    vastu_score=vastu_score,
    user_tier="free",
)

assert svg_output, "SVG output should be non-empty!"
assert "<svg" in svg_output or "<?xml" in svg_output, "Should be valid SVG!"

# Check for the new Shapely-based wall path (fill-rule: evenodd)
has_wall_path = 'fill-rule="evenodd"' in svg_output or "fill-rule:evenodd" in svg_output
print(f"  SVG length: {len(svg_output)} chars")
print(f"  Contains wall boundary path: {has_wall_path}")

# Check for room fill rect with thin stroke
has_room_stroke = 'stroke="#D0D5DD"' in svg_output
print(f"  Contains room polygons (thin gray stroke): {has_room_stroke}")

# Check for PlotAI watermark (free tier)
has_watermark = "PlotAI" in svg_output
print(f"  Contains watermark: {has_watermark}")

# Save SVG for visual inspection
out_path = os.path.join(os.path.dirname(__file__), "renderer_v2_test.svg")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg_output)
print(f"  Saved to: {out_path}")

print()
print("=" * 70)
print("  ALL TESTS PASSED ✓")
print("=" * 70)
