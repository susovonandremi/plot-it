
import pytest
from unittest.mock import MagicMock, patch
import sys
import os
import requests

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.nlp_parser import (
    parse_prompt, 
    generate_consultation_questions,
    analyze_consultation_answers
)

class TestNLPParser:

    # TEST 1.1 — Simple English prompt
    def test_simple_english_prompt(self):
        """Tests that a basic English prompt is correctly parsed."""
        # Mocking requests.post
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "choices": [{
                    "message": {
                        "content": '{"plot_size_sqft": 1200, "is_complete": true, "rooms": [{"type": "bedroom", "count": 3}], "orientation": "north"}'
                    }
                }]
            }
            
            result = parse_prompt(
                "I have a 1200 sqft plot, 3 bedrooms, 2 bathrooms, 1 kitchen, 1 dining room, 1 lounge"
            )
            assert result["plot_size_sqft"] == 1200
            assert result["is_complete"] == True
            assert result["consultation"]["needed"] == False

    # TEST 1.2 — Incomplete prompt triggers consultation
    def test_incomplete_prompt_triggers_consultation(self):
        """
        CRITICAL: Incomplete input must trigger consultation mode.
        """
        with patch('requests.post') as mock_post:
            # First call: parse_prompt
            mock_post.return_value.status_code = 200
            # Mock the parse response saying incomplete
            mock_post.side_effect = [
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={
                        "choices": [{"message": {"content": '{"plot_size_sqft": 1500, "is_complete": false, "missing_info": ["rooms"], "orientation": "north"}'}}]
                    })
                ),
                # Second call: generate_consultation_questions
                MagicMock(
                    status_code=200,
                    json=MagicMock(return_value={
                        "choices": [{"message": {"content": '[{"id": "q1", "text": "Purpose?", "type": "single_select", "options": [{"id": "home", "label": "Home"}], "required": true}]'
                        }}] 
                    })
                )
            ]
            
            result = parse_prompt("I have a 1500 sqft north-facing plot")
            assert result["is_complete"] == False
            assert result["consultation"]["needed"] == True
            # The mocked questions take precedence over logic checks inside parser if any
            # But wait, generate_consultation_questions is called inside parse_prompt.
            # We need to make sure side_effect handles the call sequence.
            
    # TEST 1.4 — Consultation answers generate valid recommendations
    def test_consultation_recommendation_generation(self):
        """Tests that user answers produce room recommendations."""
        plot_data = {"plot_size_sqft": 1500, "orientation": "north"}
        answers = {"q1": ["home"]}
        
        with patch('requests.post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {
                    "content": '{"recommended_rooms": [{"type": "bedroom", "count": 3, "reasoning": "Family needs"}], "total_rooms": 3, "vastu_preview": "95%", "estimated_usage": "80%"}'
                }}]
            }
        
            recommendation = analyze_consultation_answers(plot_data, answers)
            
            assert "recommended_rooms" in recommendation
            assert recommendation["total_rooms"] == 3
            assert len(recommendation["recommended_rooms"]) > 0
