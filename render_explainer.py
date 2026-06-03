# -*- coding: utf-8 -*-
# render_explainer.py — Pipeline: segments → per-segment TTS → multi-image clips → MP4
#
# Each segment now carries "images": [list of image numbers].
# TTS is generated once per segment; its duration is divided evenly across
# every image in that segment so each visual beat gets equal screen time.

import os
import tempfile
from datetime import datetime

# ── Canvas config ──────────────────────────────────────────────────────────────
TARGET_W  = 1920   # YouTube landscape (16:9)
TARGET_H  = 1080
FPS       = 30
VOICE     = "am_adam"
SPEED     = 1.0


def render_explainer_video(
    segments,       # list of {"segment":int, "text":str, "images":[int, ...]}
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
        ImageClip, AudioFileClip, concatenate_videoclips
    )
    from PIL import Image
    import numpy as np

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmp_dir    = tempfile.mkdtemp(prefix="explainer_")

    # ── Step 1: Load Kokoro ────────────────────────────────────────────────────
    log_fn("Loading Kokoro model...")
    status_fn("Loading TTS model...")
    progress_fn(5)
    kokoro = Kokoro(kokoro_model, kokoro_voice)

    total_segs  = len(segments)
    audio_clips = []   # one mp3 path per segment (for concatenation)
    video_clips = []   # one ImageClip per image beat (may be many per segment)
    total_images_generated = 0

    # ── Step 2: Per-segment TTS → split duration across image beats ────────────
    for i, seg in enumerate(segments):
        seg_num    = seg.get("segment", i + 1)
        text       = seg["text"].strip()
        image_nums = seg["images"]           # list of ints, e.g. [4, 5, 6]
        n_images   = len(image_nums)

        log_fn(f"[{seg_num}/{total_segs}] TTS ({n_images} images): "
               f"\"{text[:55]}{'...' if len(text) > 55 else ''}\"")
        status_fn(f"Generating speech for segment {seg_num}/{total_segs}...")
        progress_fn(5 + int(60 * i / total_segs))

        # TTS → WAV → MP3
        samples, sample_rate = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        wav_path = os.path.join(tmp_dir, f"seg_{seg_num:03d}.wav")
        mp3_path = os.path.join(tmp_dir, f"seg_{seg_num:03d}.mp3")

        sf.write(wav_path, samples, sample_rate)
        audio_seg = AudioSegment.from_wav(wav_path)
        audio_seg.export(mp3_path, format="mp3", bitrate="192k")
        os.remove(wav_path)

        seg_duration  = len(audio_seg) / 1000.0          # total seconds for this segment
        beat_duration = seg_duration / n_images           # equal time per image beat

        log_fn(f"  → {seg_duration:.2f}s total  |  "
               f"{beat_duration:.2f}s per beat  |  images {image_nums}")

        audio_clips.append(mp3_path)

        # One ImageClip per visual beat, each holding for beat_duration seconds
        for img_num in image_nums:
            img_path = image_map[img_num]
            img      = Image.open(img_path).convert("RGB")
            img      = _fit_to_canvas(img, TARGET_W, TARGET_H)
            arr      = np.array(img)
            clip     = ImageClip(arr).set_duration(beat_duration)
            video_clips.append(clip)
            total_images_generated += 1

    log_fn(f"Total image clips generated: {total_images_generated}")

    # ── Step 3: Concatenate all audio → single MP3 ────────────────────────────
    log_fn("Combining audio segments...")
    status_fn("Combining audio...")
    progress_fn(68)

    combined_audio = AudioSegment.empty()
    for mp3 in audio_clips:
        combined_audio += AudioSegment.from_mp3(mp3)

    combined_mp3 = os.path.join(tmp_dir, "combined.mp3")
    combined_audio.export(combined_mp3, format="mp3", bitrate="192k")

    # ── Step 4: Concatenate all image clips ───────────────────────────────────
    log_fn(f"Compositing {len(video_clips)} video clips...")
    status_fn("Compositing video...")
    progress_fn(75)

    final_video = concatenate_videoclips(video_clips, method="compose")
    audio_track = AudioFileClip(combined_mp3)
    final_video = final_video.set_audio(audio_track)

    # ── Step 5: Export MP4 ────────────────────────────────────────────────────
    out_path = os.path.join(output_folder, f"explainer_{timestamp}.mp4")
    log_fn(f"Rendering MP4 ({TARGET_W}×{TARGET_H} @ {FPS}fps) — YouTube 16:9...")
    status_fn("Rendering MP4 (1920×1080)...")
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

    # ── Cleanup temp files ─────────────────────────────────────────────────────
    for mp3 in audio_clips:
        try: os.remove(mp3)
        except: pass
    try: os.remove(combined_mp3)
    except: pass
    try: os.rmdir(tmp_dir)
    except: pass

    log_fn(f"Total duration: {final_video.duration:.1f}s")
    return out_path


# ── Image fit helper ───────────────────────────────────────────────────────────
def _fit_to_canvas(img, canvas_w, canvas_h):
    """
    Scale image to fill canvas_w × canvas_h via cover-fit (center-crop),
    preserving aspect ratio. Returns a PIL Image of exactly canvas_w × canvas_h.
    """
    from PIL import Image

    img_w, img_h = img.size
    scale = max(canvas_w / img_w, canvas_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img   = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - canvas_w) // 2
    top  = (new_h - canvas_h) // 2
    img  = img.crop((left, top, left + canvas_w, top + canvas_h))
    return img
