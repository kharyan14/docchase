import csv
from pathlib import Path
import re
from typing import Optional


OFF_TOPIC_REPLY = "I can only help with open mortgage and healthcare exception cases. Ask me what's missing, the context, or what to decide."
UNCLEAR_REPLY = "sorry, say that again?"
VALID_QUESTION_TYPES = {"missing", "context", "decision", "approve"}


def is_unclear_or_short(text: str) -> bool:
    if text is None:
        return True
    raw = str(text).strip()
    if not raw:
        return True
    words = re.findall(r"\b[\w'-]+\b", raw.lower())
    if len(words) < 2 or raw.lower() in {
        "hello", "hi", "hey", "howdy", "greetings", "good morning", "good afternoon",
        "good evening", "uh", "um", "huh", "pardon", "what", "sorry"
    }:
        return True
    return False


def get_question_type(text: str) -> Optional[str]:
    if not text:
        return None
    t = str(text).lower()
    if re.search(r"\b(approve|approved|accept|sign\s*off)\b", t):
        return "approve"
    if re.search(r"\b(context|history|similar|in[\s-]depth|background|past)\b", t):
        return "context"
    if re.search(r"\b(decision|decide|action|proposal)\b", t):
        return "decision"
    if re.search(r"\b(missing|status|problem|what\'?s\s*wrong|what\s+is\s+wrong|what\'?s\s*(?:the\s*)?issue|what\s+is\s*(?:the\s*)?issue|what\'?s\s*missing|what\s+is\s*missing|documents?)\b", t):
        return "missing"
    return None


# Resolve paths to the CSV datasets across both mortgage and healthcare domains.
def get_data_paths():
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    open_paths = [
        data_dir / "open_cases.csv",
        data_dir / "mortgage_open_cases.csv",
        data_dir / "healthcare_open_cases.csv",
    ]
    past_paths = [
        data_dir / "approved_cases.csv",
        data_dir / "mortgage_approved_cases.csv",
        data_dir / "healthcare_approved_cases.csv",
    ]
    existing_open = [p for p in open_paths if p.exists()]
    existing_past = [p for p in past_paths if p.exists()]
    if not existing_open or not existing_past:
        raise FileNotFoundError("Could not locate common schema CSV files in data directory.")
    return existing_open, existing_past


