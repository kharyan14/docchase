import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests

import docchase
import listen
import main
import speak

# Ensure environment variables (.env) are loaded on the server
speak.load_env_file()

app = FastAPI(title="DocChase VoiceOps Server")

# Allow CORS for local development & browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    text: Optional[str] = ""
    domain: Optional[str] = None
    last_case_id: Optional[str] = None


class SpeakRequest(BaseModel):
    text: str


@app.get("/cases")
async def get_cases(domain: Optional[str] = None):
    """
    Returns list of open cases from docchase.py filtered optionally by domain.
    """
    open_cases = docchase.load_open_cases()
    names_map = {
        "CASE-101": "John Doe",
        "CASE-102": "Sarah Miller",
        "CASE-103": "David Chen",
        "CASE-104": "Elena Rostova",
        "CASE-105": "Arthur Pendelton",
        "INS-101": "Robert Taylor",
        "INS-102": "Maria Garcia",
        "INS-103": "James Wilson",
        "INS-104": "Emily Davis",
        "INS-105": "Michael Brown",
    }
    results = []
    dom_filter = domain.strip().lower() if domain else None
    for cid, case in open_cases.items():
        case_domain = case.get("domain", "").lower()
        if dom_filter and case_domain != dom_filter:
            continue

        if case.get("sensitive_case"):
            chip = "Sensitive"
            chip_type = "sensitive"
        elif case.get("status") == "Resolved":
            chip = "Ready"
            chip_type = "ready"
        elif case.get("expected_action") == "request_missing_document":
            chip = "Missing docs"
            chip_type = "missing"
        else:
            chip = "Ready"
            chip_type = "ready"

        name = names_map.get(cid, "Borrower" if case_domain == "mortgage" else "Patient")

        results.append({
            "case_id": cid,
            "domain": case_domain,
            "name": name,
            "status": chip,
            "status_chip": chip,
            "status_chip_type": chip_type,
            "sensitive": bool(case.get("sensitive_case")),
            "exception_text": case.get("exception_text", ""),
            "expected_type": case.get("expected_type", ""),
            "expected_action": case.get("expected_action", ""),
        })
    return results


@app.post("/ask")
async def ask_question(req: AskRequest):
    """
    Multi-turn /ask with off-topic guardrails, session memory, case switching,
    follow-up prompts, and sensitive case guardrails.
    Returns: {"case_id": ..., "question_type": ..., "answer": ...}
    """
    raw_text = (req.text or "").strip()
    open_cases = docchase.load_open_cases()
    domain = (req.domain or "").strip().lower()
    last_cid = (req.last_case_id or "").strip().upper() if req.last_case_id else None
    if last_cid and last_cid not in open_cases:
        last_cid = None

    # Guardrail 1: Very short or unclear transcript
    if docchase.is_unclear_or_short(raw_text):
        return {
            "case_id": last_cid,
            "question_type": None,
            "answer": docchase.UNCLEAR_REPLY,
        }

    # Guardrail 2: Question must match one of the 4 question types (missing, context, decision, approve)
    q_type = docchase.get_question_type(raw_text)
    if not q_type or q_type not in docchase.VALID_QUESTION_TYPES:
        return {
            "case_id": last_cid,
            "question_type": None,
            "answer": docchase.OFF_TOPIC_REPLY,
        }

    # Guardrail 3: Check if user specified an unknown case (e.g. case 999, ins 500)
    unknown_match = re.search(r"\b(?:case|ins|ils)[-\s]?h?(\d+)\b", raw_text, re.I)
    if unknown_match:
        num = unknown_match.group(1)
        if f"CASE-{num}" not in open_cases and f"INS-{num}" not in open_cases:
            return {
                "case_id": last_cid,
                "question_type": None,
                "answer": docchase.OFF_TOPIC_REPLY,
            }

    digits_in_text = re.findall(r"\b\d{3,}\b", raw_text)
    if digits_in_text and not any(f"CASE-{d}" in open_cases or f"INS-{d}" in open_cases for d in digits_in_text):
        return {
            "case_id": last_cid,
            "question_type": None,
            "answer": docchase.OFF_TOPIC_REPLY,
        }

    # Find case IDs in text
    case_ids, clarification = main.find_case_ids(raw_text, open_cases)

    # Disambiguate if domain is explicitly selected
    if clarification and domain:
        digit_match = re.search(r"\b(\d+)\b", raw_text)
        if digit_match:
            num = digit_match.group(1)
            if domain == "mortgage" and f"CASE-{num}" in open_cases:
                case_ids = [f"CASE-{num}"]
                clarification = None
            elif domain == "healthcare" and f"INS-{num}" in open_cases:
                case_ids = [f"INS-{num}"]
                clarification = None

    switched = False
    if case_ids:
        case_id = case_ids[0]
        if last_cid and case_id != last_cid:
            switched = True
    else:
        # Rule: in scope only if it names a known case id OR uses session last_case_id
        # Never fall back to a default case
        if not last_cid or last_cid not in open_cases:
            return {
                "case_id": None,
                "question_type": None,
                "answer": docchase.OFF_TOPIC_REPLY,
            }
        case_id = last_cid

    if clarification:
        answer_text = clarification
    else:
        case = open_cases[case_id]
        # Guardrail: sensitive cases never approve, human decides
        if q_type == "approve" and case.get("sensitive_case"):
            answer_text = "This is a sensitive case and cannot be approved. No action is taken, the human decides."
        else:
            answer_text = docchase.answer(case_id, q_type)

        # Follow-ups: after a missing-docs answer, the assistant ends with a short spoken prompt
        if q_type == "missing":
            if not answer_text.endswith("Want the context or the decision?"):
                answer_text = f"{answer_text} Want the context or the decision?"

        # If they name a new case, switch to it and say so
        if switched:
            answer_text = f"Switched to {case_id}. {answer_text}"

        # If more than one case id is found, answer the first and append guidance
        if len(case_ids) > 1:
            answer_text = f"{answer_text} One case at a time, ask about the next one after this."

    return {
        "case_id": case_id,
        "question_type": q_type,
        "answer": answer_text,
    }


