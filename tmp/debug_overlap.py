"""Debug which rooms overlap in the treemap."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from services.layout_engine import calculate_room_sizes, place_rooms_on_grid
from services.vastu_engine import assign_vastu_zones
from shapely.geometry import box as shapely_box

rooms = [
    {"type": "bedroom", "count": 3},
    {"type": "bathroom", "count": 2},
    {"type": "kitchen", "count": 1},
    {"type": "dining", "count": 1},
    {"type": "living", "count": 1}
]
raw_assignments = assign_vastu_zones(rooms)
sized = calculate_room_sizes(2000, rooms)
placed = place_rooms_on_grid(60, 60, sized, raw_assignments)

total_area = 0
for p in placed:
    total_area += p["area"]
    print(f"  {p['id']:20s}  x={p['x']:7.2f} y={p['y']:7.2f}  w={p['width']:7.2f} h={p['height']:7.2f}  area={p['area']:7.2f}")

print(f"\nTotal area: {total_area:.2f}  (plot: {60*60})")
print(f"Room count: {len(placed)}")

overlaps_found = 0
for i, r1 in enumerate(placed):
    p1 = shapely_box(r1["x"], r1["y"], r1["x"] + r1["width"], r1["y"] + r1["height"])
    for j, r2 in enumerate(placed[i+1:], i+1):
        p2 = shapely_box(r2["x"], r2["y"], r2["x"] + r2["width"], r2["y"] + r2["height"])
        ix = p1.intersection(p2)
        if ix.area > 0.01:
            print(f"OVERLAP: {r1['id']} x {r2['id']} ix_area={ix.area:.4f}")
            overlaps_found += 1

print(f"\nOverlaps found: {overlaps_found}")
