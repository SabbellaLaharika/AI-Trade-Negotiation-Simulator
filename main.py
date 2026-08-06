import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from agents.negotiator import Negotiator
from scoring import calculate_compromise, save_negotiation_log

app = FastAPI(title="AI Trade Negotiation Simulator")

# Path to initial trade positions
POSITIONS_FILE = os.getenv(
    "TRADE_POSITIONS_PATH", 
    os.path.join(os.path.dirname(__file__), "data", "trade_positions.json")
)

def load_trade_positions() -> dict:
    """Loads country trade positions and priorities dynamically from JSON file."""
    if not os.path.exists(POSITIONS_FILE):
        # Fallback default positions if file missing
        return {
            "usa": {
                "priorities": [
                    "Reduce tariffs on technology products",
                    "Strengthen intellectual property (IP) protection clauses"
                ],
                "flexibility": {"tariffs": 0.7, "ip_protection": 0.3}
            },
            "china": {
                "priorities": [
                    "Gain greater market access for agricultural products",
                    "Limit restrictions on technology transfer"
                ],
                "flexibility": {"market_access": 0.8, "tech_transfer_limits": 0.4}
            }
        }
    with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

class NegotiateRequest(BaseModel):
    issue: str = Field(..., description="The trade issue subject to negotiation")
    rounds: int = Field(default=3, description="Number of negotiation rounds", ge=1)

@app.post("/negotiate")
async def negotiate(request: NegotiateRequest):
    positions = load_trade_positions()
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

    usa_agent = Negotiator(country="usa", positions=positions.get("usa", {}), ollama_url=ollama_url)
    china_agent = Negotiator(country="china", positions=positions.get("china", {}), ollama_url=ollama_url)

    rounds_history: List[Dict[str, Any]] = []

    for round_num in range(1, request.rounds + 1):
        # 1. USA agent generates a proposal based on context & history
        usa_proposal = await usa_agent.make_proposal(issue=request.issue, history=rounds_history)

        # 2. Temporary history turn to allow China agent to see current proposal
        current_turn_history = list(rounds_history)
        current_turn_history.append({
            "round": round_num,
            "usa_proposal": usa_proposal,
            "china_response": ""
        })

        # 3. China agent generates a response based on updated history
        china_response = await china_agent.make_proposal(issue=request.issue, history=current_turn_history)

        # 4. Append round data to rounds_history
        rounds_history.append({
            "round": round_num,
            "usa_proposal": usa_proposal,
            "china_response": china_response
        })

    # Evaluate negotiation outcome using scoring heuristic
    compromise_score = calculate_compromise(rounds_history, positions)
    agreement_reached = bool(compromise_score >= 0.5)

    # Summarize final terms from last turn
    final_usa_prop = rounds_history[-1]["usa_proposal"] if rounds_history else ""
    final_china_resp = rounds_history[-1]["china_response"] if rounds_history else ""
    
    if agreement_reached:
        final_terms = f"Agreement reached on {request.issue}. USA proposed: '{final_usa_prop}'. China agreed with terms: '{final_china_resp}'."
    else:
        final_terms = f"No consensus reached on {request.issue}. Final USA stance: '{final_usa_prop}'. Final China stance: '{final_china_resp}'."

    outcome = {
        "agreement_reached": agreement_reached,
        "final_terms": final_terms,
        "compromise_score": compromise_score
    }

    response_payload = {
        "rounds": rounds_history,
        "outcome": outcome
    }

    # Persist log to negotiation_log.json
    log_entry = {
        "issue": request.issue,
        "total_rounds": request.rounds,
        "rounds": rounds_history,
        "outcome": outcome
    }
    save_negotiation_log(log_entry, filepath="negotiation_log.json")

    return response_payload
