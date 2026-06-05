# -*- coding: utf-8 -*-
# render_explainer.py — Pipeline: microsegments -> per-microsegment TTS -> image clips -> MP4
#
# Each segment contains "microsegments": [{"text": str, "image": int}, ...]
# Each microsegment gets its own TTS pass. The image displays for exactly
# as long as that microsegment's audio plays — no equal-split math.

import os
import sys
import subprocess
import tempfile
from datetime import datetime

# ── Suppress console windows for all subprocess calls on Windows ───────────────
if sys.platform == "win32":
    _orig_popen = subprocess.Popen
    _CREATE_NO_WINDOW = 0x08000000

    class _SilentPopen(_orig_popen):
        def __init__(self, *args, **kwargs):
            if "creationflags" not in kwargs:
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            else:
                kwargs["creationflags"] |= _CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = _SilentPopen

# ── Canvas config ──────────────────────────────────────────────────────────────
TARGET_W  = 1920
TARGET_H  = 1080
FPS       = 30
VOICE     = "am_fenrir"
SPEED     = 1.0


# ── Vocoder Effect (Daft Punk) ─────────────────────────────────────────────────
def apply_vocoder(samples, sample_rate):
    import numpy as np
    samples = samples.astype(np.float32)
    t = np.arange(len(samples)) / sample_rate
    carrier = (
        0.5 * np.sin(2 * np.pi * 120 * t) +
        0.3 * np.sin(2 * np.pi * 240 * t) +
        0.2 * np.sin(2 * np.pi * 360 * t)
    ).astype(np.float32)
    delay_samples = int(sample_rate * 0.003)
    delayed = np.zeros_like(samples)
    delayed[delay_samples:] = samples[:-delay_samples]
    combed = 0.7 * samples + 0.3 * delayed
    result = combed * (0.5 + 0.5 * carrier)
    return (result / (np.max(np.abs(result)) + 1e-9)).astype(np.float32)


def render_explainer_video(
    segments,       # list of {"segment":int, "microsegments":[{"text":str,"image":int},...]}
    image_map,      # dict {image_number(int): file_path(str)}
    output_folder,
    kokoro_model,
    kokoro_voice,
    log_fn=print,
    progress_fn=lambda p: None,
    status_fn=lambda s: None,
):
    import soundfile as sf
    from kokoro_onnx import Kokoro
    from pydub import AudioSegment
    from moviepy.editor import (
        ImageClip, AudioFileClip, VideoFileClip, concatenate_videoclips
    )
    from PIL import Image
    import numpy as np

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir   = tempfile.mkdtemp(prefix="explainer_")

    # ── Step 1: Load Kokoro ────────────────────────────────────────────────────
    log_fn("Loading Kokoro model...")
    status_fn("Loading TTS model...")
    progress_fn(5)
    kokoro = Kokoro(kokoro_model, kokoro_voice)

    # Flatten all microsegments into a single ordered list for progress tracking
    all_micro = []
    for seg in segments:
        seg_num = seg.get("segment", "?")
        for micro in seg["microsegments"]:
            all_micro.append({
                "seg_num":  seg_num,
                "text":     micro["text"].strip(),
                "image":    micro["image"],
            })

    total_micro = len(all_micro)
    log_fn(f"Total microsegments: {total_micro}")

    audio_clips = []   # pydub AudioSegment per microsegment (for concatenation)
    video_clips = []   # moviepy ImageClip per microsegment

    # ── Step 2: Per-microsegment TTS → image clip ──────────────────────────────
    for idx, micro in enumerate(all_micro):
        seg_num   = micro["seg_num"]
        text      = micro["text"]
        img_num   = micro["image"]
        img_path  = image_map[img_num]

        log_fn(f"[seg {seg_num} | micro {idx+1}/{total_micro} | img #{img_num}] "
               f"\"{text[:50]}{'...' if len(text) > 50 else ''}\"")
        status_fn(f"TTS microsegment {idx+1}/{total_micro}...")
        progress_fn(5 + int(60 * idx / total_micro))

        # TTS -> vocoder effect -> WAV -> pydub AudioSegment
        samples, sample_rate = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        samples = apply_vocoder(samples, sample_rate)
        wav_path = os.path.join(tmp_dir, f"micro_{idx:04d}.wav")
        sf.write(wav_path, samples, sample_rate)
        audio_seg = AudioSegment.from_wav(wav_path)
        os.remove(wav_path)

        duration_s = len(audio_seg) / 1000.0
        log_fn(f"  -> {duration_s:.2f}s")

        audio_clips.append(audio_seg)

        # Image clip: holds for exactly this microsegment's audio duration
        img   = Image.open(img_path).convert("RGB")
        img   = _fit_to_canvas(img, TARGET_W, TARGET_H)
        arr   = np.array(img)
        clip  = ImageClip(arr).set_duration(duration_s)
        video_clips.append(clip)

    # ── Step 3: Concatenate all audio -> single MP3 ────────────────────────────
    log_fn("Combining audio...")
    status_fn("Combining audio...")
    progress_fn(68)

    combined_audio = AudioSegment.empty()
    for a in audio_clips:
        combined_audio += a

    combined_mp3 = os.path.join(tmp_dir, "combined.mp3")
    combined_audio.export(combined_mp3, format="mp3", bitrate="192k")

    # ── Step 4: Concatenate image clips ───────────────────────────────────────
    log_fn(f"Compositing {len(video_clips)} image clips...")
    status_fn("Compositing video...")
    progress_fn(75)

    content_video = concatenate_videoclips(video_clips, method="compose")
    audio_track   = AudioFileClip(combined_mp3)
    content_video = content_video.set_audio(audio_track)

    # ── Step 5: Prepend channel intro ─────────────────────────────────────────
    intro_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "video", "WonderSketch-intro.mp4")
    if os.path.isfile(intro_path):
        log_fn("Prepending channel intro...")
        status_fn("Prepending intro...")
        intro_clip  = VideoFileClip(intro_path).resize((TARGET_W, TARGET_H))
        final_video = concatenate_videoclips([intro_clip, content_video], method="compose")
    else:
        log_fn(f"⚠ Intro not found at {intro_path} — skipping.")
        final_video = content_video

    # ── Step 6: Export MP4 ────────────────────────────────────────────────────
    out_path = os.path.join(output_folder, f"explainer_{timestamp}.mp4")
    log_fn(f"Rendering MP4 ({TARGET_W}x{TARGET_H} @ {FPS}fps)...")
    status_fn("Rendering MP4 (1920x1080)...")
    progress_fn(82)

    final_video.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        ffmpeg_params=["-crf", "23"],
        logger=None,
    )
    progress_fn(97)

    # ── Cleanup ────────────────────────────────────────────────────────────────
    try: os.remove(combined_mp3)
    except: pass
    try: os.rmdir(tmp_dir)
    except: pass

    log_fn(f"Total duration: {final_video.duration:.1f}s")
    return out_path


# ── Image fit helper ───────────────────────────────────────────────────────────
def _fit_to_canvas(img, canvas_w, canvas_h):
    from PIL import Image
    img_w, img_h = img.size
    scale = max(canvas_w / img_w, canvas_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img   = img.resize((new_w, new_h), Image.LANCZOS)
    left  = (new_w - canvas_w) // 2
    top   = (new_h - canvas_h) // 2
    img   = img.crop((left, top, left + canvas_w, top + canvas_h))
    return img
