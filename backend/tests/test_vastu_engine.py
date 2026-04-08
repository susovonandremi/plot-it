
import pytest
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.vastu_engine import assign_vastu_zones, calculate_vastu_score

def test_kitchen_placement():
    rooms = [{"id": "k1", "type": "Kitchen"}]
    assigned = assign_vastu_zones(rooms)
    assert assigned['k1'] == 'SE'

def test_master_bedroom_placement():
    rooms = [{"id": "mb1", "type": "Master Bedroom"}]
    assigned = assign_vastu_zones(rooms)
    assert assigned['mb1'] == 'SW'

def test_bathroom_never_in_ne():
    rooms = [{"id": "b1", "type": "Bathroom"}]
    assigned = assign_vastu_zones(rooms)
    assert assigned['b1'] != 'NE'

def test_vastu_scoring_perfect():
    assignments = {
        "kitchen_1": "SE",
        "bedroom_1": "SW", 
        "living_1": "N"
    }
    
    score_data = calculate_vastu_score(assignments)
    assert score_data['score'] == 100
    assert "Excellent" in score_data['label']

def test_vastu_scoring_penalty():
    # Bad layout: Kitchen in NE (Forbidden, -20)
    assignments = {
        "kitchen_1": "NE"
    }
    score_data = calculate_vastu_score(assignments)
    # Base 100 - 20 = 80
    assert score_data['score'] <= 80
    assert any("kitchen" in v.lower() and "north-east" in v.lower() for v in score_data['violations'])
