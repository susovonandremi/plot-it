
import sys

# Try with utf-8 first
try:
    with open('services/building_program.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
except UnicodeDecodeError:
    # Fallback to latin-1 if utf-8 fails
    with open('services/building_program.py', 'r', encoding='latin-1') as f:
        lines = f.readlines()

new_func = [
    '    def get_floor_program(self, floor_number: int, floors_total: int) -> List[Dict]:\n',
    '        """Returns the CORRECT room list for each floor type (G+1 Residential Standard)."""\n',
    '        rooms = []\n',
    '        is_single_story = floors_total <= 1\n',
    '        is_independent = self.building_type == BuildingType.INDEPENDENT_HOUSE\n',
    '        \n',
    '        # Room normalizer helper for filtering\n',
    '        def _norm(rtype):\n',
    "            return rtype.lower().replace(' ', '_').replace('_room', '')\n",
    '\n',
    '        if floor_number == 0:\n',
    '            # GROUND FLOOR: PUBLIC ZONE\n',
    '            # 1. Mandatory Public Infrastructure\n',
    "            rooms.append({'type': 'car_parking', 'count': 1, 'area_hint': 200, 'label': 'CAR PARKING'}) # 10x20\n",
    "            rooms.append({'type': 'foyer', 'count': 1, 'area_hint': 48, 'label': 'FOYER'}) # 6x8\n",
    "            rooms.append({'type': 'staircase', 'count': 1, 'area_hint': 50, 'label': 'STAIRCASE'}) # 5x10\n",
    '            \n',
    '            if self.has_lift:\n',
    "                rooms.append({'type': 'lift', 'count': 1, 'area_hint': 25, 'label': 'LIFT'})\n",
    '\n',
    '            # 2. Infrastructure/Utilities\n',
    "            rooms.append({'type': 'sump', 'count': 1, 'area_hint': 35, 'is_external': True, 'label': 'SUMP'})\n",
    "            rooms.append({'type': 'septic_tank', 'count': 1, 'area_hint': 35, 'is_external': True, 'label': 'SEPTIC TANK'})\n",
    '            \n',
    '            # 3. Pull Public rooms from user_rooms if available\n',
    "            public_types = ['living', 'dining', 'kitchen', 'guest_bath', 'bathroom', 'toilet', 'wc', 'pooja', 'utility', 'wash']\n",
    '            \n',
    '            added_types = set()\n',
    '            for r in self.user_rooms:\n',
    "                ntype = _norm(r['type'])\n",
    "                if ntype in public_types and 'bedroom' not in ntype:\n",
    "                    # Limit to 1 bathroom on GF for G+1 unless explicitly requested more than 1 bath total\n",
    "                    if ntype in ['bathroom', 'toilet', 'wc'] and 'bathroom' in added_types:\n",
    '                        continue\n',
    '                    rooms.append(r.copy())\n',
    '                    added_types.add(ntype)\n',
    '\n',
    '            # Ensure minimal Public core if not in user_rooms\n',
    "            if 'living' not in added_types:\n",
    "                rooms.append({'type': 'Living Room', 'count': 1, 'area_hint': 220, 'label': 'LIVING'}) # 12x18+\n",
    "            if 'kitchen' not in added_types:\n",
    "                rooms.append({'type': 'Kitchen', 'count': 1, 'area_hint': 80, 'label': 'KITCHEN'})\n",
    "            if 'dining' not in added_types:\n",
    "                rooms.append({'type': 'Dining', 'count': 1, 'area_hint': 100, 'label': 'DINING'})\n",
    '\n',
    '        elif floor_number == 1 and not is_single_story:\n',
    '            # 1ST FLOOR: PRIVATE ZONE\n',
    "            rooms.append({'type': 'passage', 'count': 1, 'area_hint': 50, 'label': 'LANDING / CORRIDOR'})\n",
    "            rooms.append({'type': 'staircase', 'count': 1, 'area_hint': 50, 'label': 'STAIRCASE'})\n",
    '            \n',
    '            if self.has_lift:\n',
    "                rooms.append({'type': 'lift', 'count': 1, 'area_hint': 25, 'label': 'LIFT'})\n",
    '\n',
    '            # Pull Private rooms (Bedrooms)\n',
    '            bedroom_count = 0\n',
    '            for r in self.user_rooms:\n',
    "                ntype = _norm(r['type'])\n",
    "                if 'bedroom' in ntype:\n",
    '                    rooms.append(r.copy())\n',
    "                    bedroom_count += int(r.get('count', 1))\n",
    "                # Pull bathrooms for the bedrooms\n",
    "                elif ntype in ['bathroom', 'toilet', 'wc']:\n",
    '                    rooms.append(r.copy())\n',
    "                elif ntype in ['study', 'balcony', 'verandah']:\n",
    '                    rooms.append(r.copy())\n',
    '\n',
    '            # Ensure minimal private core if 3BHK was asked but not provided in user_rooms\n',
    '            if bedroom_count < 3 and is_independent:\n',
    '                for i in range(3 - bedroom_count):\n',
    "                    rooms.append({'type': 'Bedroom', 'count': 1, 'area_hint': 120, 'label': f'BEDROOM {bedroom_count + i + 1}'})\n",
    '\n',
    '        elif floor_number >= (2 if is_independent and not is_single_story else (floors_total if not is_single_story else 1)):\n',
    '            # ROOF FLOOR\n',
    "            rooms.append({'type': 'overhead_water_tank', 'count': 1, 'area_hint': 16, 'label': 'WATER TANK'}) # 4x4\n",
    "            rooms.append({'type': 'open_terrace', 'count': 1, 'area_hint': self.plot_area - 100, 'label': 'OPEN TERRACE'})\n",
    "            rooms.append({'type': 'stair_room', 'count': 1, 'area_hint': 40, 'label': 'MUMTY'}) # Staircase exit\n",
    '            \n',
    '        else:\n',
    '            # Fallback for Generic Upper Floors (N > 1)\n',
    '            rooms = [r.copy() for r in self.user_rooms]\n',
    "            rooms.append({'type': 'passage', 'count': 1, 'area_hint': 40})\n",
    "            rooms.append({'type': 'staircase', 'count': 1, 'area_hint': 50})\n",
    '                \n',
    '        return rooms\n'
]

# Find start and end indices
start_idx = -1
for i, line in enumerate(lines):
    if 'def get_floor_program' in line and (i > 500): # safety check
        start_idx = i
        break

if start_idx == -1:
    print("Could not find start of function")
    sys.exit(1)

# Find 'return rooms' that ends the function
end_idx = -1
for i in range(start_idx, len(lines)):
    if 'return rooms' in lines[i]:
        end_idx = i
        break

if end_idx == -1:
    print("Could not find end of function")
    sys.exit(1)

# Perform replacement
new_lines = lines[:start_idx] + new_func + lines[end_idx+1:]

# Detect encoding for writing
try:
    with open('services/building_program.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
except Exception as e:
    print(f"Error writing: {e}")
    sys.exit(1)

print("Successfully updated get_floor_program")
