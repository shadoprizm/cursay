"""Private, OpenAI-compatible speech-to-text service for Cursay."""
from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel


MODEL_NAME = os.getenv("CURSAY_MODEL", "base.en")
MODEL_ID = os.getenv("CURSAY_MODEL_ID", "whisper-base.en")
DEFAULT_LANGUAGE = os.getenv("CURSAY_LANGUAGE", "en")
THREADS = int(os.getenv("CURSAY_THREADS", str(max(1, min(8, os.cpu_count() or 4)))))
BEAM_SIZE = int(os.getenv("CURSAY_BEAM_SIZE", "1"))
MAX_BYTES = int(os.getenv("CURSAY_MAX_AUDIO_BYTES", str(50 * 1024 * 1024)))
MODEL_DIR = Path(
    os.getenv(
        "CURSAY_MODEL_DIR",
        Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "cursay" / "models",
    )
)

app = FastAPI(title="Cursay Speech-to-Text", version="1.1.0")
_lock = threading.Lock()
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    with _lock:
        if _model is None:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            MODEL_DIR.chmod(0o700)
            _model = WhisperModel(
                MODEL_NAME,
                download_root=str(MODEL_DIR),
                device="cpu",
                compute_type="int8",
                cpu_threads=THREADS,
            )
        return _model


def _transcribe(data: bytes, filename: str, language: str | None, temperature: float) -> dict[str, Any]:
    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        handle.write(data)
        handle.flush()
        segments, info = _get_model().transcribe(
            handle.name,
            language=language or DEFAULT_LANGUAGE or None,
            temperature=temperature,
            vad_filter=True,
            beam_size=BEAM_SIZE,
            condition_on_previous_text=False,
            word_timestamps=True,
        )
        segment_list = list(segments)

    text = " ".join(segment.text.strip() for segment in segment_list if segment.text.strip()).strip()
    words = [
        {
            "text": word.word.strip(),
            "start": round(word.start, 3),
            "end": round(word.end, 3),
            "confidence": round(word.probability, 4),
        }
        for segment in segment_list
        for word in (segment.words or [])
        if word.word.strip()
    ]
    return {
        "text": text,
        "language": info.language,
        "duration": round(info.duration, 2),
        "words": words,
        "provider": "cursay-local",
        "model": MODEL_ID,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "selected_provider": "local",
        "local_model": MODEL_ID,
        "local_loaded": _model is not None,
        "device": "cpu",
        "language": DEFAULT_LANGUAGE or "auto",
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "cursay"}]}


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(MODEL_ID),
    language: str | None = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
) -> Any:
    del model
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty audio upload")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "audio upload too large")

    started = time.monotonic()
    result = _transcribe(data, file.filename or "audio.wav", language, temperature)
    result["elapsed"] = round(time.monotonic() - started, 2)
    if response_format == "text":
        return PlainTextResponse(result["text"])
    return JSONResponse(result)
