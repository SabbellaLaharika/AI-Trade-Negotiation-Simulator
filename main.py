import json
import os
import logging
import asyncio
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from agents.negotiator import Negotiator
from scoring import calculate_compromise, save_negotiation_log

app = FastAPI(
    title="AI Trade Negotiation Simulator",
    description="Multi-agent bilateral trade agreement negotiation engine powered by Ollama and FastAPI",
    version="1.0.0"
)

@app.on_event("startup")
async def ensure_model_available():
    """Checks if the required Ollama model is available on startup, and automatically pulls it if missing."""
    target_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
    candidate_urls = [ollama_url, "http://localhost:11434", "http://127.0.0.1:11434"]

    async def _check_and_pull():
        for base in candidate_urls:
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.get(f"{base}/api/tags")
                    if res.status_code == 200:
                        models = [m.get("name", "") for m in res.json().get("models", [])]
                        if any(target_model in m for m in models):
                            logger.info(f"[Startup] Model '{target_model}' is already available in Ollama.")
                            return
                        logger.info(f"[Startup] Model '{target_model}' not found in Ollama. Auto-pulling now...")
                        async with httpx.AsyncClient(timeout=300.0) as pull_client:
                            pull_res = await pull_client.post(f"{base}/api/pull", json={"name": target_model, "stream": False})
                            if pull_res.status_code == 200:
                                logger.info(f"[Startup] Successfully pulled model '{target_model}'!")
                                return
            except Exception as e:
                logger.debug(f"[Startup] Endpoint {base} check: {e}")

    asyncio.create_task(_check_and_pull())

# Path to initial trade positions
POSITIONS_FILE = os.getenv(
    "TRADE_POSITIONS_PATH", 
    os.path.join(os.path.dirname(__file__), "data", "trade_positions.json")
)

