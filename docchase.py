import csv
from pathlib import Path
import re
from typing import Optional


OFF_TOPIC_REPLY = "I can only help with open mortgage and healthcare exception cases. Ask me what's missing, the context, or what to decide."
UNCLEAR_REPLY = "sorry, say that again?"
VALID_QUESTION_TYPES = {"missing", "context", "decision", "approve", "domain", "document", "details"}


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
    # Approve
    if re.search(r"\b(approve|approved|accept|sign\s*off|manzoor|pasand|sweekar)\b|(मंजूर|मन्जूर|स्वीकृत|पास\s*करो)", t):
        return "approve"
    # Specific Details / Attributes / Sensitivity
    if re.search(r"\b(detail|details|specifics|specific|more\s+info|tell\s+me\s+more|elaborate|overview|summary|explain\s+(?:the\s+)?case|about\s+this\s+case|what\s+about\s+this\s+case|who\s+is\s+(?:the\s+)?(?:borrower|patient|member|person|client)|borrower|patient|confidence|evidence|missing\s+field|document\s+type|sensitive|sensitivity|why\s+(?:is\s+it\s+)?sensitive|kya\s+(?:yeh\s+)?sensitive|what\s+form|form\s+type|kaun\s+hai|batao|kya\s+hai|jaankari|vivaran)\b|(विवरण|जानकारी|विस्तार|बताओ|बताएं|कौन\s*है|स्कोर|सबूत|दस्तावेज|सेंसिटिव|संवेदनशील)", t):
        return "details"
    # Context
    if re.search(r"\b(context|history|similar|in[\s-]depth|background|past|itihaas|sandarbh|pehle)\b|(संदर्भ|इतिहास|पिछला|पूर्व)", t):
        return "context"
    # Decision
    if re.search(r"\b(decision|decide|action|proposal|faisla|nirnay|kadam)\b|(निर्णय|फैसला|कदम)", t):
        return "decision"
    # Missing
    if re.search(r"\b(missing|status|problem|what\'?s\s*wrong|what\s+is\s+wrong|what\'?s\s*(?:the\s*)?issue|what\s+is\s*(?:the\s*)?issue|what\'?s\s*missing|what\s+is\s*missing|documents?|kami|gayab)\b|(मिसिंग|कमी|गायब|क्या\s*कमी)", t):
        return "missing"
    # Domain
    if re.search(r"\b(domain|belong\s+to|what\s+domain|which\s+domain|mortgage\s+or\s+healthcare|category)\b|(डोमेन|श्रेणी)", t):
        return "domain"
    # Document
    if re.search(r"\b(pdf|packet|file|report|form|application|paystub|invoice)\b|(दस्तावेज़|दस्तावेज|फॉर्म|फ़ाइल|फाइल)", t):
        return "document"
    return None


