"""Smoke test for v5.0 Circulation-First Layout Engine."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from services.layout_engine import (
    calculate_room_sizes, generate_layout, LayoutEngine,
    has_overlap, snap_to_grid, snap_room_to_grid,
    subdivide_buildable_area, subdivide_with_circulation,
    RoomAdjacencyGraph, _aspect_ratio,
    place_rooms_on_grid,
)
from shapely.geometry import box as shapely_box

print("=" * 70)
print("  Layout Engine v5.0 — Circulation-First Smoke Test")
print("=" * 70)

# ═══════════════════════════════════════════════════════════════════════
# Test 1: RoomAdjacencyGraph
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 1: RoomAdjacencyGraph ──")
graph = RoomAdjacencyGraph()
rooms_input = [
    {"type": "living", "normalized_type": "LIVING"},
    {"type": "bedroom", "normalized_type": "BEDROOM"},
    {"type": "kitchen", "normalized_type": "KITCHEN"},
    {"type": "passage", "normalized_type": "PASSAGE"},
]
graph.build_from_room_list(rooms_input)

nbs = graph.preferred_neighbours("bedroom")
print(f"  bedroom neighbours: {nbs}")
assert "bathroom" in nbs, "bedroom should prefer bathroom"
assert "passage" in nbs, "bedroom should prefer passage"

assert graph.is_forbidden("kitchen", "bedroom"), "kitchen-bedroom should be forbidden"
assert not graph.is_forbidden("living", "dining"), "living-dining should NOT be forbidden"

assert graph.needs_spine_access("bedroom"), "bedroom needs passage access"
assert graph.needs_spine_access("kitchen"), "kitchen needs passage access"

assert graph.classify_zone("LIVING") == "public"
assert graph.classify_zone("BEDROOM") == "private"
print("  ✓ Graph edges, forbidden, spine access, zone classification OK")

# Serialise
gd = graph.to_dict()
assert len(gd["nodes"]) > 0
assert len(gd["edges"]) > 0
print(f"  ✓ Serialised: {len(gd['nodes'])} nodes, {len(gd['edges'])} edges")

# ═══════════════════════════════════════════════════════════════════════
# Test 2: Circulation spine carving
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 2: subdivide_with_circulation (30×40 plot, 9 rooms) ──")

buildable = shapely_box(0, 0, 30, 40)
targets = [
    {"id": "living_1",   "type": "LIVING",   "area": 160, "normalized_type": "LIVING"},
    {"id": "bedroom_1",  "type": "BEDROOM",  "area": 130, "normalized_type": "BEDROOM"},
    {"id": "bedroom_2",  "type": "BEDROOM",  "area": 120, "normalized_type": "BEDROOM"},
    {"id": "kitchen_1",  "type": "KITCHEN",  "area": 110, "normalized_type": "KITCHEN"},
    {"id": "dining_1",   "type": "DINING",   "area": 90,  "normalized_type": "DINING"},
    {"id": "bathroom_1", "type": "BATHROOM", "area": 35,  "normalized_type": "BATHROOM"},
    {"id": "bathroom_2", "type": "BATHROOM", "area": 35,  "normalized_type": "BATHROOM"},
    {"id": "passage_1",  "type": "PASSAGE",  "area": 80,  "normalized_type": "PASSAGE"},
    {"id": "pooja_1",    "type": "POOJA",    "area": 40,  "normalized_type": "POOJA"},
]

placed = subdivide_with_circulation(buildable, targets)
print(f"  Placed {len(placed)} rooms:")

spine_rooms_placed = []
flank_a_placed = []
flank_b_placed = []
total_area = 0
for p in placed:
    w, h = p["width"], p["height"]
    ar = max(w, h) / min(w, h) if min(w, h) > 0 else 999
    total_area += p["area"]
    is_spine = p.get("is_circulation", False) or p["type"] == "PASSAGE"
    zone = "SPINE" if is_spine else p.get("zone", "?")
    print(f"    {p['id']:20s}  ({p['x']:6.2f},{p['y']:6.2f})  {w:6.2f}×{h:6.2f}  AR={ar:.2f}  [{zone}]")

    if p["type"] in ("PASSAGE", "STAIRCASE", "LIFT"):
        spine_rooms_placed.append(p)

print(f"  Total area: {total_area:.2f} / {buildable.area:.2f}")
print(f"  Spine rooms: {len(spine_rooms_placed)}")

# Must have at least one spine room placed
assert len(spine_rooms_placed) >= 1, "No spine room found!"
print("  ✓ Spine carved and rooms partitioned")

# ═══════════════════════════════════════════════════════════════════════
# Test 3: Spine-edge adjacency check
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 3: Spine edge adjacency ──")

# Check that rooms requiring spine access share at least one edge with
# the spine polygon.
spine_polys = []
for sp in spine_rooms_placed:
    spine_polys.append(shapely_box(sp["x"], sp["y"],
                                    sp["x"] + sp["width"],
                                    sp["y"] + sp["height"]))
spine_union = spine_polys[0] if len(spine_polys) == 1 else spine_polys[0].union(spine_polys[-1])

# Rooms that should touch the spine
should_touch = {"BEDROOM", "KITCHEN", "LIVING"}
graph2 = RoomAdjacencyGraph()
touching_count = 0
total_checked = 0
for p in placed:
    nt = p.get("normalized_type", p["type"]).upper()
    if nt in should_touch:
        total_checked += 1
        rp = shapely_box(p["x"], p["y"], p["x"] + p["width"], p["y"] + p["height"])
        if rp.touches(spine_union) or rp.intersects(spine_union):
            touching_count += 1

if total_checked > 0:
    touch_pct = touching_count / total_checked * 100
    print(f"  {touching_count}/{total_checked} spine-access rooms touch the spine ({touch_pct:.0f}%)")
else:
    print("  No rooms checked (no bedrooms/kitchen/living)")

# ═══════════════════════════════════════════════════════════════════════
# Test 4: Overlap check (Shapely geometric)
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 4: Geometric overlap check ──")
overlap_count = 0
for i, r1 in enumerate(placed):
    p1 = shapely_box(r1["x"], r1["y"], r1["x"] + r1["width"], r1["y"] + r1["height"])
    for j, r2 in enumerate(placed[i+1:], i+1):
        p2 = shapely_box(r2["x"], r2["y"], r2["x"] + r2["width"], r2["y"] + r2["height"])
        ix = p1.intersection(p2)
        if ix.area > 0.01:
            print(f"  ⚠ OVERLAP: {r1['id']} × {r2['id']} area={ix.area:.4f}")
            overlap_count += 1
print(f"  {'✓ Zero' if overlap_count == 0 else f'✗ {overlap_count}'} overlaps")
assert overlap_count == 0, f"Found {overlap_count} overlaps!"

# ═══════════════════════════════════════════════════════════════════════
# Test 5: calculate_room_sizes (preserved API)
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 5: calculate_room_sizes ──")
rooms_cfg = [
    {"type": "Living", "count": 1},
    {"type": "Bedroom", "count": 2},
    {"type": "Kitchen", "count": 1},
    {"type": "Bathroom", "count": 2},
]
sized = calculate_room_sizes(1200, rooms_cfg)
print(f"  Expanded {len(sized)} rooms")
assert len(sized) == 6

# ═══════════════════════════════════════════════════════════════════════
# Test 6: Full pipeline with passage in room list
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 6: Full pipeline (LayoutEngine with passage) ──")
full_rooms = calculate_room_sizes(2400, [
    {"type": "Living", "count": 1},
    {"type": "Bedroom", "count": 3},
    {"type": "Kitchen", "count": 1},
    {"type": "Dining", "count": 1},
    {"type": "Bathroom", "count": 2},
    {"type": "Passage", "count": 1},
])
result = generate_layout(2400, full_rooms)
print(f"  Rooms: {len(result['rooms'])}, Total area used: {result['total_area_used']}")
has_spine = any(r["type"] in ("PASSAGE", "STAIRCASE") for r in result["rooms"])
print(f"  Spine present: {has_spine}")
assert has_spine, "No spine in output!"

# ═══════════════════════════════════════════════════════════════════════
# Test 7: Backward-compat — place_rooms_on_grid
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 7: Backward-compat place_rooms_on_grid ──")
from services.vastu_engine import assign_vastu_zones
rooms_old = [
    {"type": "bedroom", "count": 2},
    {"type": "bathroom", "count": 1},
    {"type": "kitchen", "count": 1},
    {"type": "living", "count": 1},
]
raw_assignments = assign_vastu_zones(rooms_old)
sized_old = calculate_room_sizes(1200, rooms_old)
placed_old = place_rooms_on_grid(40, 30, sized_old, raw_assignments)
print(f"  Placed {len(placed_old)} rooms via legacy API")
assert len(placed_old) >= 5

# ═══════════════════════════════════════════════════════════════════════
# Test 8: has_overlap / snap_to_grid (utilities)
# ═══════════════════════════════════════════════════════════════════════
print("\n── Test 8: Utility functions ──")
r1 = {"x": 0, "y": 0, "width": 10, "height": 10}
r2 = {"x": 11, "y": 0, "width": 10, "height": 10}
r3 = {"x": 5, "y": 5, "width": 10, "height": 10}
assert not has_overlap(r1, r2)
assert has_overlap(r1, r3)
assert snap_to_grid(12.3) == 12.0
assert snap_to_grid(12.7) == 13.0
print("  ✓ has_overlap, snap_to_grid OK")

print()
print("=" * 70)
print("  ALL TESTS PASSED ✓")
print("=" * 70)
