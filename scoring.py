# scoring.py
from typing import List, Dict
import json
import os
import logging

logger = logging.getLogger("scoring")

CONCESSION_KEYWORDS = [
    "agree", "accept", "concede", "lower", "flexibility", "compromise", 
    "reduce", "mutual", "cooperate", "allow", "grant", "protection", "access"
]

COMBATIVE_KEYWORDS = [
    "reject", "refuse", "demand", "unacceptable", "insist", "deny", 
    "sanction", "threat", "strict", "prohibit", "never"
]

# Analyzes the final negotiation history to output a normalized score.
# Params:
#   - history (List[Dict]): The full array of rounds containing proposals and responses.
#   - positions (Dict): The initial configurations for both agents.
# Returns: A float between 0.0 and 1.0 representing the level of compromise.
def calculate_compromise(history: List[Dict], positions: dict) -> float:
    # Define a list of concession keywords (e.g., 'agree', 'accept', 'concede', 'lower')
    # Iterate through the history array.
    # Tally instances where agents used concession keywords versus combative keywords.
    # Normalize the final count into a floating-point number between 0.0 and 1.0.
    if not history:
        return 0.5

    concession_count = 0
    combative_count = 0

    for round_data in history:
        usa_text = str(round_data.get("usa_proposal", "")).lower()
        china_text = str(round_data.get("china_response", "")).lower()
        combined_text = f"{usa_text} {china_text}"

        for word in CONCESSION_KEYWORDS:
            concession_count += combined_text.count(word)

        for word in COMBATIVE_KEYWORDS:
            combative_count += combined_text.count(word)

    total_signals = concession_count + combative_count
    if total_signals == 0:
        base_score = 0.5
    else:
        base_score = concession_count / (concession_count + combative_count)

    usa_flex = positions.get("usa", {}).get("flexibility", {})
    china_flex = positions.get("china", {}).get("flexibility", {})
    
    avg_flex = 0.5
    all_flex_vals = list(usa_flex.values()) + list(china_flex.values())
    if all_flex_vals:
        avg_flex = sum(all_flex_vals) / len(all_flex_vals)

    final_score = (base_score * 0.7) + (avg_flex * 0.3)
    return float(round(max(0.0, min(1.0, final_score)), 2))

def save_negotiation_log(log_entry: dict, filepath: str = "negotiation_log.json") -> None:
    """
    Persists the state of completed negotiations by appending to local JSON file.
    """
    logs = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = [logs]
        except Exception as e:
            logger.warning(f"Could not read existing log file {filepath}: {e}")
            logs = []

    logs.append(log_entry)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)