# Serve static UI files if static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
async def serve_ui():
    """Serves the interactive single-page application UI."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Trade Negotiation Simulator API is operational. Visit /negotiate or /docs."}

def load_trade_positions() -> dict:
    """Loads country trade positions and priorities dynamically from JSON file."""
    if not os.path.exists(POSITIONS_FILE):
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

# Pydantic Schemas for Positions Response
class CountryPosition(BaseModel):
    priorities: List[str] = Field(..., description="List of trade priorities")
    flexibility: Dict[str, float] = Field(..., description="Flexibility weights per domain")

class TradePositionsResponse(BaseModel):
    usa: CountryPosition
    china: CountryPosition

    model_config = {
        "json_schema_extra": {
            "example": {
                "usa": {
                    "priorities": [
                        "Reduce tariffs on technology products",
                        "Strengthen intellectual property (IP) protection clauses"
                    ],
                    "flexibility": {
                        "tariffs": 0.7,
                        "ip_protection": 0.3
                    }
                },
                "china": {
                    "priorities": [
                        "Gain greater market access for agricultural products",
                        "Limit restrictions on technology transfer"
                    ],
                    "flexibility": {
                        "market_access": 0.8,
                        "tech_transfer_limits": 0.4
                    }
                }
            }
        }
    }

@app.get(
    "/positions", 
    response_model=TradePositionsResponse,
    summary="Get Initial Trade Positions",
    description="Returns the dynamically loaded initial trade positions, priorities, and flexibility weights for USA and China."
)
async def get_positions():
    """Returns the dynamically loaded initial trade positions for USA and China."""
    return load_trade_positions()

# Pydantic Schemas with OpenAPI Examples for Swagger UI
class NegotiateRequest(BaseModel):
    issue: str = Field(..., description="The trade issue subject to negotiation")
    rounds: int = Field(default=3, description="Number of negotiation rounds", ge=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "issue": "Semiconductor Import Tariffs",
                "rounds": 3
            }
        }
    }

class RoundItem(BaseModel):
    round: int = Field(..., description="Round number")
    usa_proposal: str = Field(..., description="Proposal string from USA agent")
    china_response: str = Field(..., description="Response string from China agent")

class OutcomeObject(BaseModel):
    agreement_reached: bool = Field(..., description="Boolean indicating if agreement was reached")
    final_terms: str = Field(..., description="Summary string detailing final negotiation terms")
    compromise_score: float = Field(..., description="Normalized compromise score between 0.0 and 1.0")

class NegotiateResponse(BaseModel):
    rounds: List[RoundItem] = Field(..., description="Array of round-by-round proposals and responses")
    outcome: OutcomeObject = Field(..., description="Negotiation outcome details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "rounds": [
                    {
                        "round": 1,
                        "usa_proposal": "The USA proposes to reduce tariffs on technology products and strengthen intellectual property (IP) protection clauses.",
                        "china_response": "China agrees to negotiate provided we gain greater market access for agricultural products."
                    },
                    {
                        "round": 2,
                        "usa_proposal": "The USA agrees to grant market access for agricultural products if IP protections are strictly enforced.",
                        "china_response": "China accepts lower tariffs and agrees to mutual intellectual property safeguards."
                    },
                    {
                        "round": 3,
                        "usa_proposal": "The USA confirms the reduced tariff schedule and IP protection terms.",
                        "china_response": "China signs the agreement based on agricultural access and technology transfer terms."
                    }
                ],
                "outcome": {
                    "agreement_reached": True,
                    "final_terms": "Agreement reached on Semiconductor Import Tariffs. USA proposed: 'The USA confirms the reduced tariff schedule...'. China agreed with terms: 'China signs the agreement...'.",
                    "compromise_score": 0.78
                }
            }
        }
    }

HTTP_422_CUSTOM_EXAMPLE = {
    422: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "example": {
                    "detail": [
                        {
                            "loc": ["body", "issue"],
                            "msg": "Field required",
                            "type": "missing"
                        }
                    ]
                }
            }
        }
    }
}

@app.post(
    "/negotiate", 
    response_model=NegotiateResponse,
    responses=HTTP_422_CUSTOM_EXAMPLE,
    summary="Initiate Negotiation Simulation",
    description="Triggers multi-round turn-taking between USA and China agents, evaluates compromise score, and logs outcome."
)
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

@app.get(
    "/negotiate/stream",
    summary="Real-Time Streaming Negotiation",
    description="Streams round-by-round turns live via Server-Sent Events (SSE) for the frontend UI."
)
async def negotiate_stream(issue: str, rounds: int = 3):
    async def event_generator():
        positions = load_trade_positions()
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

        usa_agent = Negotiator(country="usa", positions=positions.get("usa", {}), ollama_url=ollama_url)
        china_agent = Negotiator(country="china", positions=positions.get("china", {}), ollama_url=ollama_url)

        rounds_history: List[Dict[str, Any]] = []

        for round_num in range(1, rounds + 1):
            yield f"data: {json.dumps({'type': 'turn_start', 'round': round_num, 'agent': 'usa'})}\n\n"
            usa_proposal = await usa_agent.make_proposal(issue=issue, history=rounds_history)
            yield f"data: {json.dumps({'type': 'proposal', 'round': round_num, 'agent': 'usa', 'text': usa_proposal})}\n\n"

            current_turn_history = list(rounds_history)
            current_turn_history.append({
                "round": round_num,
                "usa_proposal": usa_proposal,
                "china_response": ""
            })

            yield f"data: {json.dumps({'type': 'turn_start', 'round': round_num, 'agent': 'china'})}\n\n"
            china_response = await china_agent.make_proposal(issue=issue, history=current_turn_history)
            yield f"data: {json.dumps({'type': 'response', 'round': round_num, 'agent': 'china', 'text': china_response})}\n\n"

            rounds_history.append({
                "round": round_num,
                "usa_proposal": usa_proposal,
                "china_response": china_response
            })

        compromise_score = calculate_compromise(rounds_history, positions)
        agreement_reached = bool(compromise_score >= 0.5)

        final_usa_prop = rounds_history[-1]["usa_proposal"] if rounds_history else ""
        final_china_resp = rounds_history[-1]["china_response"] if rounds_history else ""

        if agreement_reached:
            final_terms = f"Agreement reached on {issue}. USA proposed: '{final_usa_prop}'. China agreed with terms: '{final_china_resp}'."
        else:
            final_terms = f"No consensus reached on {issue}. Final USA stance: '{final_usa_prop}'. Final China stance: '{final_china_resp}'."

        outcome = {
            "agreement_reached": agreement_reached,
            "final_terms": final_terms,
            "compromise_score": compromise_score
        }

        # Persist log to negotiation_log.json
        log_entry = {
            "issue": issue,
            "total_rounds": rounds,
            "rounds": rounds_history,
            "outcome": outcome
        }
        save_negotiation_log(log_entry, filepath="negotiation_log.json")

        yield f"data: {json.dumps({'type': 'outcome', 'outcome': outcome})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
