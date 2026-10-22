#!/usr/bin/env python3
"""One-time local OCR setup; installs a private CPU environment, never a service or chat client."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check bundled models and recognize a test image offline")
    args = parser.parse_args()
    if args.check:
        import article_ingest as ingest
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (400, 80), "white")
        ImageDraw.Draw(image).text((10, 10), "OCR 123", fill="black", font_size=40)
        result = ingest.get_ocr()(image)
        if not result.txts:
            raise RuntimeError("OCR smoke check recognized no text")
        print(json.dumps({"ok": True, "engine": "rapidocr", "text": list(result.txts)}))
        return
    started = time.monotonic()
    root = Path.home() / ".local" / "share" / "article_ingest" / "venv"
    print(f"[1/3] Create/reuse OCR environment: {root}", flush=True)
    venv.EnvBuilder(with_pip=True).create(root)
    binary = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    print("[2/3] Install pinned CPU OCR dependencies (first setup needs network)", flush=True)
    subprocess.run([str(binary), "-m", "pip", "install", "-r", str(Path(__file__).with_name("requirements_ocr.txt"))], check=True)
    print("[3/3] Verify bundled models and offline recognition", flush=True)
    subprocess.run([str(binary), "-B", str(Path(__file__).resolve()), "--check"], check=True)
    print(f"OCR ready: {time.monotonic() - started:.1f}s; normal image recognition needs no network/login", flush=True)


if __name__ == "__main__":
    main()