CASE_METADATA = {
    "CASE-101": {
        "person_name": "John Doe",
        "person_role": "Borrower",
        "doc_title": "Uniform Residential Loan Application (Form 1003)",
        "missing_desc": "borrower signature on page 3",
        "exception_detail": "The borrower forgot to sign the Form 1003 application certification section.",
        "action_detail": "request the missing borrower signature",
        "risk_classification": "Standard Mortgage Review",
    },
    "CASE-102": {
        "person_name": "Sarah Miller",
        "person_role": "Borrower",
        "doc_title": "Wage and Tax Statement (Paystub / Form 1040)",
        "missing_desc": "recent 30-day paystub",
        "exception_detail": "The loan file is missing the most recent paystub required for income verification.",
        "action_detail": "request the missing paystub from the borrower",
        "risk_classification": "Standard Income Verification",
    },
    "CASE-103": {
        "person_name": "David Chen",
        "person_role": "Borrower",
        "doc_title": "Property Appraisal & Deed Reconciliation (CASE-005.pdf)",
        "missing_desc": "reconciled property siting address",
        "exception_detail": "The property address in the appraisal differs from the county deed record (street address and zip code conflict).",
        "action_detail": "propose a field correction to align appraisal and deed records",
        "risk_classification": "Standard Siting Discrepancy",
    },
    "CASE-104": {
        "person_name": "Elena Rostova",
        "person_role": "Borrower",
        "doc_title": "Foreign-Language Tax Packet (Form 2-NDFL / Foreign Asset Disclosure)",
        "missing_desc": "certified translation",
        "exception_detail": "Foreign-language tax declaration in Cyrillic flagged for low-confidence extraction requiring specialist translation review.",
        "action_detail": "route to a multilingual specialist reviewer",
        "risk_classification": "Specialist Review Required",
    },
    "CASE-105": {
        "person_name": "Arthur Pendelton",
        "person_role": "Borrower",
        "doc_title": "Unverified Transfer & Third-Party Escrow Wire Assignment",
        "missing_desc": "verified escrow wire authorization",
        "exception_detail": "Secondary quitclaim deed and third-party escrow wire assignment outside standard workflow flagged as suspicious.",
        "action_detail": "abstain from automated action; quarantined for human compliance review",
        "risk_classification": "Elevated Risk (Sensitive Case)",
    },
    "INS-101": {
        "person_name": "Robert Taylor",
        "person_role": "Patient",
        "doc_title": "Prior Authorization Request & Clinical Checklist (INS-H101.pdf)",
        "missing_desc": "supporting clinical consultation note for brain MRI",
        "exception_detail": "The prior authorization request is missing the required clinical note from the neurologist.",
        "action_detail": "request the missing clinical note from the provider",
        "risk_classification": "Standard Prior Authorization Review",
    },
    "INS-102": {
        "person_name": "Michael B. Peterson",
        "person_role": "Patient",
        "doc_title": "Post-Service Hospital Claim & Operative Report (CMS-1500 / UB-04, INS-H102.pdf)",
        "missing_desc": "itemized hospital bill",
        "exception_detail": "The post-service claim is missing the itemized hospital bill required for claims adjudication.",
        "action_detail": "request the missing itemized hospital bill",
        "risk_classification": "Standard Claims Adjudication",
    },
    "INS-103": {
        "person_name": "James Wilson",
        "person_role": "Policyholder",
        "doc_title": "Prior Authorization Request & Master Policy Record (INS-H103.pdf)",
        "missing_desc": "authoritative policyholder verification",
        "exception_detail": "Policyholder name on intake request differs from authoritative policy records; correction requires verification.",
        "action_detail": "verify authoritative records before proposing a field correction",
        "risk_classification": "Manual Verification Required",
    },
    "INS-104": {
        "person_name": "Emily Davis",
        "person_role": "Patient",
        "doc_title": "Supporting Medical Report & Extraction Review (INS-H104 / INS-H105)",
        "missing_desc": "standardized terminology interpretation",
        "exception_detail": "Supporting medical report contains unfamiliar clinical terminology with 0.42 extraction confidence.",
        "action_detail": "route to a specialist medical reviewer",
        "risk_classification": "Low Confidence Extraction Review",
    },
    "INS-105": {
        "person_name": "Michael Brown",
        "person_role": "Patient",
        "doc_title": "Special Investigations Unit (SIU) Forensic Review & Invoice Bundle (INS-H106.pdf)",
        "missing_desc": "unaltered provider invoice documentation",
        "exception_detail": "Claim bundle contains potentially altered invoices and arithmetic discrepancies with 0.35 confidence.",
        "action_detail": "abstain from automated action; quarantined to SIU with no automated action taken",
        "risk_classification": "Elevated Risk (Sensitive Case / SIU)",
    },
}


