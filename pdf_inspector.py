import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import fitz  # PyMuPDF


class PDFInspector:
    def __init__(self, samples_dir: Optional[Path] = None):
        if samples_dir is None:
            samples_dir = Path(__file__).resolve().parent / "samples"
        self.samples_dir = samples_dir
        self.documents: Dict[str, Dict[str, Any]] = {}
        self._load_samples()

    def _load_samples(self):
        """
        Indexes all sample PDFs and synthetic document manifests.
        """
        if not self.samples_dir.exists():
            return

        # 1. Index all PDF files
        for pdf_path in sorted(self.samples_dir.glob("*.pdf")):
            try:
                doc = fitz.open(str(pdf_path))
                pages_text = [page.get_text() for page in doc]
                full_text = "\n".join(pages_text).strip()
                meta = self._parse_pdf_text(pdf_path.name, full_text)
                self.documents[pdf_path.name.lower()] = meta
                # Also index by base name (e.g. 'case-104')
                self.documents[pdf_path.stem.lower()] = meta
            except Exception as e:
                print(f"[PDFInspector] Error loading {pdf_path}: {e}")

        # 2. Add synthetic image references with rich structured metadata
        synthetic_docs = [
            {
                "filename": "synthetic_mortgage_application.png",
                "case_id": "CASE-101",
                "domain": "Mortgage Underwriting & Closing",
                "domain_key": "mortgage",
                "person_name": "John Doe",
                "doc_type": "Uniform Residential Loan Application (Form 1003)",
                "status": "Ready",
                "action": "request_missing_document",
                "missing_field": "borrower_signature",
                "exception_summary": "The borrower signature is missing on page 3 of the Form 1003 application.",
                "sensitivity": "Standard (sensitive_case: False)",
                "sensitive": False,
                "text": "Uniform Residential Loan Application Form 1003. Borrower: John Doe. Case ID: CASE-101. Domain: Mortgage. Missing borrower signature on page 3.",
            },
            {
                "filename": "synthetic_income_document.png",
                "case_id": "CASE-102",
                "domain": "Mortgage Underwriting & Closing",
                "domain_key": "mortgage",
                "person_name": "Sarah Miller",
                "doc_type": "Income Verification & Paystub (Form 1040)",
                "status": "Missing docs",
                "action": "request_missing_document",
                "missing_field": "recent_paystub",
                "exception_summary": "The loan file is missing the recent 30-day paystub to substantiate qualifying base income.",
                "sensitivity": "Standard (sensitive_case: False)",
                "sensitive": False,
                "text": "Income Verification Document Paystub Form 1040. Borrower: Sarah Miller. Case ID: CASE-102. Domain: Mortgage. Missing recent paystub.",
            },
            {
                "filename": "synthetic_property_address.png",
                "case_id": "CASE-103",
                "domain": "Mortgage Underwriting & Closing",
                "domain_key": "mortgage",
                "person_name": "David Chen",
                "doc_type": "Property Appraisal & Deed Verification",
                "status": "Ready",
                "action": "propose_field_correction",
                "missing_field": "property_siting_address",
                "exception_summary": "Appraisal address differs from deed records; street address and zip code conflict.",
                "sensitivity": "Standard (sensitive_case: False)",
                "sensitive": False,
                "text": "Property Appraisal Extract & Deed Comparison. Borrower: David Chen. Case ID: CASE-103. Domain: Mortgage. Address conflict between appraisal and deed.",
            },
        ]
        for s in synthetic_docs:
            self.documents[s["filename"].lower()] = s
            self.documents[s["case_id"].lower()] = s

    def _parse_pdf_text(self, filename: str, text: str) -> Dict[str, Any]:
        """
        Extracts structured fields from raw PDF text.
        """
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        def extract_regex(pattern, default=""):
            m = re.search(pattern, text, re.I | re.M)
            return m.group(1).strip() if m else default

        MANIFEST_MAP = {
            "case-005.pdf": {
                "title": "Cross-Source Property Siting Reconciliation (Appraisal vs Deed)",
                "doc_type": "Appraisal & Title Reconciliation",
                "person": "Robert M. Sterling",
                "domain": "Mortgage Underwriting & Closing",
                "case_id": "CASE-103",
                "action": "propose_field_correction",
            },
            "case-104.pdf": {
                "title": "Foreign-Language Tax Packet (Form 2-NDFL / Foreign Asset Disclosure)",
                "doc_type": "Foreign Tax Document & Translation",
                "person": "Elena Rostova",
                "domain": "Mortgage Underwriting & Closing",
                "case_id": "CASE-104",
                "action": "route_to_specialist",
            },
            "case-105.pdf": {
                "title": "Unverified Transfer & Third-Party Escrow Wire Assignment",
                "doc_type": "Suspicious Transfer Document",
                "person": "Arthur Pendelton",
                "domain": "Mortgage Underwriting & Closing",
                "case_id": "CASE-105",
                "action": "abstain",
            },
            "ins-h101.pdf": {
                "title": "Prior Authorization Request & Clinical Checklist",
                "doc_type": "Prior Auth & Clinical Checklist",
                "person": "Robert Taylor",
                "domain": "Healthcare Prior Authorization",
                "case_id": "INS-101",
                "action": "request_missing_document",
            },
            "ins-h102.pdf": {
                "title": "Post-Service Hospital Claim & Operative Report (CMS-1500 / UB-04)",
                "doc_type": "Operative Report & CMS-1500",
                "person": "Michael B. Peterson",
                "domain": "Healthcare Claims Processing",
                "case_id": "INS-102",
                "action": "request_missing_document",
            },
            "ins-h103.pdf": {
                "title": "Prior Authorization Request & Master Policy Record",
                "doc_type": "Prior Auth & Clinical Chart",
                "person": "James Wilson",
                "domain": "Healthcare Prior Authorization",
                "case_id": "INS-103",
                "action": "propose_field_correction",
            },
            "ins-h104.pdf": {
                "title": "CMS-1500 / UB-04 Claim Form and Policy Certificate",
                "doc_type": "UB-04 Inpatient Claim",
                "person": "Emily Davis",
                "domain": "Healthcare Claims Processing",
                "case_id": "INS-104",
                "action": "propose_field_correction",
            },
            "ins-h105.pdf": {
                "title": "Supporting Medical Report & Extraction Review",
                "doc_type": "Supporting Medical Report",
                "person": "Emily Davis",
                "domain": "Healthcare Medical Review",
                "case_id": "INS-104",
                "action": "route_to_specialist",
            },
            "ins-h106.pdf": {
                "title": "Special Investigations Unit (SIU) Forensic Review & Invoice Bundle",
                "doc_type": "Special Investigation Review",
                "person": "Michael Brown",
                "domain": "Healthcare Special Investigations & Compliance",
                "case_id": "INS-105",
                "action": "abstain",
            },
        }

        preset = MANIFEST_MAP.get(filename.lower(), {})

        # System Case ID
        case_id = preset.get("case_id") or extract_regex(r"(?:System Case ID|SYSTEM CASE ID)[:\s]+([A-Z0-9-]+)", "")
        if not case_id:
            m = re.search(r"\b(CASE-\d+|INS-H?\d+)\b", filename, re.I)
            case_id = m.group(1).upper() if m else filename.replace(".pdf", "").upper()

        canonical_case_id = re.sub(r"INS-H(\d+)", r"INS-\1", case_id)

        # Domain
        domain_raw = preset.get("domain") or extract_regex(r"(?:Domain|DOMAIN)[:\s]+([^\n\r]+)", "")
        if not domain_raw:
            for i, line in enumerate(lines):
                if line.upper() == "DOMAIN" and i + 1 < len(lines):
                    domain_raw = lines[i + 1]
                    break

        domain_clean = domain_raw.strip() if domain_raw else ("Mortgage Underwriting & Closing" if "CASE" in case_id else "Healthcare Prior Authorization & Claims")
        domain_key = "mortgage" if "mortgage" in domain_clean.lower() or "CASE" in case_id else "healthcare"

        # Document Type / Name
        doc_type = preset.get("doc_type") or extract_regex(r"(?:Document Name|Document Type|DOCUMENT TYPE)[:\s]+([^\n\r]+)", "")
        if not doc_type:
            doc_type = preset.get("title") or filename.replace(".pdf", "")

        # Person (Borrower or Patient)
        person_name = preset.get("person") or ""
        if not person_name:
            borrower_match = re.search(r"\bBorrower:\s*([A-Za-z\s\.]+?)(?:\s*\(|$)", text)
            patient_match = re.search(r"\bPatient Name:\s*([A-Za-z\s\.]+?)(?:\s*\(|$)", text)
            if borrower_match:
                person_name = borrower_match.group(1).strip()
            elif patient_match:
                person_name = patient_match.group(1).strip()

        # Status
        status = extract_regex(r"(?:Lifecycle Status|LIFECYCLE STATUS|Underwriting Status)[:\s]+([^\n\r]+)", "New")
        if not status:
            for i, line in enumerate(lines):
                if line.upper() == "LIFECYCLE STATUS" and i + 1 < len(lines):
                    status = lines[i + 1]
                    break

        # Sensitivity
        sensitivity = extract_regex(r"(?:Sensitivity|SENSITIVITY|Sensitivity Classification)[:\s]+([^\n\r]+)", "Standard")
        if not sensitivity:
            for i, line in enumerate(lines):
                if line.upper() == "SENSITIVITY" and i + 1 < len(lines):
                    sensitivity = lines[i + 1]
                    break
        sensitive = "true" in sensitivity.lower() or "elevated" in sensitivity.lower() or "sensitive_case: true" in text.lower()

        # Assigned Action
        action = extract_regex(r"(?:Assigned Action|ASSIGNED ACTION)[:\s]+([a-z0-9_]+)", "review")
        if not action or action == "review":
            for i, line in enumerate(lines):
                if line.upper() == "ASSIGNED ACTION" and i + 1 < len(lines):
                    action = lines[i + 1]
                    break

        # Missing Target Field
        missing_field = extract_regex(r"(?:Missing Target Field|MISSING TARGET FIELD)[:\s]+([^\n\r]+)", "None")
        if not missing_field or missing_field == "None":
            for i, line in enumerate(lines):
                if line.upper() == "MISSING TARGET FIELD" and i + 1 < len(lines):
                    missing_field = lines[i + 1]
                    break

        # Evidence / Recommendation / Exception Summary
        exception_summary = ""
        for heading in ["DOCUMENT EXTRACTION EXCEPTION", "LOW CONFIDENCE EXTRACTION EXCEPTION", "SUSPICIOUS DOCUMENT TRANSFER ALERT", "Section 1", "Section 2"]:
            if heading in text:
                parts = text.split(heading, 1)
                if len(parts) > 1:
                    snippet = parts[1].strip().split("\n\n")[0].replace("\n", " ").strip()
                    if snippet and len(snippet) > 20:
                        exception_summary = snippet[:220]
                        break

        if not exception_summary:
            exception_summary = f"{doc_type} with assigned action {action.replace('_', ' ')}."

        return {
            "filename": filename,
            "case_id": case_id,
            "canonical_case_id": canonical_case_id,
            "domain": domain_clean,
            "domain_key": domain_key,
            "person_name": person_name.strip(),
            "doc_type": doc_type.strip(),
            "status": status.strip(),
            "sensitivity": sensitivity.strip(),
            "sensitive": sensitive,
            "action": action.strip(),
            "missing_field": missing_field.strip(),
            "exception_summary": exception_summary,
            "text": text,
        }

    def get_pdf_for_query(
        self,
        query: str,
        case_id: Optional[str] = None,
        sample_id: Optional[str] = None,
        sample_file: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the most relevant PDF/document given the query text and contextual hints.
        """
        raw = query.lower()

        # 1. Explicit filename or sample_file
        if sample_file and sample_file.lower() in self.documents:
            return self.documents[sample_file.lower()]

        # 2. Explicit sample_id
        if sample_id and sample_id.lower() in self.documents:
            return self.documents[sample_id.lower()]

        # 3. Direct mention in query string (e.g. 'case-104', 'ins-h101', 'case-005.pdf')
        for doc_key, doc_data in self.documents.items():
            if doc_key in raw:
                return doc_data

        # 4. Numeric matching in text (e.g., '104' -> CASE-104 or INS-104 based on domain)
        num_match = re.search(r"\b(?:case|ins|packet|doc|pdf)?[-\s]?h?(\d{3})\b", raw, re.I)
        if num_match:
            num = num_match.group(1)
            candidates = []
            for doc_key, doc_data in self.documents.items():
                if num in doc_key:
                    candidates.append(doc_data)
            if candidates:
                if domain:
                    dom_clean = domain.strip().lower()
                    for c in candidates:
                        if c.get("domain_key") == dom_clean:
                            return c
                return candidates[0]

        # 5. Fallback to session case_id
        if case_id:
            cid_clean = case_id.strip().lower()
            if cid_clean in self.documents:
                return self.documents[cid_clean]
            # Try matching digits (e.g. CASE-104 -> case-104.pdf)
            for doc_key, doc_data in self.documents.items():
                if doc_data.get("case_id", "").lower() == cid_clean or doc_data.get("canonical_case_id", "").lower() == cid_clean:
                    return doc_data

        # 6. Fallback to active domain default sample
        if domain:
            dom = domain.strip().lower()
            if dom == "mortgage" and "case-104.pdf" in self.documents:
                return self.documents["case-104.pdf"]
            elif dom == "healthcare" and "ins-h101.pdf" in self.documents:
                return self.documents["ins-h101.pdf"]

        # 7. Fallback to default document (CASE-104.pdf or first available)
        if "case-104.pdf" in self.documents:
            return self.documents["case-104.pdf"]
        if self.documents:
            return next(iter(self.documents.values()))

        return None

    def matches_pdf_query(self, query: str, doc_data: Dict[str, Any], has_explicit_sample: bool = False) -> bool:
        """
        Determines whether the query is specifically asking about the PDF/document, domain, or contents within it.
        """
        raw = query.lower()

        # 1. Explicit domain questions ("what domain does this belong to", "which domain", etc.)
        if re.search(r"\b(domain|which\s+domain|what\s+domain|what\s+(?:does\s+)?(?:this|that|the\s+pdf|the\s+document|it)\s+belong\s+to|what\s+domain\s+does)\b", raw, re.I):
            return True

        # 2. Explicit document/PDF mentions
        if re.search(r"\b(pdf|document|sample\s*file|packet|paper|report|invoice|form\s*1003|cms-1500|ub-04|2-ndfl)\b", raw, re.I):
            return True

        # 3. Direct mention of sample filenames
        for sample_key in ["case-005", "case-104", "case-105", "ins-h101", "ins-h102", "ins-h103", "ins-h104", "ins-h105", "ins-h106", "synthetic_"]:
            if sample_key in raw:
                return True

        # 4. If an explicit sample was selected in workbench and query asks to inspect/summarize it
        if has_explicit_sample:
            if re.search(r"\b(summarize|summary|overview|explain|who\s+is\s+the|what\s+is\s+the\s+date|cpt|icd)\b", raw, re.I):
                return True

        return False

    def answer_pdf_query(self, query: str, doc: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Generates a natural, grounded answer to the query based directly on the PDF content.
        Returns: (answer_text, question_type, case_id)
        """
        t = query.lower()
        filename = doc.get("filename", "the document")
        domain = doc.get("domain", "Mortgage")
        domain_key = doc.get("domain_key", "mortgage")
        case_id = doc.get("canonical_case_id") or doc.get("case_id", "CASE")
        doc_type = doc.get("doc_type", "Document")
        person = doc.get("person_name", "")
        person_str = f" for {person}" if person else ""
        action_clean = doc.get("action", "review").replace("_", " ")
        missing_clean = doc.get("missing_field", "None").replace("_", " ")

        # 1. Domain Question ("what domain does this belong to", "which domain", etc.)
        if re.search(r"\b(domain|which\s+domain|what\s+domain|belong\s+to|mortgage\s+or\s+healthcare|category)\b", t):
            ans = (
                f"Based on the PDF ({filename}), this document belongs to the {domain} domain. "
                f"It is a {doc_type} associated with {case_id}{person_str}, with assigned action: {action_clean}."
            )
            return ans, "domain", case_id

        # 2. What's Missing / Missing Field
        if re.search(r"\b(missing|what\'?s\s*missing|what\s+is\s+missing|missing\s+target\s+field|deficiency)\b", t):
            if missing_clean.lower() != "none":
                ans = f"In the PDF ({filename}), the missing target field is: {missing_clean}. Exception: {doc.get('exception_summary', '')}"
            else:
                ans = f"In the PDF ({filename}), no standard field is missing, but an exception was flagged: {doc.get('exception_summary', '')}"
            return ans, "missing", case_id

        # 3. Action / Decision / Proposal
        if re.search(r"\b(action|decision|decide|propos(?:al|e)|what\s+should\s+be\s+done|next\s+step|resolution)\b", t):
            ans = (
                f"In the PDF ({filename}) for {case_id}, the assigned action is {action_clean}. "
                f"Status: {doc.get('status', 'Pending review')}, but the human decides."
            )
            return ans, "decision", case_id

        # 4. Sensitivity / Fraud / Risk
        if re.search(r"\b(sensitive|risk|fraud|alert|quarantine|human\s+review)\b", t):
            if doc.get("sensitive"):
                ans = f"This PDF ({filename}) is an elevated-risk sensitive case ({doc.get('sensitivity')}). Automation abstains, and the human decides."
            else:
                ans = f"This PDF ({filename}) is classified as standard sensitivity ({doc.get('sensitivity')})."
            return ans, "context", case_id

        # 5. Borrower / Patient / Member
        if re.search(r"\b(borrower|patient|member|person|who\s+is\s+this|client|customer)\b", t):
            role = "Borrower" if domain_key == "mortgage" else "Patient"
            if person:
                ans = f"According to the PDF ({filename}), the {role.lower()} listed is {person} on {case_id}."
            else:
                ans = f"According to the PDF ({filename}), the case reference is {case_id} in {domain}."
            return ans, "context", case_id

        # 6. Summary / Overview / What is this document / What does it say
        if re.search(r"\b(summar(?:y|ize)|what\s+is\s+(?:this|the\s+pdf|the\s+document)|overview|tell\s+me\s+about\s+(?:this|the\s+pdf)|what\s+does\s+(?:it|this)\s+say)\b", t):
            ans = (
                f"This document is {filename} from the {domain} domain for {case_id}{person_str}. "
                f"Document type: {doc_type}. Summary: {doc.get('exception_summary', '')}"
            )
            return ans, "context", case_id

        # 7. Generic Extractive Fallback: Search lines in the PDF
        lines = [l.strip() for l in doc.get("text", "").splitlines() if l.strip()]
        matched_lines = []
        words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", t) if w not in {"what", "tell", "show", "from", "with", "this", "that", "please", "about"}]
        for line in lines:
            if any(w in line.lower() for w in words):
                matched_lines.append(line)
                if len(matched_lines) >= 3:
                    break

        if matched_lines:
            snippet = "; ".join(matched_lines)
            ans = f"According to the PDF ({filename}): {snippet}."
            return ans, "document_qa", case_id

        # Default fallback: structured document description
        ans = (
            f"From the PDF ({filename}): {doc_type} for {case_id}{person_str} in {domain}. "
            f"Assigned action: {action_clean}."
        )
        return ans, "document_qa", case_id


# Global singleton instance
INSPECTOR = PDFInspector()
