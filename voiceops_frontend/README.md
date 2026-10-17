# VoiceOps Frontend — Document Upload, Ask & Read Aloud

This frontend provides:
- Ask DocChase questions via `POST /ask` with case resolution and voice playback.
- Upload controls for PDF, DOCX, and TXT files via `POST /documents/upload`.
- Text area for extracted or manually entered text.
- Read Aloud using `POST /voice/speak`.

## Running the Server
```bash
python3 server.py
```
Open http://localhost:8000 in your browser.
