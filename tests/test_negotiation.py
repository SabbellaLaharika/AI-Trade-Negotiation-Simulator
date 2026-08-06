import os
import json
import httpx
import pytest

# Compatibility patch for httpx >= 0.28.0 with starlette TestClient
_orig_httpx_init = httpx.Client.__init__
def _patched_httpx_init(self, *args, **kwargs):
    if "app" in kwargs:
        app = kwargs.pop("app")
        if "transport" not in kwargs and app is not None:
            kwargs["transport"] = httpx.ASGITransport(app=app)
    _orig_httpx_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_httpx_init

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_negotiation_rounds_length():
    """Verify that requesting 3 rounds returns a rounds array of length 3."""
    payload = {
        "issue": "Technology Tariffs",
        "rounds": 3
    }
    response = client.post("/negotiate", json=payload)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
    data = response.json()
    
    assert "rounds" in data
    assert isinstance(data["rounds"], list)
    assert len(data["rounds"]) == 3, f"Expected rounds array length of 3, got {len(data['rounds'])}"

def test_negotiation_single_round():
    """Verify that requesting 1 round returns a rounds array of length 1."""
    payload = {
        "issue": "Agricultural Subsidies",
        "rounds": 1
    }
    response = client.post("/negotiate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["rounds"]) == 1

def test_negotiation_outcome_schema_and_score_range():
    """Verify outcome object structure and normalized compromise_score float range."""
    payload = {
        "issue": "Intellectual Property Safeguards",
        "rounds": 2
    }
    response = client.post("/negotiate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "outcome" in data
    outcome = data["outcome"]
    
    assert "agreement_reached" in outcome
    assert isinstance(outcome["agreement_reached"], bool)
    
    assert "final_terms" in outcome
    assert isinstance(outcome["final_terms"], str)
    assert len(outcome["final_terms"]) > 0

    assert "compromise_score" in outcome
    score = outcome["compromise_score"]
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 1.0, f"compromise_score {score} is out of bounds [0.0, 1.0]"

def test_positions_reference_in_proposals():
    """Verify that proposals actively reference key priority terms from trade_positions.json."""
    payload = {
        "issue": "Semiconductor Import Tariffs",
        "rounds": 2
    }
    response = client.post("/negotiate", json=payload)
    assert response.status_code == 200
    data = response.json()

    rounds = data["rounds"]
    assert len(rounds) > 0

    # Load initial trade positions to compare priority terms
    positions_file = os.getenv("TRADE_POSITIONS_PATH", "data/trade_positions.json")
    with open(positions_file, "r", encoding="utf-8") as f:
        trade_positions = json.load(f)

    # Verify USA proposals mention USA priorities (e.g. 'tariffs', 'ip', 'protection')
    usa_priority_keywords = ["tariff", "tariffs", "ip", "protection", "intellectual"]
    # Verify China responses mention China priorities (e.g. 'market access', 'agricultural', 'tech')
    china_priority_keywords = ["market", "access", "agricultural", "tech", "transfer"]

    found_usa_keyword = False
    found_china_keyword = False

    for r in rounds:
        usa_text = r.get("usa_proposal", "").lower()
        china_text = r.get("china_response", "").lower()

        if any(kw in usa_text for kw in usa_priority_keywords):
            found_usa_keyword = True
        
        if any(kw in china_text for kw in china_priority_keywords):
            found_china_keyword = True

    assert found_usa_keyword, f"USA proposals did not reference priority terms: {[r.get('usa_proposal') for r in rounds]}"
    assert found_china_keyword, f"China responses did not reference priority terms: {[r.get('china_response') for r in rounds]}"
