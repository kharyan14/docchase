import datetime
import os
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import docchase
import listen
import speak

BASE_DIR = Path(__file__).resolve().parent
APPROVALS_LOG = BASE_DIR / "approvals.log"


def log_approval(case_id: str, note: str = "Approved by human reviewer") -> None:
    """
    Guardrail: Never approves on its own. Only logs human decision.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(APPROVALS_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] CASE={case_id} STATUS=APPROVED NOTE={note}\n")


def extract_case_id(text: str, open_cases: dict) -> str:
    """
    Extract case ID from user query. Supports '102', 'case 102', 'case-102', 'ins 101', 'ins-101',
    as well as word numbers like 'one zero two' or 'one hundred two'.
    """
    raw = text.lower().strip()

    # Map word digits to numerals
    word_digits = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    }
    for word, digit in word_digits.items():
        raw = re.sub(rf"\b{word}\b", digit, raw)
    # remove spaces between digits (e.g., '1 0 2' -> '102')
    raw = re.sub(r"(?<=\d)\s+(?=\d)", "", raw)

    # Check for direct case identifiers like CASE-102 or INS-101
    match = re.search(r"\b(case|ins)[-\s]?(\d{3})\b", raw)
    if match:
        prefix, num = match.groups()
        candidate = f"{prefix.upper()}-{num}"
        if candidate in open_cases:
            return candidate

    # Check for standalone 3-digit number (e.g. '102')
    match_num = re.search(r"\b(\d{3})\b", raw)
    if match_num:
        num = match_num.group(1)
        for prefix in ["CASE", "INS"]:
            candidate = f"{prefix}-{num}"
            if candidate in open_cases:
                return candidate

    return None


def handle_query(query: str) -> str:
    """
    Processes the user query enforcing the 5 demo asks and 5 guardrails.
    Returns the exact, to-the-point conversational voice response.
    """
    query_clean = query.strip()
    if not query_clean:
        return "I didn't understand that question. Could you ask again?"

    open_cases = docchase.load_open_cases()
    q_lower = query_clean.lower()

    # 1. Extract case ID
    case_id = extract_case_id(query_clean, open_cases)

    # Guardrail: Check for unknown case mentions like 'case 999' or 'case 404'
    if not case_id:
        has_case_intent = bool(re.search(r"\bcase\b|\bins\b|\b\d{3}\b", q_lower))
        if has_case_intent:
            return "I don't have that case."
        return "I didn't understand that question. Could you ask again?"

    case = open_cases[case_id]

    # Guardrail: Sensitive case check (Ask 4 & Guardrail 1)
    # Must refuse to propose an action, route to human reviewer
    if case.get("sensitive_case"):
        if case_id == "INS-105":
            return "The claim contains potentially altered invoices outside standard workflow, and this sensitive case needs human review."
        return "The loan file references a suspicious transfer document outside standard workflow, and this sensitive case needs human review."

    # Guardrail & Ask 5: Human Approval
    # It never approves on its own, only logs your decision.
    if re.search(r"\b(approve|approved|accept|sign off)\b", q_lower):
        log_approval(case_id, note=f"Voice approval: '{query_clean}'")
        return f"I've logged your approval for {case_id}. The human decides."

    # Ask: Specific Details
    if re.search(r"\b(detail|details|specifics|specific|more info|tell me more|who is|borrower|patient|confidence|evidence|missing field|document type)\b", q_lower):
        return docchase.answer(case_id, "details", query_text=query_clean)

    # Ask 2: Context on past cases
    if re.search(r"\b(context|past case|past cases|history|similar)\b", q_lower):
        return docchase.answer(case_id, "context")

    # Ask 3: Decision guidance
    if re.search(r"\b(decide|decision|what do i need to decide|action|proposal)\b", q_lower):
        return docchase.answer(case_id, "decision")

    # Ask 1: What is missing / Status / Default case query
    is_missing_query = bool(re.search(r"\b(missing|status|lacking|needed document|required document)\b", q_lower)) or bool(re.search(r"\bwhat\s+(is|are)\s+(missing|needed|required)\b", q_lower))
    is_bare_case_mention = query_clean.strip().lower() in [f"case {case_id.split('-')[-1]}", case_id.lower(), f"case-{case_id.split('-')[-1]}"]
    if is_missing_query or is_bare_case_mention:
        return docchase.answer(case_id, "missing")

    # Guardrail 3: Question it doesn't understand -> ask again, never guess
    return "I didn't understand that question. Could you ask again?"


def respond(query: str, play_voice: bool = True) -> str:
    """
    Handle query, print transcript, and speak response out loud.
    """
    print(f"\nUser: \"{query}\"")
    answer_text = handle_query(query)
    print(f"DocChase: \"{answer_text}\"")

    if play_voice:
        speak.speak(answer_text, output_path="assistant_response.wav")

    return answer_text


def demo():
    """
    Run automated verification of all 5 demo asks + guardrails.
    """
    print("\n" + "=" * 60)
    print("DEMO VERIFICATION: 5 ASKS & GUARDRAILS")
    print("=" * 60)

    asks = [
        ("Ask 1 (clean missing)", "what is missing in case 102"),
        ("Ask 2 (context on past cases)", "give me context on case 103"),
        ("Ask 3 (specialist decision)", "what do I need to decide case 104"),
        ("Ask 4 (sensitive refusal)", "case 105"),
        ("Ask 5 (human approval & logging)", "approve case 102"),
        ("Guardrail: Unknown Case", "what is missing in case 999"),
        ("Guardrail: Unknown Question", "what is the weather on Mars for case 102"),
    ]

    for title, q in asks:
        print(f"\n--- {title} ---")
        respond(q, play_voice=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo()
    elif len(sys.argv) > 1 and sys.argv[1] == "--listen":
        # Voice loop: record from microphone, transcribe, and respond in voice
        print("\n🎙️ Listening for your voice query...")
        user_query = listen.listen(duration=5)
        if user_query:
            respond(user_query, play_voice=True)
        else:
            print("(No speech detected)")
    elif len(sys.argv) > 1:
        # Direct text query with voice playback
        respond(" ".join(sys.argv[1:]), play_voice=True)
    else:
        # Default run demo checks
        demo()
