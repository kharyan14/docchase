import audioop
import os
import subprocess
import sys
import time
import warnings
import wave
from pathlib import Path

warnings.filterwarnings("ignore")
import requests


def load_env_file(env_path: Path = None):
    if env_path is None:
        env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val


def record_microphone(
    output_path: str,
    silence_limit: float = 1.5,
    max_duration: float = 15.0,
) -> tuple:
    """
    Record audio from default mic using ffmpeg, stopping after ~1.5s of silence
    following speech (or up to max_duration). Returns (output_path, t_end_of_speech).
    """
    print("🎙️  Listening... Speak now!", flush=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "avfoundation",
        "-i", ":default",
        "-t", str(max_duration),
        "-f", "s16le",
        "-ar", "16000",
        "-ac", "1",
        "-loglevel", "error",
        "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frames = []
    chunk_bytes = 3200  # 0.1s chunk at 16kHz 16-bit mono
    chunk_sec = 0.1
    speech_detected = False
    silence_time = 0.0
    start_time = time.time()

    # Baseline ambient noise calibration from first 3 chunks (0.3s)
    baseline = []
    for _ in range(3):
        c = proc.stdout.read(chunk_bytes)
        if c:
            frames.append(c)
            baseline.append(audioop.rms(c, 2))
    base_rms = max(300, sum(baseline) / len(baseline)) if baseline else 300
    threshold = max(550, base_rms * 2.0)

    while True:
        chunk = proc.stdout.read(chunk_bytes)
        if not chunk:
            break
        frames.append(chunk)
        elapsed = time.time() - start_time
        if elapsed >= max_duration:
            break
        rms = audioop.rms(chunk, 2)
        if rms >= threshold:
            speech_detected = True
            silence_time = 0.0
        else:
            if speech_detected:
                silence_time += chunk_sec
                if silence_time >= silence_limit:
                    break

    proc.terminate()
    proc.wait()
    t_end_of_speech = time.time()

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"".join(frames))

    print("⏳ Transcribing audio via SLNG...", flush=True)
    return output_path, t_end_of_speech


def transcribe(audio_path: str, model: str = "slng/deepgram/nova:3-en") -> str:
    import speak
    speak.load_env_file()
    keys_to_try = speak.get_active_keys()
    if not keys_to_try:
        raise ValueError("SLNG API key not found in .env. Please set VOICEAI_API_KEY.")

    base_url = os.environ.get("VOICEAI_BASE_URL", "https://in.api.slng.ai").rstrip("/")
    endpoint = f"{base_url}/v1/stt/{model}"

    response = None
    last_err = None

    for idx, key in enumerate(keys_to_try):
        try:
            with open(audio_path, "rb") as f:
                res = requests.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"audio": f},
                    timeout=30,
                )
            if res.status_code in (429, 402, 403, 502, 503, 504) and len(keys_to_try) > 1 and idx < len(keys_to_try) - 1:
                speak.mark_key_rate_limited(key, cooldown_seconds=60.0)
                last_err = requests.HTTPError(f"HTTP {res.status_code}: {res.text}", response=res)
                continue

            res.raise_for_status()
            response = res
            break
        except requests.exceptions.RequestException as e:
            last_err = e
            if idx < len(keys_to_try) - 1:
                continue
            raise e

    if response is None and last_err is not None:
        raise last_err

    data = response.json()

    if "transcript" in data and data["transcript"]:
        return data["transcript"].strip()

    channels = data.get("results", {}).get("channels", [])
    if channels and "alternatives" in channels[0]:
        return channels[0]["alternatives"][0].get("transcript", "").strip()

    return ""


def listen(
    silence_limit: float = 1.5,
    max_duration: float = 15.0,
    return_timing: bool = False,
):
    temp_wav = Path(__file__).resolve().parent / "temp_listen.wav"
    try:
        _, t_end_of_speech = record_microphone(
            str(temp_wav), silence_limit=silence_limit, max_duration=max_duration
        )
        text = transcribe(str(temp_wav))
        if return_timing:
            return text, t_end_of_speech
        return text
    finally:
        if temp_wav.exists():
            temp_wav.unlink()


if __name__ == "__main__":
    transcript = listen()
    if transcript:
        print(f"\nTranscript: \"{transcript}\"")
    else:
        print("\n(No speech detected)")