@app.post("/voice/speak")
async def voice_speak(req: SpeakRequest):
    """
    Calls speak.py to synthesize audio bytes via SLNG TTS and returns the audio bytes.
    """
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    output_wav = Path(__file__).resolve().parent / "server_speak.wav"
    try:
        # Calls speak.py without playing on server speakers
        speak.speak(text, output_path=str(output_wav), play=False)
        with open(output_wav, "rb") as f:
            audio_bytes = f.read()
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)):
    """
    Accepts an audio file upload (browser recording), sends it to the SLNG
    speech-to-text model (slng/deepgram/nova:3-en), and returns {"text": "..."}.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file provided.")

    keys_to_try = speak.get_active_keys()
    if not keys_to_try:
        raise HTTPException(status_code=500, detail="SLNG API key not configured on server.")

    base_url = os.environ.get("VOICEAI_BASE_URL", "https://in.api.slng.ai").rstrip("/")
    endpoint = f"{base_url}/v1/stt/slng/deepgram/nova:3-en"

    raw_content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    if "webm" in raw_content_type:
        mime = "audio/webm"
        fname = "recording.webm"
    elif "wav" in raw_content_type:
        mime = "audio/wav"
        fname = "recording.wav"
    elif "ogg" in raw_content_type:
        mime = "audio/ogg"
        fname = "recording.ogg"
    elif "mp4" in raw_content_type or "m4a" in raw_content_type:
        mime = "audio/mp4"
        fname = "recording.mp4"
    else:
        mime = raw_content_type
        fname = audio.filename or "recording.webm"

    def extract_transcript(data_dict):
        if "transcript" in data_dict and data_dict["transcript"]:
            return data_dict["transcript"].strip()
        channels = data_dict.get("results", {}).get("channels", [])
        if channels and "alternatives" in channels[0]:
            return channels[0]["alternatives"][0].get("transcript", "").strip()
        return ""

    response = None
    last_err = None

    for idx, key in enumerate(keys_to_try):
        try:
            res = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}"},
                files={"audio": (fname, audio_bytes, mime)},
                timeout=30,
            )

            # Fallback: if SLNG rejected format or codec, convert to 16kHz mono WAV via ffmpeg
            if not res.ok and res.status_code not in (429, 401, 403):
                temp_in = Path(__file__).resolve().parent / "temp_browser_audio"
                temp_out = Path(__file__).resolve().parent / "temp_browser_audio.wav"
                try:
                    temp_in.write_bytes(audio_bytes)
                    conv = subprocess.run(
                        ["ffmpeg", "-y", "-i", str(temp_in), "-ar", "16000", "-ac", "1", str(temp_out)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if conv.returncode == 0 and temp_out.exists():
                        with open(temp_out, "rb") as wf:
                            res = requests.post(
                                endpoint,
                                headers={"Authorization": f"Bearer {key}"},
                                files={"audio": ("recording.wav", wf, "audio/wav")},
                                timeout=30,
                            )
                finally:
                    if temp_in.exists():
                        temp_in.unlink()
                    if temp_out.exists():
                        temp_out.unlink()

            if res.status_code in (429, 402, 403, 502, 503, 504) and len(keys_to_try) > 1 and idx < len(keys_to_try) - 1:
                speak.mark_key_rate_limited(key, cooldown_seconds=60.0)
                last_err = res
                continue

            res.raise_for_status()
            response = res
            break
        except requests.exceptions.RequestException as e:
            last_err = e
            if idx < len(keys_to_try) - 1:
                continue
            raise HTTPException(status_code=502, detail=f"Speech-to-text service error: {str(e)}")

    if response is None:
        raise HTTPException(status_code=502, detail=f"Speech-to-text failed across all keys: {str(last_err)}")

    data = response.json()
    transcript = extract_transcript(data)
    return {"text": transcript}



@app.post("/documents/upload")
async def upload_document():
    """
    Returns a clear 501 message 'document extraction not built yet' and does nothing else.
    """
    return JSONResponse(
        status_code=501,
        content={"message": "document extraction not built yet", "detail": "document extraction not built yet"},
    )


@app.get("/api/samples")
async def get_samples(domain: Optional[str] = None):
    """
    Returns list of sample documents shared in the project with thumbnail previews
    and case mappings.
    """
    samples_data = [
        # --- MORTGAGE SAMPLES ---
        {
            "id": "synthetic_mortgage_application",
            "filename": "synthetic_mortgage_application.png",
            "title": "Loan Application: Form 1003",
            "case_id": "CASE-101",
            "domain": "mortgage",
            "doc_type": "Uniform Loan Application",
            "description": "Primary borrower mortgage application with missing borrower signature on the certification section.",
            "file_url": "/samples/synthetic_mortgage_application.png",
            "thumbnail_url": "/samples/thumbnails/synthetic_mortgage_application.png",
            "file_type": "png",
            "sensitive": False,
        },
        {
            "id": "synthetic_income_document",
            "filename": "synthetic_income_document.png",
            "title": "Borrower Wage Statement (Paystub)",
            "case_id": "CASE-102",
            "domain": "mortgage",
            "doc_type": "Wage & Tax Statement",
            "description": "Earnings statement checklist showing missing recent paystub required for income verification.",
            "file_url": "/samples/synthetic_income_document.png",
            "thumbnail_url": "/samples/thumbnails/synthetic_income_document.png",
            "file_type": "png",
            "sensitive": False,
        },
        {
            "id": "synthetic_property_address",
            "filename": "synthetic_property_address.png",
            "title": "Property Appraisal & Deed Verification",
            "case_id": "CASE-103",
            "domain": "mortgage",
            "doc_type": "Property Appraisal Extract",
            "description": "Property appraisal and deed comparison showing street address and zip code conflict.",
            "file_url": "/samples/synthetic_property_address.png",
            "thumbnail_url": "/samples/thumbnails/synthetic_property_address.png",
            "file_type": "png",
            "sensitive": False,
        },
        {
            "id": "CASE-005",
            "filename": "CASE-005.pdf",
            "title": "CASE-005: Property Siting Reconciliation",
            "case_id": "CASE-103",
            "domain": "mortgage",
            "doc_type": "Appraisal & Title Reconciliation",
            "description": "Dual-source governing record reconciliation between appraisal valuation and county deed.",
            "file_url": "/samples/CASE-005.pdf",
            "thumbnail_url": "/samples/thumbnails/CASE-005.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "CASE-104",
            "filename": "CASE-104.pdf",
            "title": "CASE-104: Foreign-Language Tax Packet",
            "case_id": "CASE-104",
            "domain": "mortgage",
            "doc_type": "Foreign Tax Document & Translation",
            "description": "Overseas individual tax declaration in Cyrillic flagged for low-confidence OCR extraction and specialist review.",
            "file_url": "/samples/CASE-104.pdf",
            "thumbnail_url": "/samples/thumbnails/CASE-104.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "CASE-105",
            "filename": "CASE-105.pdf",
            "title": "CASE-105: Unverified Transfer & Wire Assignment",
            "case_id": "CASE-105",
            "domain": "mortgage",
            "doc_type": "Suspicious Transfer Document",
            "description": "Flagged sensitive case: secondary quitclaim deed and third-party escrow wire assignment outside standard workflow.",
            "file_url": "/samples/CASE-105.pdf",
            "thumbnail_url": "/samples/thumbnails/CASE-105.pdf.png",
            "file_type": "pdf",
            "sensitive": True,
        },

        # --- HEALTHCARE SAMPLES ---
        {
            "id": "INS-H101",
            "filename": "INS-H101.pdf",
            "title": "INS-H101: Prior Authorization Request",
            "case_id": "INS-101",
            "domain": "healthcare",
            "doc_type": "Prior Auth & Clinical Checklist",
            "description": "Prior authorization request packet for brain MRI missing required clinical consultation notes.",
            "file_url": "/samples/INS-H101.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H101.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "INS-H102",
            "filename": "INS-H102.pdf",
            "title": "INS-H102: Post-Service Hospital Claim",
            "case_id": "INS-102",
            "domain": "healthcare",
            "doc_type": "Operative Report & CMS-1500",
            "description": "Post-service surgical claim packet flagging missing required itemized hospital bill.",
            "file_url": "/samples/INS-H102.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H102.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "INS-H103",
            "filename": "INS-H103.pdf",
            "title": "INS-H103: Authorization & Policy Record",
            "case_id": "INS-103",
            "domain": "healthcare",
            "doc_type": "Prior Auth & Clinical Chart",
            "description": "Prior authorization request with policyholder name discrepancy between intake form and authoritative policy record.",
            "file_url": "/samples/INS-H103.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H103.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "INS-H104",
            "filename": "INS-H104.pdf",
            "title": "INS-H104: Inpatient Claim & Certificate",
            "case_id": "INS-104",
            "domain": "healthcare",
            "doc_type": "UB-04 Inpatient Claim",
            "description": "Institutional inpatient claim with certificate policy number mismatch requiring verification.",
            "file_url": "/samples/INS-H104.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H104.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "INS-H105",
            "filename": "INS-H105.pdf",
            "title": "INS-H105: Medical Extraction Review",
            "case_id": "INS-104",
            "domain": "healthcare",
            "doc_type": "Supporting Medical Report",
            "description": "Clinical documentation report containing unfamiliar terminology routed to specialist reviewer.",
            "file_url": "/samples/INS-H105.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H105.pdf.png",
            "file_type": "pdf",
            "sensitive": False,
        },
        {
            "id": "INS-H106",
            "filename": "INS-H106.pdf",
            "title": "INS-H106: SIU Forensic Investigation",
            "case_id": "INS-105",
            "domain": "healthcare",
            "doc_type": "Special Investigation Review",
            "description": "Flagged sensitive case: potentially altered invoices and arithmetic discrepancies quarantined to SIU with no automated action.",
            "file_url": "/samples/INS-H106.pdf",
            "thumbnail_url": "/samples/thumbnails/INS-H106.pdf.png",
            "file_type": "pdf",
            "sensitive": True,
        },
    ]

    if domain:
        dom = domain.strip().lower()
        samples_data = [s for s in samples_data if s["domain"] == dom]
    return samples_data


# Serve samples static files (documents & thumbnails)
samples_dir = Path(__file__).resolve().parent / "samples"
if samples_dir.exists():
    app.mount("/samples", StaticFiles(directory=str(samples_dir)), name="samples")


# Serve voiceops_frontend static files
frontend_dir = Path(__file__).resolve().parent / "voiceops_frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
