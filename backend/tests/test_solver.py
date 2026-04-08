"""Quick smoke test: solve a typical Indian residential plan."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.constraint_solver import solve_layout
from services.geometric_validator import validate_layout

# ── TEST 1: Standard 30×40 plot (1200 sqft) with 2BHK ──
print("=" * 60)
print("TEST 1: 30×40 plot — 2BHK")
print("=" * 60)

rooms = [
    {'type': 'Master Bedroom', 'count': 1},
    {'type': 'Bedroom', 'count': 1},
    {'type': 'Kitchen', 'count': 1},
    {'type': 'Living Room', 'count': 1},
    {'type': 'Dining', 'count': 1},
    {'type': 'Bathroom', 'count': 2},
    {'type': 'Passage', 'count': 1},
]

vastu = {
    'master_bedroom_0': 'SW',
    'bedroom_1': 'NW',
    'kitchen_2': 'SE',
    'living_3': 'NE',
    'dining_4': 'E',
    'bathroom_5': 'N',
    'bathroom_6': 'N',
    'passage_7': 'C',
}

result = solve_layout(30, 40, rooms, vastu, entry_direction='S')
print(f"Status: {result['status']}")
print(f"Solve time: {result['solve_time_ms']}ms")
print(f"Coverage: {result['coverage_pct']}%")
print(f"Rooms placed: {len(result['rooms'])}")
print()
for r in result['rooms']:
    print(f"  {r['id']:20s}  x={r['x']:6.1f}  y={r['y']:6.1f}  "
          f"w={r['width']:5.1f}  h={r['height']:5.1f}  "
          f"area={r['area']:6.1f} sqft")

# Run validator
validation = validate_layout(result['rooms'], 30, 40)
print(f"\nValidation: {'PASS' if validation['is_valid'] else 'FAIL'}")
print(f"  Overlaps: {validation['overlap_count']}")
if validation['errors']:
    for e in validation['errors']:
        print(f"  ERROR: {e}")
if validation['warnings']:
    for w in validation['warnings']:
        print(f"  WARN: {w}")


# ── TEST 2: Tight 20×30 plot (600 sqft) with 1BHK ──
print("\n" + "=" * 60)
print("TEST 2: 20×30 plot — 1BHK (tight)")
print("=" * 60)

rooms2 = [
    {'type': 'Bedroom', 'count': 1},
    {'type': 'Kitchen', 'count': 1},
    {'type': 'Living', 'count': 1},
    {'type': 'Bathroom', 'count': 1},
]

result2 = solve_layout(20, 30, rooms2, entry_direction='S')
print(f"Status: {result2['status']}")
print(f"Solve time: {result2['solve_time_ms']}ms")
print(f"Coverage: {result2['coverage_pct']}%")
for r in result2['rooms']:
    print(f"  {r['id']:20s}  x={r['x']:6.1f}  y={r['y']:6.1f}  "
          f"w={r['width']:5.1f}  h={r['height']:5.1f}  "
          f"area={r['area']:6.1f} sqft")

validation2 = validate_layout(result2['rooms'], 20, 30)
print(f"\nValidation: {'PASS' if validation2['is_valid'] else 'FAIL'}")
print(f"  Overlaps: {validation2['overlap_count']}")


# ── TEST 3: Large 40×60 plot (2400 sqft) with 3BHK ──
print("\n" + "=" * 60)
print("TEST 3: 40×60 plot — 3BHK (spacious)")
print("=" * 60)

rooms3 = [
    {'type': 'Master Bedroom', 'count': 1},
    {'type': 'Bedroom', 'count': 2},
    {'type': 'Kitchen', 'count': 1},
    {'type': 'Living', 'count': 1},
    {'type': 'Dining', 'count': 1},
    {'type': 'Bathroom', 'count': 3},
    {'type': 'Pooja', 'count': 1},
    {'type': 'Study', 'count': 1},
    {'type': 'Passage', 'count': 1},
    {'type': 'Staircase', 'count': 1},
]

result3 = solve_layout(40, 60, rooms3, entry_direction='E')
print(f"Status: {result3['status']}")
print(f"Solve time: {result3['solve_time_ms']}ms")
print(f"Coverage: {result3['coverage_pct']}%")
print(f"Rooms placed: {len(result3['rooms'])}")
for r in result3['rooms']:
    print(f"  {r['id']:20s}  x={r['x']:6.1f}  y={r['y']:6.1f}  "
          f"w={r['width']:5.1f}  h={r['height']:5.1f}  "
          f"area={r['area']:6.1f} sqft")

validation3 = validate_layout(result3['rooms'], 40, 60)
print(f"\nValidation: {'PASS' if validation3['is_valid'] else 'FAIL'}")
print(f"  Overlaps: {validation3['overlap_count']}")
if validation3['errors']:
    for e in validation3['errors']:
        print(f"  ERROR: {e}")

print("\nAll tests complete!")