def format_case_details(case: dict, query_text: str = "") -> str:
    """
    Applies dynamic processing to return the explicit details of any mortgage
    or healthcare case, responding specifically to the user's inquiry or providing
    a comprehensive detailed summary.
    """
    cid = case.get("case_id", "").strip().upper()
    domain = case.get("domain", "").strip().lower()
    domain_title = "Mortgage Underwriting & Closing" if domain == "mortgage" else "Healthcare Prior Authorization & Claims"
    meta = CASE_METADATA.get(cid, {})

    person_name = meta.get("person_name") or ("Borrower" if domain == "mortgage" else "Patient")
    person_role = meta.get("person_role") or ("Borrower" if domain == "mortgage" else "Patient")
    doc_title = meta.get("doc_title") or case.get("document_type") or "Document Packet"
    missing_desc = meta.get("missing_desc") or case.get("missing_fields") or "required documentation"
    exception_text = case.get("exception_text") or meta.get("exception_detail") or "Standard operational exception flagged."
    action_detail = meta.get("action_detail") or case.get("expected_action", "").replace("_", " ")
    risk_class = meta.get("risk_classification") or ("Elevated Risk" if case.get("sensitive_case") else "Standard Operational Review")
    status = case.get("status", "New")
    confidence = case.get("confidence_score") or "0.95"
    try:
        conf_pct = f"{int(float(confidence) * 100)}%"
    except Exception:
        conf_pct = "95%"
    evidence_refs = case.get("evidence_references") or f"synthetic_doc_{cid}"
    supporting_evidence = case.get("supporting_evidence") or exception_text

    t = (query_text or "").lower()

    # 1. Specific inquiry: Person / Borrower / Patient
    if re.search(r"\b(who\s+is\s+(?:the\s+)?(?:borrower|patient|member|person|client)|borrower|patient|member|customer|person(?:'s)?\s+name|who\s+is\s+this|kaun\s+hai)\b|(बोरोअर|मरीज|पेशेंट|ग्राहक|नाम|व्यक्ति)", t):
        return f"For {cid}, the {person_role.lower()} is {person_name} in {domain_title}."

    # 2. Specific inquiry: Confidence score / Reliability
    if re.search(r"\b(confidence|confidence\s+score|score|how\s+confident|reliability|accuracy|kitna\s+score)\b|(कॉन्फिडेंस|स्कोर|सटीकता|विश्वसनीयता)", t):
        manual_str = "required" if case.get("manual_review_required") else "not required"
        return f"For {cid} ({person_name}), the extraction confidence score is {confidence} ({conf_pct}). Manual review is {manual_str}."

    # 3. Specific inquiry: Missing field / Missing target
    if re.search(r"\b(missing\s+field|missing\s+fields|specific\s+missing|what\s+field|which\s+field|missing\s+target\s+field|kya\s+missing|kya\s+kami)\b|(मिसिंग\s*फील्ड|क्या\s*कमी|गायब\s*दस्तावेज|दस्तावेज)", t):
        return f"In {cid} ({person_name}), the explicit missing field is {missing_desc} on {doc_title}. Exception: {exception_text}"

    # 4. Specific inquiry: Evidence / References / Supporting proof
    if re.search(r"\b(evidence|supporting\s+evidence|references?|proof|source\s+record|documentation|saboot|pramaan)\b|(सबूत|प्रमाण|रेफरेंस|दस्तावेजीकरण)", t):
        return f"Evidence for {cid} ({person_name}): Reference IDs: {evidence_refs}. Supporting evidence: {supporting_evidence}"

    # 5. Specific inquiry: Exception / Root cause / Why flagged
    if re.search(r"\b(exception|why\s+flagged|why\s+is\s+it\s+flagged|root\s+cause|flag|what\s+happened|specific\s+issue|what\s+went\s+wrong|kya\s+hua|gadbad)\b|(अपवाद|समस्या|कारण|दिक्कत|फ्लैग)", t):
        return f"The exception flagged for {cid} ({person_name}) is: '{exception_text}' on {doc_title}. Required action: {action_detail}."

    # 6. Specific inquiry: Sensitivity / Risk / Fraud
    if re.search(r"\b(sensitive|sensitivity|risk|fraud|quarantine|why\s+sensitive|dhokhadhadi|jhol)\b|(सेंसिटिव|संवेदनशील|जोखिम|धोखाधड़ी|फ्रॉड)", t):
        if case.get("sensitive_case"):
            return f"Case {cid} ({person_name}) is an elevated-risk sensitive case. {exception_text} Automated approval is blocked; the human reviewer decides."
        return f"Case {cid} ({person_name}) is standard sensitivity ({risk_class}). It is not a sensitive case."

    # 7. Specific inquiry: Document / Form type
    if re.search(r"\b(document\s+type|doc\s+type|which\s+form|what\s+form|form\s+number|form\s+type|kaunsa\s+form)\b|(दस्तावेज\s*का\s*प्रकार|फॉर्म\s*का\s*नाम|फॉर्म\s*टाइप)", t):
        return f"The governing document for {cid} ({person_name}) is {doc_title}. Domain: {domain_title}."

    # 8. General / Full explicit details
    sensitive_tag = " [Sensitive - Human Quarantined]" if case.get("sensitive_case") else ""
    return (
        f"Specific details for {cid} ({person_name}, {domain_title}): "
        f"Document: {doc_title}. "
        f"Exception: {exception_text} "
        f"Missing: {missing_desc}. "
        f"Assigned action: {action_detail}. "
        f"Status: {status}{sensitive_tag}. "
        f"Confidence score: {confidence} ({conf_pct})."
    )


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
def answer(case_number, question_type=None, last_case_id=None, query_text=None):
    open_cases = load_open_cases()
    past_cases = load_past_cases()

    raw_query = query_text or (str(case_number) if question_type is None else "")

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
        if not case and last_case_id and last_case_id in open_cases:
            case = open_cases[last_case_id]
        if not case:
            try:
                from pdf_inspector import INSPECTOR
                pdf_doc = INSPECTOR.get_pdf_for_query(raw, case_id=last_case_id)
                if pdf_doc and INSPECTOR.matches_pdf_query(raw, pdf_doc):
                    ans, _, _ = INSPECTOR.answer_pdf_query(raw, pdf_doc)
                    return ans
            except Exception:
                pass
            return OFF_TOPIC_REPLY

    domain = case["domain"]
    action_text = case["expected_action"].replace("_", " ")
    type_text = case["expected_type"].replace("_", " ")

    matching_past = [
        p for p in past_cases
        if p["domain"] == domain and p["expected_type"] == case["expected_type"]
    ]

    if q_type == "details":
        return format_case_details(case, raw_query)

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

    elif q_type in ("domain", "document"):
        domain_name = "Mortgage Underwriting & Closing" if domain == "mortgage" else "Healthcare Prior Authorization & Claims"
        return f"This document belongs to the {domain_name} domain. It is associated with {case['case_id']}, where {action_text} is expected."

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
