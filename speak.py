import os
import shutil
import subprocess
import sys
from pathlib import Path
import requests

import docchase


def load_env_file(env_path: Path = None):
    """
    Read key-value pairs from .env file into os.environ without overwriting existing env vars.
    This ensures the API key is never hardcoded.
    """
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


def play_audio(audio_path: str):
    """
    Play the generated audio file using the system's native player (afplay on macOS).
    """
    if sys.platform == "darwin" and shutil.which("afplay"):
        subprocess.run(["afplay", audio_path], check=True)
    elif shutil.which("ffplay"):
        subprocess.run(["ffplay", "-nodisp", "-autoexit", audio_path], check=True)
    elif shutil.which("aplay"):
        subprocess.run(["aplay", audio_path], check=True)
    else:
        print(f"Audio playback utility not found. Audio saved to: {audio_path}")


_KEY_COOLDOWNS = {}


def get_api_keys() -> list:
    """
    Returns prioritized list of SLNG API keys for dynamic failover:
    1. Priority key: from VOICEAI_API_KEY_PRIORITY / SLNG_API_KEY_PRIORITY in .env
    2. Fallback key: from VOICEAI_API_KEY / SLNG_API_KEY in .env
    """
    load_env_file()
    keys = []

    # Priority key: check env / .env
    prio = (
        os.environ.get("VOICEAI_API_KEY_PRIORITY")
        or os.environ.get("SLNG_API_KEY_PRIORITY")
    )
    if prio and prio.strip():
        keys.append(prio.strip())

    # Fallback key: from .env / os.environ
    fallback = os.environ.get("VOICEAI_API_KEY") or os.environ.get("SLNG_API_KEY")
    if fallback and fallback.strip() and fallback.strip() not in keys:
        keys.append(fallback.strip())

    return keys


def mark_key_rate_limited(api_key: str, cooldown_seconds: float = 60.0):
    """
    Temporarily marks an API key as rate-limited / high-usage so subsequent requests
    automatically failover to the alternate key.
    """
    _KEY_COOLDOWNS[api_key] = time.time() + cooldown_seconds


def is_key_rate_limited(api_key: str) -> bool:
    expiry = _KEY_COOLDOWNS.get(api_key, 0)
    if time.time() < expiry:
        return True
    if api_key in _KEY_COOLDOWNS:
        del _KEY_COOLDOWNS[api_key]
    return False


def get_active_keys() -> list:
    """
    Returns active keys sorted so available keys come first, preserving priority.
    """
    all_keys = get_api_keys()
    active = [k for k in all_keys if not is_key_rate_limited(k)]
    cooling = [k for k in all_keys if is_key_rate_limited(k)]
    return active if active else cooling


def speak(
    text: str,
    output_path: str = "case102_missing.wav",
    voice: str = "aura-2-luna-en",
    model: str = "deepgram/aura:2",
    play: bool = True,
) -> str:
    """
    Converts input text to speech using the SLNG Voice AI API with dynamic key failover.
    Prioritises the new key over the first one; dynamically fails over if usage is high.
    """
    load_env_file()

    keys_to_try = get_active_keys()
    if not keys_to_try:
        raise ValueError("SLNG API key not found in .env or environment. Please set VOICEAI_API_KEY.")

    base_url = os.environ.get("VOICEAI_BASE_URL", "https://in.api.slng.ai").rstrip("/")
    endpoint = f"{base_url}/v1/tts/{model}"

    last_error = None
    response = None

    for idx, key in enumerate(keys_to_try):
        try:
            res = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model": voice,
                },
                timeout=30,
            )
            # If rate limit (429) or high-usage temporary error (502, 503, 504), failover
            if res.status_code in (429, 402, 403, 502, 503, 504) and len(keys_to_try) > 1 and idx < len(keys_to_try) - 1:
                mark_key_rate_limited(key, cooldown_seconds=60.0)
                last_error = requests.HTTPError(f"HTTP {res.status_code}: {res.text}", response=res)
                continue

            res.raise_for_status()
            response = res
            break
        except requests.exceptions.RequestException as e:
            last_error = e
            if idx < len(keys_to_try) - 1:
                continue
            raise e

    if response is None and last_error is not None:
        raise last_error

    # Save audio binary content (WAV) to disk
    resolved_output = Path(output_path).resolve()
    with open(resolved_output, "wb") as f:
        f.write(response.content)

    print(f"Saved synthesized speech ({len(response.content):,} bytes) to: {resolved_output}")

    # Play the audio file
    if play:
        print(f"Playing audio via system player...")
        play_audio(str(resolved_output))

    return str(resolved_output)


if __name__ == "__main__":
    # Test speaking the CASE-102 MISSING answer from docchase.py
    case_102_missing_text = docchase.answer("CASE-102", "missing")
    print(f"\n[DocChase CASE-102 MISSING answer]:\n\"{case_102_missing_text}\"\n")

    speak(case_102_missing_text)
