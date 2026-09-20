from __future__ import annotations

import os
from pathlib import Path

from faster_whisper import WhisperModel


model_name = os.getenv("CURSAY_MODEL", "base.en")
model_dir = Path(
    os.getenv(
        "CURSAY_MODEL_DIR",
        Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "cursay" / "models",
    )
)
model_dir.mkdir(parents=True, exist_ok=True)
model_dir.chmod(0o700)
print(f"Downloading {model_name} to {model_dir} …", flush=True)
WhisperModel(model_name, download_root=str(model_dir), device="cpu", compute_type="int8", cpu_threads=1)
print("Local Whisper model is ready.", flush=True)