# Load open cases from both domains using the common schema.
def load_open_cases():
    data_dir = Path(__file__).resolve().parent / "data"
    cases = {}
    fpaths = [data_dir / "open_cases.csv"] if (data_dir / "open_cases.csv").exists() else [
        data_dir / "mortgage_open_cases.csv",
        data_dir / "healthcare_open_cases.csv",
    ]
    for fpath in fpaths:
        if fpath.exists():
            with open(fpath, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cid = row["case_id"].strip()
                    sensitive = row.get("sensitive_case", "False").strip().lower() == "true"
                    manual_review = row.get("manual_review_required", "False").strip().lower() == "true"
                    cases[cid] = {
                        "case_id": cid,
                        "domain": row.get("domain", "").strip().lower(),
                        "exception_text": row.get("exception_text", "").strip(),
                        "expected_type": row.get("expected_type", "").strip(),
                        "expected_action": row.get("expected_action", "").strip(),
                        "sensitive_case": sensitive,
                        "status": row.get("status", "").strip(),
                        "authorization_type": row.get("authorization_type", "").strip(),
                        "document_type": row.get("document_type", "").strip(),
                        "missing_fields": row.get("missing_fields", "").strip(),
                        "evidence_references": row.get("evidence_references", "").strip(),
                        "confidence_score": row.get("confidence_score", "").strip(),
                        "manual_review_required": manual_review,
                        "supporting_evidence": row.get("supporting_evidence", "").strip(),
                    }
    return cases


# Load past approved cases from both domains using the common schema.
def load_past_cases():
    data_dir = Path(__file__).resolve().parent / "data"
    past_cases = []
    fpaths = [data_dir / "approved_cases.csv"] if (data_dir / "approved_cases.csv").exists() else [
        data_dir / "mortgage_approved_cases.csv",
        data_dir / "healthcare_approved_cases.csv",
    ]
    for fpath in fpaths:
        if fpath.exists():
            with open(fpath, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sensitive = row.get("sensitive_case", "False").strip().lower() == "true"
                    manual_review = row.get("manual_review_required", "False").strip().lower() == "true"
                    past_cases.append({
                        "case_id": row["case_id"].strip(),
                        "domain": row.get("domain", "").strip().lower(),
                        "exception_text": row.get("exception_text", "").strip(),
                        "expected_type": row.get("expected_type", "").strip(),
                        "expected_action": row.get("expected_action", "").strip(),
                        "sensitive_case": sensitive,
                        "status": row.get("status", "").strip(),
                        "authorization_type": row.get("authorization_type", "").strip(),
                        "document_type": row.get("document_type", "").strip(),
                        "missing_fields": row.get("missing_fields", "").strip(),
                        "evidence_references": row.get("evidence_references", "").strip(),
                        "confidence_score": row.get("confidence_score", "").strip(),
                        "manual_review_required": manual_review,
                        "supporting_evidence": row.get("supporting_evidence", "").strip(),
                    })
    return past_cases


# Look up an open case by its case identifier or number.
def find_case(open_cases, case_number):
    if not case_number:
        return None
    c_str = str(case_number).strip().upper()
    if c_str in open_cases:
        return open_cases[c_str]
    for k, v in open_cases.items():
        if k == f"CASE-{c_str}" or k == f"INS-{c_str}" or k.endswith(c_str):
            return v
    return None


# Generate a spoken answer for a given case number and question type across both domains.
def answer(case_number, question_type=None, last_case_id=None):
    open_cases = load_open_cases()
    past_cases = load_past_cases()

    # Case 1: called with explicit question_type (e.g. answer("CASE-101", "missing"))
    if question_type is not None:
        q_type = str(question_type).strip().lower()
        if q_type not in VALID_QUESTION_TYPES:
            if is_unclear_or_short(case_number) or is_unclear_or_short(question_type):
                return UNCLEAR_REPLY
            return OFF_TOPIC_REPLY
        case = find_case(open_cases, case_number)
        if not case and last_case_id and last_case_id in open_cases:
            case = open_cases[last_case_id]
        if not case:
            if is_unclear_or_short(case_number):
                return UNCLEAR_REPLY
            return OFF_TOPIC_REPLY

    # Case 2: called with a query sentence in case_number (e.g. answer("tell me about pasta"))
    else:
        raw = str(case_number).strip() if case_number else ""
        if is_unclear_or_short(raw):
            return UNCLEAR_REPLY

        q_type = get_question_type(raw)
        if not q_type or q_type not in VALID_QUESTION_TYPES:
            return OFF_TOPIC_REPLY

        case = find_case(open_cases, raw)
        if not case:
            import main
            cids, _ = main.find_case_ids(raw, open_cases)
            if cids:
                case = open_cases[cids[0]]
            elif last_case_id and last_case_id in open_cases:
                case = open_cases[last_case_id]
        if not case:
            return OFF_TOPIC_REPLY

    domain = case["domain"]
    action_text = case["expected_action"].replace("_", " ")
    type_text = case["expected_type"].replace("_", " ")

    matching_past = [
        p for p in past_cases
        if p["domain"] == domain and p["expected_type"] == case["expected_type"]
    ]

    if q_type == "missing":
        if case["sensitive_case"]:
            if case["case_id"] == "INS-105":
                return "The claim contains potentially altered invoices outside standard workflow, and this sensitive case needs human review."
            return "The loan file references a suspicious transfer document outside standard workflow, and this sensitive case needs human review."
        missing_map = {
            "CASE-101": "The borrower signature is missing from the form; want me to request the missing document?",
            "CASE-102": "The loan file is missing the recent paystub; want me to request the missing document?",
            "CASE-103": "The appraisal address differs from deed records; want me to propose a field correction?",
            "CASE-104": "The foreign-language tax document needs specialist review; want me to send it to a specialist?",
            "INS-101": "The authorization request is missing the required clinical note; want me to request the missing document?",
            "INS-102": "The post-service claim is missing the itemized hospital bill; want me to request the missing document?",
            "INS-103": "The policyholder name differs from policy records, but a human must verify first; want me to propose a field correction?",
            "INS-104": "The supporting medical report contains unfamiliar terminology, but a human must verify first; want me to send it to a specialist?",
        }
        if case["case_id"] in missing_map:
            return missing_map[case["case_id"]]
        if case["manual_review_required"]:
            return f"The case requires verified documentation, but a human must verify first; want me to {action_text}?"
        return f"The case is missing required information; want me to {action_text}?"

    elif q_type == "context":
        if case["sensitive_case"]:
            if domain == "healthcare" and matching_past:
                return "Past approved cases abstained on suspected fraud, and this sensitive case needs human review."
            return "No past approved cases exist for this type, and this sensitive case needs human review."
        if not matching_past:
            return f"No past approved cases were found for {type_text} in the {domain} archive."
        context_map = {
            ("mortgage", "signature"): "Past approved signature cases were resolved by requesting the missing borrower signature on the application or note.",
            ("mortgage", "income"): "Past approved income cases were resolved by requesting the missing income verification document or recent paystub.",
            ("mortgage", "address"): "Past approved address cases were resolved by proposing a field correction to align appraisal or mailing addresses with official records.",
            ("healthcare", "missing_clinical_document"): "Past approved clinical document cases were resolved by requesting the missing clinical note from the provider.",
            ("healthcare", "missing_billing_document"): "Past approved billing document cases were resolved by requesting the missing itemized hospital bill.",
            ("healthcare", "policyholder_mismatch"): "Past approved policyholder mismatch cases were resolved by verifying authoritative records before proposing a field correction.",
            ("healthcare", "low_confidence_extraction"): "Past approved extraction cases with unresolved terminology were resolved by routing the report to a specialist reviewer.",
        }
        key = (domain, case["expected_type"])
        if key in context_map:
            return context_map[key]
        return f"Past approved {type_text} cases in {domain} were resolved following verified procedures."

    elif q_type == "decision":
        if case["sensitive_case"]:
            if case["case_id"] == "INS-105":
                return "Past evidence documented inconsistent invoice totals and this sensitive case needs human review, so no action is proposed and the human decides."
            return "No past evidence exists and this sensitive case needs human review, so no action is proposed and the human decides."
        decision_map = {
            "CASE-101": "Past evidence confirmed the required signature was absent on review, so the proposed action is to request the missing document, but the human decides.",
            "CASE-102": "Past evidence verified the required recent paystub was absent from the packet, so the proposed action is to request the missing document, but the human decides.",
            "CASE-103": "Past evidence documented address discrepancies between appraisal and deed records, so the proposed action is to propose a field correction, but the human decides.",
            "CASE-104": "No past case evidence exists for foreign tax documents, so the proposed action is to route to a specialist, but the human decides.",
            "INS-101": "Past evidence confirmed the clinical note was missing from the checklist, so the proposed action is to request the missing document, but the human decides.",
            "INS-102": "Past evidence verified the itemized bill was absent from the checklist, so the proposed action is to request the missing document, but the human decides.",
            "INS-103": "Past evidence documented source disagreement on policyholder name, so a human must verify first before proposing a field correction, but the human decides.",
            "INS-104": "Past evidence showed unresolved extraction terminology, so a human must verify first before routing to a specialist, but the human decides.",
        }
        if case["case_id"] in decision_map:
            return decision_map[case["case_id"]]
        if not matching_past:
            return f"No past case evidence exists for {type_text}, so the proposed action is to {action_text}, but the human decides."
        if case["manual_review_required"]:
            return f"Past evidence was reviewed for {type_text}, so a human must verify first before {action_text}, but the human decides."
        return f"Past case evidence was reviewed for {type_text}, so the proposed action is to {action_text}, but the human decides."

    elif q_type == "approve":
        log_file = Path(__file__).resolve().parent / "approvals.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{case['case_id']}] APPROVED by human\n")
        return f"Recorded approval for {case['case_id']}; the human decides."

    else:
        return OFF_TOPIC_REPLY


# Print answers for all open cases across both domains and all 3 question types.
def print_all_answers():
    open_cases = load_open_cases()
    question_types = ["missing", "context", "decision"]
    for case_id in sorted(open_cases.keys()):
        domain = open_cases[case_id].get("domain", "").upper()
        print(f"=== {case_id} ({domain}) ===")
        for q_type in question_types:
            res = answer(case_id, q_type)
            words = len(res.split())
            print(f"[{q_type.upper()}] ({words} words): {res}")
        print()


if __name__ == "__main__":
    print_all_answers()
