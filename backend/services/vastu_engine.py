"""
Vastu Engine Service
Handles 3x3 grid zone assignments and Vastu Shastra scoring.
"""
import logging

from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Vastu Zone Constants (3x3 Grid)
ZONES = {
    "NW": "North-West",
    "N":  "North",
    "NE": "North-East",
    "W":  "West",
    "C":  "Center",
    "E":  "East",
    "SW": "South-West",
    "S":  "South",
    "SE": "South-East"
}

# Vastu Placement Rules
RULES = {
    "ENTRANCE": ["N", "E", "NE"],
    "MASTER_BEDROOM": ["SW"],
    "KITCHEN": ["SE"],
    "BEDROOM": ["W", "NW", "S", "E"], # Expanded general options
    "BEDROOM_CHILDREN": ["W", "NW"],
    "BEDROOM_GUEST": ["NW"],
    "DINING": ["W", "E"], 
    "BATHROOM": ["S", "W", "NW"], 
    "POOJA": ["NE"],
    "LIVING": ["N", "E", "NE"],
    "STUDY": ["W", "SW"],
    "STAIRCASE": ["S", "W", "SW"],
    "GARAGE": ["SE", "NW"],
    "PASSAGE": ["C"], # Central Hall / Corridor
}

# Forbidden Placements (Hard Rules)
FORBIDDEN = {
    "KITCHEN": ["NE"],
    "BATHROOM": ["NE"],
    "POOJA": ["S", "SW"], # Typical forbidden zones for pooja
}

# Avoid Placements
AVOID = {
    "BEDROOM": ["SE"],
    "ENTRANCE": ["S"]
}

def assign_vastu_zones(rooms: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Assigns each room to a Vastu zone based on its type and priority.
    Returns a dictionary mapping room_id to zone code.
    """
    assignments = {}
    
    # 1. Expand rooms into instances for assignment
    instances = []
    for config in rooms:
        count = int(config.get('count') or 1)
        base_type = (config.get('type', '') or '').upper().replace(" ", "_")
        if not base_type:
            continue
        
        for i in range(count):
            room_id = config.get('id', f"{config['type']}_{i+1}")
            
            # Special handling for Master Bedroom: first bedroom is Master
            normalized_type = base_type
            if base_type == "BEDROOM" and i == 0:
                normalized_type = "MASTER_BEDROOM"
                
            instances.append({
                'id': room_id,
                'type': config['type'],
                'normalized_type': normalized_type
            })
    
    occupied_zones = set()
    
    # Priority order for assignment
    # Master Bedroom high priority to secure SW
    priority_order = ["PASSAGE", "KITCHEN", "MASTER_BEDROOM", "POOJA", "ENTRANCE", "BATHROOM"]
    
    # Sort instances by priority
    sorted_instances = sorted(
        instances,
        key=lambda x: priority_order.index(x['normalized_type']) if x['normalized_type'] in priority_order else 99
    )
    
    for room in sorted_instances:
        room_type = room['normalized_type']
        preferred_zones = RULES.get(room_type, [])
        assigned_zone = None
        
        # 1. Try preferred zones that are not occupied
        for zone in preferred_zones:
            if zone not in occupied_zones:
                assigned_zone = zone
                break
        
        # 2. If nothing preferred is available, try any unoccupied zone that isn't FORBIDDEN
        if not assigned_zone:
            forbidden_for_room = FORBIDDEN.get(room_type, [])
            for zone in ZONES.keys():
                if zone not in occupied_zones and zone not in forbidden_for_room:
                    assigned_zone = zone
                    break
        
        # 3. Last resort - any unoccupied zone (fallback)
        if not assigned_zone:
            for zone in ZONES.keys():
                if zone not in occupied_zones:
                    assigned_zone = zone
                    break
        
        # If still no zone (more rooms than zones), allow overlap in 'C' or neighbors
        if not assigned_zone:
            assigned_zone = "C"

        assignments[room['id']] = assigned_zone
        occupied_zones.add(assigned_zone)
        
    return assignments

def calculate_vastu_score(assignments: Dict[str, str]) -> Dict[str, Any]:
    """
    Calculates the Vastu compliance score based on room ID assignments.
    """
    score = 100
    violations = []
    
    for room_id, zone in assignments.items():
        # Derive type from ID (e.g. bedroom_1 -> BEDROOM)
        parts = room_id.split('_')
        base_type = parts[0].upper()
        
        # Determine normalized type for scoring (first bedroom is Master)
        type_check = base_type
        if base_type == "BEDROOM" and len(parts) > 1 and parts[1] == "1":
            type_check = "MASTER_BEDROOM"
            
        # Check Forbidden
        if zone in FORBIDDEN.get(base_type, []):
            penalty = 20
            score -= penalty
            violations.append(f"FORBIDDEN: {room_id} in {ZONES.get(zone, zone)}")
        
        # Check Avoid
        elif zone in AVOID.get(base_type, []):
            penalty = 5
            score -= penalty
            violations.append(f"AVOID: {room_id} in {ZONES.get(zone, zone)}")
            
        # Check Preferred
        elif zone not in RULES.get(type_check, []):
            # Non-optimal placement
            penalty = 5
            score -= penalty
            violations.append(f"NON-OPTIMAL: {room_id} ({type_check}) in {ZONES.get(zone, zone)}")

    # Ensure score is not negative
    score = max(0, score)
    
    # Determine color and label
    if score >= 90:
        color = "green"
        label = "Excellent Vastu"
    elif score >= 70:
        color = "yellow"
        label = "Good Vastu"
    elif score >= 50:
        color = "orange"
        label = "Average Vastu"
    else:
        color = "red"
        label = "Poor Vastu"
        
    return {
        "score": score,
        "overall": score,  # Compatibility with legacy renderer
        "color": color,
        "label": label,
        "violations": violations
    }