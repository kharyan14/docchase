import re
import sys
import time
import warnings
import wave
from pathlib import Path

warnings.filterwarnings("ignore")

import docchase
import listen
import speak


class SessionStats:
    def __init__(self):
        self.question_count = 0
        self.stt_calls = 0
        self.tts_calls = 0
        self.stt_seconds = 0.0
        self.tts_seconds = 0.0

    @property
    def total_calls(self):
        return self.stt_calls + self.tts_calls

    @property
    def stt_cost(self):
        return (self.stt_seconds / 60.0) * 0.003

    @property
    def tts_cost(self):
        return (self.tts_seconds / 60.0) * 0.005

    @property
    def total_cost(self):
        return self.stt_cost + self.tts_cost

    def print_summary(self):
        print(f"API calls made: {self.total_calls} (STT: {self.stt_calls}, TTS: {self.tts_calls})")
        print(f"Estimated cost: ${self.total_cost:.5f} (STT: ${self.stt_cost:.5f}, TTS: ${self.tts_cost:.5f})")


GLOBAL_STATS = SessionStats()


def get_audio_duration(path):
    try:
        path = Path(path)
        with wave.open(str(path), "rb") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            frames = wf.getnframes()
            bytes_per_sec = rate * channels * sampwidth
            if bytes_per_sec > 0:
                file_size = path.stat().st_size
                dur = frames / float(rate)
                if dur < 3600 and dur * bytes_per_sec <= file_size + 100:
                    return dur
                return max(0.0, (file_size - 44) / float(bytes_per_sec))
    except Exception:
        pass
    return 0.0


def find_case_ids(text, open_cases):
    t = text.lower()
    # Map English and Hindi numerals
    hindi_digits = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4", "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}
    for hd, ed in hindi_digits.items():
        t = t.replace(hd, ed)

    num_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ek": "1", "do": "2", "teen": "3", "char": "4", "paanch": "5",
        "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5",
    }
    for w, d in num_words.items():
        t = re.sub(rf"\b{w}\b", d, t)
    t = re.sub(r"(?<=\d)\s+(?=\d)", "", t)

    matches = []
    is_healthcare = bool(re.search(r"\b(health\s*care|healthcare|insurance)\b|(हेल्थकेयर|स्वास्थ्य|बीमा|हॉस्पिटल)", t))

    # 1) "INS", "I N S", "ILS", or healthcare mentions plus digits must map to healthcare case id
    for m in re.finditer(r"(?:\b(?:i\s*n\s*s|ins|ils|in\s+s)|आई\s*एन\s*एस|आईएनएस)[-\s]?h?(\d+)\b", t):
        cid = f"INS-{m.group(1)}"
        if cid in open_cases:
            matches.append((m.start(), cid))

    # If user explicitly specified healthcare domain, map any digits to INS cases
    if is_healthcare:
        for m in re.finditer(r"(?:(?:\bcase|केस)[-\s]?)?(\d+)\b", t):
            cid = f"INS-{m.group(1)}"
            if cid in open_cases and not any(c == cid for _, c in matches):
                matches.append((m.start(), cid))

    # 1) "case" or "केस" plus digits to the mortgage one (if not explicitly healthcare)
    if not is_healthcare:
        for m in re.finditer(r"(?:\bcase|केस)[-\s]?(\d+)\b", t):
            cid = f"CASE-{m.group(1)}"
            if cid in open_cases:
                matches.append((m.start(), cid))

    # 1) If neither "ins" nor "case" was specified, check digits.
    # If both domains have that number, ask which one.
    clarification = None
    if not matches:
        for m in re.finditer(r"\b(\d+)\b", t):
            num = m.group(1)
            has_mortgage = f"CASE-{num}" in open_cases
            has_healthcare = f"INS-{num}" in open_cases
            if has_mortgage and has_healthcare:
                clarification = f"Both mortgage and healthcare have case {num}. Which one did you mean?"
                break
            elif has_mortgage:
                matches.append((m.start(), f"CASE-{num}"))
            elif has_healthcare:
                matches.append((m.start(), f"INS-{num}"))

    matches.sort(key=lambda x: x[0])
    case_ids = [cid for _, cid in matches]
    return case_ids, clarification


def find_question_type(text):
    t = text.lower()
    if any(k in t for k in ["approve", "approved", "accept", "sign off"]):
        return "approve"
    # 3) treat "in depth", "background", "similar" as context
    if any(k in t for k in ["context", "past", "history", "similar", "in depth", "background"]):
        return "context"
    if any(k in t for k in ["decision", "decide", "action", "proposal"]):
        return "decision"
    # 3) treat "status", "problem", "what's wrong", "what is the issue" as missing
    if any(k in t for k in [
        "missing", "status", "problem", "what's wrong", "what is wrong", "whats wrong",
        "what is the issue", "what's the issue", "whats the issue", "what is missing", "document"
    ]):
        return "missing"
    return None


