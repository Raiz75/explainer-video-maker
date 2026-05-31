# Explainer Video Maker

A local Windows desktop tool that turns an AI-generated script + images into a fully synced MP4 explainer video. Uses [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) for offline text-to-speech — no API keys, no internet required at render time.

**Output:** 1080×1920 portrait MP4 (TikTok / YouTube Shorts / Reels)

---

## How It Works

1. Copy the **Master Prompt** from the app
2. Paste it into any AI (ChatGPT, Claude, Gemini), fill in your topic
3. The AI outputs:
   - A **JSON array** of script segments → paste into the app
   - **Plain text image prompts** → paste each into an image AI (Midjourney, DALL·E, etc.)
4. Add your generated images into the app's image slots (in order)
5. Click **GENERATE VIDEO**

The app runs Kokoro TTS on each segment, measures the exact audio duration, holds the matching image on screen for that duration, then concatenates everything into one MP4.

---

## Project Structure

```
explainer-video-maker/
├── explainer-video-maker.py   # GUI entry point (Tkinter)
├── render_explainer.py        # Pipeline: TTS → image clips → MP4
├── run_explainer-video-maker.vbs  # Windows silent launcher (no console)
├── requirements.txt
├── kokoro-v1.0.onnx           # ← NOT in repo, download separately
├── voices-v1.0.bin            # ← NOT in repo, download separately
├── images/                    # Drop your AI-generated images here (or browse)
└── output/                    # Rendered MP4s land here
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/explainer-video-maker.git
cd explainer-video-maker
```

### 2. Install Python dependencies

Requires **Python 3.10+** (tested on 3.14).

```bash
pip install -r requirements.txt
```

> **Windows note:** If `pydub` can't find FFmpeg, see step 4.

### 3. Download the Kokoro model files

The two model files are too large for GitHub. Download them manually:

| File | Size | Link |
|---|---|---|
| `kokoro-v1.0.onnx` | ~310 MB | [Hugging Face — kokoro-v1.0.onnx](https://huggingface.co/onnx-community/Kokoro-82M-ONNX/resolve/main/model/kokoro-v1.0.onnx) |
| `voices-v1.0.bin` | ~25 MB | [Hugging Face — voices-v1.0.bin](https://huggingface.co/onnx-community/Kokoro-82M-ONNX/resolve/main/voices-v1.0.bin) |

**Place both files in the root of the project folder** (same directory as `explainer-video-maker.py`):

```
explainer-video-maker/
├── kokoro-v1.0.onnx   ✅ here
├── voices-v1.0.bin    ✅ here
├── explainer-video-maker.py
...
```

> You can also find both files at the [kokoro-onnx GitHub releases](https://github.com/thewh1teagle/kokoro-onnx/releases) or via the `kokoro-onnx` Python package docs.

### 4. Install FFmpeg (required by MoviePy and pydub)

FFmpeg must be available on your system PATH.

**Windows (recommended — winget):**
```bash
winget install Gyan.FFmpeg
```

**Or download manually:**
1. Go to https://ffmpeg.org/download.html → Windows builds
2. Extract the archive
3. Add the `bin/` folder to your system PATH

**Verify:**
```bash
ffmpeg -version
```

### 5. Run the app

**Option A — VBS launcher (no console window):**
Double-click `run_explainer-video-maker.vbs`

**Option B — Terminal:**
```bash
python explainer-video-maker.py
```

---

## Script Segments JSON Format

Paste this structure into the **Script Segments** box. Each segment maps one narration chunk to one image slot number.

```json
[
  {"segment": 1, "text": "Did you know most people breathe wrong their entire lives?", "image": 1},
  {"segment": 2, "text": "Shallow chest breathing keeps your body in a low-grade stress state 24/7.", "image": 2},
  {"segment": 3, "text": "Diaphragmatic breathing activates your parasympathetic nervous system in seconds.", "image": 3},
  {"segment": 4, "text": "Inhale for 4, hold for 4, exhale for 8 — try it right now.", "image": 4}
]
```

- `"segment"` — order number (integer)
- `"text"` — the narration spoken by TTS for that segment
- `"image"` — which image slot number is shown during this segment

The number of JSON segments **must match** the number of image slots you fill in.

---

## Image Slots

- The app starts with 3 slots pre-loaded
- Click **＋ ADD IMAGE SLOT** to add more
- Click 📂 on any slot to browse for that image
- Click ✕ to remove a slot (remaining slots auto-renumber)
- Slot order = image number order — slot [01] = `"image": 1`, slot [02] = `"image": 2`, etc.

Supported formats: `.png` `.jpg` `.jpeg` `.webp` `.bmp`

All images are auto-fit to 1080×1920 via center-crop (no stretching).

---

## Dependencies

| Package | Purpose |
|---|---|
| `kokoro-onnx` | Local TTS inference via Kokoro ONNX model |
| `soundfile` | Write WAV from Kokoro audio samples |
| `pydub` | WAV → MP3 conversion, audio concatenation |
| `moviepy` | ImageClip compositing, MP4 export |
| `Pillow` | Image loading and canvas fit/crop |
| `numpy` | Frame array conversion for MoviePy |
| `tkinter` | GUI (Python stdlib, no install needed) |

---

## Output

- Format: H.264 + AAC
- Resolution: 1080×1920 @ 30fps
- CRF: 23 (good quality, reasonable file size)
- Filename: `output/explainer_YYYYMMDD_HHMMSS.mp4`
- Each segment's image is held for **exactly** the duration of its TTS audio — automatic sync, no manual timing needed

---

## Notes

- Kokoro voice used: `am_adam` (American male). To change it, edit `VOICE` in `render_explainer.py`.
- TTS speed: `1.0`. Adjust `SPEED` in `render_explainer.py`.
- The `images/` folder exists for convenience — you can also browse to any location on disk.
- All rendering is 100% local. No API calls, no internet needed after setup.