def step(transcript=None, t_end_of_speech=None, open_cases=None, stats=None):
    if open_cases is None:
        open_cases = docchase.load_open_cases()
    if stats is None:
        stats = GLOBAL_STATS

    # 2) Recording: stop recording after ~1.5s silence (max 15s)
    if transcript is None:
        temp_wav = Path(__file__).resolve().parent / "temp_step.wav"
        try:
            _, t_end_of_speech = listen.record_microphone(
                str(temp_wav), silence_limit=1.5, max_duration=15.0
            )
            # Track STT audio duration and call count
            stt_dur = get_audio_duration(temp_wav)
            stats.stt_calls += 1
            stats.stt_seconds += stt_dur

            t_trans_start = time.time()
            transcript = listen.transcribe(str(temp_wav))
            sec_transcribe = time.time() - t_trans_start
        finally:
            if temp_wav.exists():
                temp_wav.unlink()
    else:
        if t_end_of_speech is None:
            t_end_of_speech = time.time()
        sec_transcribe = 0.0

    words = transcript.strip().split()

    # 3) Stop command: if I say "stop" or "exit", quit.
    if any(w.lower() in ["stop", "exit"] for w in words):
        print(f"\nTranscript:    {transcript}")
        print("Exiting.")
        return False

    # 2) If the transcript is empty or under 3 words, do not call the text-to-speech API,
    # just print "nothing heard" and wait.
    if len(words) < 3:
        print(f"\nTranscript:    {transcript}")
        print("nothing heard")
        stats.print_summary()
        print()
        return True

    # Timing: answering
    t_ans_start = time.time()
    case_ids, clarification = find_case_ids(transcript, open_cases)
    case_id = case_ids[0] if case_ids else None
    q_type = find_question_type(transcript)

    # 1) if a case id is found but no question type, default to "missing"
    if case_id and not q_type:
        q_type = "missing"

    if clarification:
        answer_text = clarification
    # 3) if no case id is found, say "Which case?" instead of "please repeat"
    elif not case_id:
        answer_text = "Which case?"
    else:
        answer_text = docchase.answer(case_id, q_type)
        # 2) if more than one case id is found in one sentence, answer the first
        # and say "One case at a time, ask about the next one after this."
        if len(case_ids) > 1:
            answer_text = f"{answer_text} One case at a time, ask about the next one after this."

    sec_answering = time.time() - t_ans_start

    # Timing: speaking & latency from end of speech to start of audio
    t_speak_start = time.time()
    audio_file = speak.speak(answer_text, output_path="main_response.wav", play=False)
    tts_dur = get_audio_duration(audio_file)
    stats.tts_calls += 1
    stats.tts_seconds += tts_dur
    stats.question_count += 1

    t_start_of_audio = time.time()
    sec_total = t_start_of_audio - t_end_of_speech

    print(f"\nTranscript:    {transcript}")
    print(f"Case ID:       {case_id or 'Unknown'}")
    print(f"Question Type: {q_type or 'Unknown'}")
    print(f"Answer:        {answer_text}")

    # Play the spoken audio
    speak.play_audio(audio_file)
    sec_speaking = time.time() - t_speak_start

    # Print seconds taken by each stage
    print(f"Seconds taken by transcribing: {sec_transcribe:.2f}")
    print(f"Seconds taken by answering:    {sec_answering:.4f}")
    print(f"Seconds taken by speaking:     {sec_speaking:.2f}")
    print(f"Total from end of speech to start of audio: {sec_total:.2f}")

    # 4) Print running count of API calls made and estimated cost
    stats.print_summary()
    print()

    return True


def main():
    open_cases = docchase.load_open_cases()
    stats = GLOBAL_STATS
    print("DocChase voice assistant ready. Push to talk enabled.")
    print("Limit: 20 questions per run. Say 'stop' or 'exit' to quit.\n")

    # 1) Push to talk: wait for me to press Enter, then record one question,
    # answer once, then wait for Enter again. No always-on loop.
    # 3) Hard limit of 20 questions per run
    while stats.question_count < 20:
        try:
            prompt = f"[{stats.question_count}/20] Press Enter to record (or type 'exit' to quit)... "
            user_input = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.strip().lower() in ["exit", "stop", "q", "quit"]:
            print("Exiting.")
            break

        should_continue = step(open_cases=open_cases, stats=stats)
        if should_continue is False:
            break

    if stats.question_count >= 20:
        print("Reached maximum limit of 20 questions for this run. Exiting.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sample = sys.argv[2] if len(sys.argv) > 2 else "what is missing in case 102"
        step(transcript=sample)
    else:
        main()
