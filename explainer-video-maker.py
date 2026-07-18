# -*- coding: utf-8 -*-
# explainer-video-maker.py — AI Explainer Video Maker
# Run via run_explainer-video-maker.vbs

import tkinter as tk
from tkinter import messagebox
import threading
import os
import json

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER    = os.path.join(SCRIPT_DIR, "output")
ASSETS_IMAGES    = os.path.join(SCRIPT_DIR, "assets", "images")
KOKORO_MODEL  = os.path.join(SCRIPT_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICE  = os.path.join(SCRIPT_DIR, "voices-v1.0.bin")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
SURFACE  = "#16213e"
SURFACE2 = "#0d0d1a"
BORDER   = "#0f3460"
ACCENT   = "#e94560"
FG_GREEN = "#7fcc7f"
FG_MUTED = "#888888"

# ── Master Prompts ─────────────────────────────────────────────────────────────
def _load_prompt(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"[ERROR: {filename} not found at {path}]"

MASTER_PROMPT1 = _load_prompt("master_prompt1.txt")
MASTER_PROMPT2 = _load_prompt("master_prompt2.txt")
MASTER_PROMPT3 = _load_prompt("master_prompt3.txt")

HINT_JSON = (
    'Each segment needs: segment, intent, microsegments[]\n'
    'Each microsegment needs: text, image (int), pose (string or null)\n'
    '[\n'
    '  {"segment": 1, "intent": "hook", "microsegments": [\n'
    '    {"text": "Short punchy hook.", "image": 1, "pose": "emphasis"},\n'
    '    {"text": "Stakes raised -- this changes everything.", "image": 2, "pose": null},\n'
    '    {"text": "By the end, you will know exactly why.", "image": 3, "pose": "asking"}\n'
    '  ]},\n'
    '  {"segment": 2, "intent": "setup", "microsegments": [\n'
    '    {"text": "Here is the world before everything changed.", "image": 4, "pose": "explaining"},\n'
    '    {"text": "It looked normal.", "image": 5, "pose": null}\n'
    '  ]}\n'
    ']\n'
    'intents: hook | setup | escalation | conflict | reveal | resolution | payoff\n'
    'poses:   asking | authority | emphasis | explaining | pointingLeft | null (~50% null)'
)

# ── Main App ───────────────────────────────────────────────────────────────────
class ExplainerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Long-Form Explainer Video Maker")
        self.geometry("740x700")
        self.minsize(740, 500)
        self.configure(bg=BG)
        self._running = False
        self._build_ui()

    def _build_ui(self):
        import tkinter.ttk as ttk

        # ── Bottom bar: always visible Generate + Clear ────────────────────────
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=24, pady=10)

        self._gen_btn = tk.Button(bottom,
                                  text="▶  GENERATE VIDEO",
                                  bg=ACCENT, fg="white",
                                  font=("Consolas", 12, "bold"),
                                  relief="flat", cursor="hand2",
                                  activebackground="#c73652",
                                  activeforeground="white",
                                  command=self._on_generate)
        self._gen_btn.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 6))

        self._clear_btn = tk.Button(bottom,
                                    text="🗑  CLEAR ALL",
                                    bg=SURFACE2, fg=ACCENT,
                                    font=("Consolas", 11, "bold"),
                                    relief="flat", cursor="hand2",
                                    activebackground=BORDER,
                                    activeforeground=ACCENT,
                                    command=self._clear_all)
        self._clear_btn.pack(side="left", ipady=10, ipadx=14)

        # ── Separator ──────────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(side="bottom", fill="x")

        # ── Scrollable main area ───────────────────────────────────────────────
        outer = tk.Frame(self, bg=BG)
        outer.pack(side="top", fill="both", expand=True)

        self._main_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient="vertical", command=self._main_canvas.yview)
        self._main_canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")
        self._main_canvas.pack(side="left", fill="both", expand=True)

        self._scroll_frame = tk.Frame(self._main_canvas, bg=BG)
        self._scroll_win = self._main_canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw")

        self._scroll_frame.bind("<Configure>", self._on_scroll_configure)
        self._main_canvas.bind("<Configure>", self._on_canvas_resize)

        # Mouse wheel scrolling
        self._main_canvas.bind_all("<MouseWheel>",
            lambda e: self._main_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Build all content inside self._scroll_frame
        self._build_content(ttk)

    def _on_scroll_configure(self, _e):
        self._main_canvas.configure(scrollregion=self._main_canvas.bbox("all"))

    def _on_canvas_resize(self, e):
        self._main_canvas.itemconfig(self._scroll_win, width=e.width)

    def _build_content(self, ttk):
        f = self._scroll_frame

        # ── Title ──────────────────────────────────────────────────────────────
        tk.Label(f, text="LONG-FORM EXPLAINER VIDEO MAKER",
                 bg=BG, fg=ACCENT,
                 font=("Consolas", 15, "bold")).pack(pady=(18, 2))
        tk.Label(f, text="AI Script  •  Kokoro TTS  •  1080×1920 MP4  •  Fully Local",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 9)).pack(pady=(0, 18))

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 1 — Transcript & Script
        # ══════════════════════════════════════════════════════════════════════
        PHASE_FG = "#e94560"
        tk.Label(f, text="▸ PHASE 1 — Transcript & Script",
                 bg=BG, fg=PHASE_FG,
                 font=("Consolas", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=24, pady=(0, 4))
        tk.Label(f, text="  1. Paste a reference transcript  →  2. Copy Prompt 1 to AI  →  3. Paste AI's JSON below",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 8), anchor="w"
                 ).pack(fill="x", padx=24, pady=(0, 8))

        # ── Step 1: Reference Transcript ────────────────────────────────────
        lf_t = tk.LabelFrame(f, text=" Step 1 — Reference Transcript (paste from famous video) ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_t.pack(fill="x", padx=24, pady=(0, 6))

        self._transcript_box = tk.Text(lf_t, bg=SURFACE2, fg="#d4a8d4",
                                       insertbackground=ACCENT,
                                       font=("Consolas", 10),
                                       height=7, relief="flat", bd=8, wrap="word")
        self._transcript_box.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(lf_t,
                 text="Paste the transcript of a famous video here. Prompt 1 will use it as the flow reference.",
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7)).pack(anchor="w", padx=12, pady=(0, 8))

        # ── Step 2: Copy Prompt 1 ───────────────────────────────────────────
        self._copy_btn1 = tk.Button(
            f, text="📋  Step 2 — COPY PROMPT 1 → AI  (Generates script JSON)",
            bg=BORDER, fg="#a8d8ea",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a", activeforeground=FG_GREEN,
            command=self._copy_prompt1)
        self._copy_btn1.pack(fill="x", padx=24, ipady=7, pady=(0, 6))

        # ── Step 3: Script Segments JSON ────────────────────────────────────
        lf_s = tk.LabelFrame(f, text=" Step 3 — Script Segments JSON (paste AI output here) ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_s.pack(fill="x", padx=24, pady=(0, 10))

        script_row = tk.Frame(lf_s, bg=SURFACE2)
        script_row.pack(fill="x", padx=10, pady=(10, 4))

        self._script_box = tk.Text(script_row, bg=SURFACE2, fg="#a8d8a8",
                                   insertbackground=ACCENT,
                                   font=("Consolas", 10),
                                   height=10, relief="flat", bd=8, wrap="word",
                                   yscrollcommand=lambda *a: _script_sb.set(*a))
        _script_sb = ttk.Scrollbar(script_row, orient="vertical",
                                   command=self._script_box.yview)
        _script_sb.pack(side="right", fill="y")
        self._script_box.pack(side="left", fill="x", expand=True)

        tk.Label(lf_s, text=HINT_JSON, bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7), justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 2 — Image Prompts & Selection
        # ══════════════════════════════════════════════════════════════════════
        tk.Label(f, text="▸ PHASE 2 — Image Prompts & Selection",
                 bg=BG, fg=PHASE_FG,
                 font=("Consolas", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=24, pady=(16, 4))
        tk.Label(f, text="  4. Copy Prompt 2 to AI  →  5. Generate & download images  →  6. Place in assets/images/ folder",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 8), anchor="w"
                 ).pack(fill="x", padx=24, pady=(0, 8))

        # ── Step 4: Copy Prompt 2 ───────────────────────────────────────────
        self._copy_btn2 = tk.Button(
            f, text="📋  Step 4 — COPY PROMPT 2 → AI  (Generates image prompts)",
            bg=BORDER, fg="#a8d8ea",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a", activeforeground=FG_GREEN,
            command=self._copy_prompt2)
        self._copy_btn2.pack(fill="x", padx=24, ipady=7, pady=(0, 6))

        # ── Steps 5-6: Images — auto-detected ───────────────────────────────
        lf_i = tk.LabelFrame(f, text=" Steps 5-6 — Images (auto-detected from assets/images/) ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_i.pack(fill="x", padx=24, pady=(0, 10))

        scan_row = tk.Frame(lf_i, bg=SURFACE)
        scan_row.pack(fill="x", padx=10, pady=(10, 4))

        self._scan_btn = tk.Button(scan_row, text="🔍  SCAN IMAGES",
                                   bg=SURFACE2, fg=FG_GREEN,
                                   font=("Consolas", 9, "bold"),
                                   relief="flat", cursor="hand2",
                                   activebackground=BORDER, activeforeground=FG_GREEN,
                                   command=self._scan_and_display_images)
        self._scan_btn.pack(side="left", ipady=4, ipadx=8)

        self._img_status_var = tk.StringVar(value="Not scanned yet.")
        tk.Label(scan_row, textvariable=self._img_status_var,
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 8)).pack(side="left", padx=(10, 0))

        self._img_list_box = tk.Text(lf_i, bg=SURFACE2, fg="#a8d8a8",
                                     font=("Consolas", 9),
                                     height=6, relief="flat", bd=8, wrap="word",
                                     state="disabled")
        self._img_list_box.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(lf_i,
                 text="Name files starting with the image number: 1_desc.png, 2_name.jpg, 3_idea.webp (first character = slot number)",
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7)).pack(anchor="w", padx=12, pady=(0, 8))

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 3 — Title, Description & Tags
        # ══════════════════════════════════════════════════════════════════════
        tk.Label(f, text="▸ PHASE 3 — Title, Description & Tags",
                 bg=BG, fg=PHASE_FG,
                 font=("Consolas", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=24, pady=(16, 4))
        tk.Label(f, text="  7. Copy Prompt 3 to AI  →  8. Paste AI's JSON output below",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 8), anchor="w"
                 ).pack(fill="x", padx=24, pady=(0, 8))

        # ── Step 7: Copy Prompt 3 ───────────────────────────────────────────
        self._copy_btn3 = tk.Button(
            f, text="📋  Step 7 — COPY PROMPT 3 → AI  (Generates title, description & tags JSON)",
            bg=BORDER, fg="#f0c87a",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a", activeforeground=FG_GREEN,
            command=self._copy_prompt3)
        self._copy_btn3.pack(fill="x", padx=24, ipady=7, pady=(0, 6))

        # ── Step 8: Video Details JSON ──────────────────────────────────────
        lf_d = tk.LabelFrame(f, text=" Step 8 — Video Details JSON (paste AI output here) ",
                             bg=SURFACE, fg="#f0c87a", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_d.pack(fill="x", padx=24, pady=(0, 10))

        self._details_box = tk.Text(lf_d, bg=SURFACE2, fg="#f0c87a",
                                    insertbackground=ACCENT,
                                    font=("Consolas", 10),
                                    height=6, relief="flat", bd=8, wrap="word")
        self._details_box.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(lf_d,
                 text='Paste the {"title":…,"description":…,"tags":[…]} JSON here. '
                      'Title becomes the filename; full JSON saved as .txt alongside the MP4.',
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7), wraplength=660, justify="left"
                 ).pack(anchor="w", padx=12, pady=(0, 8))

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 4 — Render Video
        # ══════════════════════════════════════════════════════════════════════
        tk.Label(f, text="▸ PHASE 4 — Render Video",
                 bg=BG, fg=PHASE_FG,
                 font=("Consolas", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=24, pady=(16, 4))
        tk.Label(f, text="  9. Click GENERATE VIDEO below  →  MP4 + .txt saved in output/ folder",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 8), anchor="w"
                 ).pack(fill="x", padx=24, pady=(0, 8))

        # ── Progress ───────────────────────────────────────────────────────────
        lf_p = tk.LabelFrame(f, text=" Progress ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_p.pack(fill="x", padx=24, pady=(0, 10))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("EXP.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT, thickness=8)
        self._pb = ttk.Progressbar(lf_p, style="EXP.Horizontal.TProgressbar",
                                   orient="horizontal", mode="determinate")
        self._pb.pack(fill="x", padx=14, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(lf_p, textvariable=self._status_var,
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 8)).pack(anchor="w", padx=14, pady=(0, 6))

        # ── Log ────────────────────────────────────────────────────────────────
        lf_l = tk.LabelFrame(f, text=" Log ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_l.pack(fill="x", padx=24, pady=(0, 20))

        self._log_box = tk.Text(lf_l, bg=SURFACE2, fg=FG_GREEN,
                                font=("Consolas", 9),
                                height=5, relief="flat", bd=6,
                                state="disabled", wrap="word")
        self._log_box.pack(fill="x", padx=10, pady=8)

        # Auto-scan images on startup
        self._scan_and_display_images()

    # ── Image scanning ─────────────────────────────────────────────────────────
    @staticmethod
    def _parse_image_num(fname):
        digits = ''
        for ch in fname:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) if digits else None

    def _build_image_map(self):
        """Scan assets/images/ and return {image_number: file_path}."""
        if not os.path.isdir(ASSETS_IMAGES):
            return {}
        image_map = {}
        for fname in os.listdir(ASSETS_IMAGES):
            if fname.startswith('.'):
                continue
            path = os.path.join(ASSETS_IMAGES, fname)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
                continue
            num = self._parse_image_num(fname)
            if num is not None:
                image_map[num] = path
        return dict(sorted(image_map.items()))

    def _scan_and_display_images(self):
        if not os.path.isdir(ASSETS_IMAGES):
            self._img_status_var.set(f"❌ Folder not found: assets/images/")
            self._img_list_box.config(state="normal")
            self._img_list_box.delete("1.0", "end")
            self._img_list_box.config(state="disabled")
            return

        found = []
        for fname in os.listdir(ASSETS_IMAGES):
            if fname.startswith('.'):
                continue
            path = os.path.join(ASSETS_IMAGES, fname)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ('.png', '.jpg', '.jpeg', '.webp', '.bmp'):
                continue
            num = self._parse_image_num(fname)
            if num is not None:
                found.append((num, fname))

        found.sort(key=lambda x: x[0])

        self._img_list_box.config(state="normal")
        self._img_list_box.delete("1.0", "end")
        if not found:
            self._img_list_box.insert("end", "  No valid images found.\n")
            self._img_list_box.insert("end", "  Place images in: assets/images/\n")
            self._img_list_box.insert("end", "  Name files like: 1_desc.png, 2_name.jpg\n")
            self._img_status_var.set("❌ No images detected.")
        else:
            for num, fname in found:
                self._img_list_box.insert("end", f"  [{num:02d}] {fname}  ✅\n")
            self._img_status_var.set(f"✅ {len(found)} image(s) loaded from assets/images/")
        self._img_list_box.config(state="disabled")

    def _clear_image_display(self):
        self._img_list_box.config(state="normal")
        self._img_list_box.delete("1.0", "end")
        self._img_list_box.config(state="disabled")
        self._img_status_var.set("Not scanned yet.")

    # ── Clear all ──────────────────────────────────────────────────────────────
    def _clear_all(self):
        if self._running:
            return
        if not messagebox.askyesno("Clear All Data",
                                   "Clear the transcript, script JSON, video details, and the log?"):
            return
        self._script_box.delete("1.0", "end")
        self._transcript_box.delete("1.0", "end")
        self._details_box.delete("1.0", "end")
        self._clear_image_display()
        self._clear_log()
        self._set_progress(0)
        self._set_status("Ready.")

    # ── Copy prompts ───────────────────────────────────────────────────────────
    def _copy_prompt1(self):
        transcript = self._transcript_box.get("1.0", "end").strip()
        if not transcript:
            messagebox.showwarning("No Transcript",
                                   "Paste a transcript first before copying Prompt 1.")
            return
        prompt = MASTER_PROMPT1.replace("[TRANSCRIPT]", transcript)
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self._copy_btn1.config(bg="#1a472a", fg=FG_GREEN, text="✅  COPIED! (Prompt 1)")
        self.after(2000, lambda: self._copy_btn1.config(
            bg=BORDER, fg="#a8d8ea", text="📋  COPY PROMPT 1  (Script)"))

    def _copy_prompt2(self):
        self.clipboard_clear()
        self.clipboard_append(MASTER_PROMPT2)
        self._copy_btn2.config(bg="#1a472a", fg=FG_GREEN, text="✅  COPIED! (Prompt 2)")
        self.after(2000, lambda: self._copy_btn2.config(
            bg=BORDER, fg="#a8d8ea", text="📋  COPY PROMPT 2  (Images)"))

    def _copy_prompt3(self):
        script = self._script_box.get("1.0", "end").strip()
        if not script:
            messagebox.showwarning("No Script JSON",
                                   "Paste your script JSON first before copying Prompt 3.")
            return
        prompt = MASTER_PROMPT3.replace("[SCRIPT_JSON]", script)
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self._copy_btn3.config(bg="#1a472a", fg=FG_GREEN, text="✅  COPIED! (Prompt 3)")
        self.after(2000, lambda: self._copy_btn3.config(
            bg=BORDER, fg="#f0c87a", text="📋  COPY PROMPT 3  (Title, Description & Tags)"))

    # ── Log helpers ────────────────────────────────────────────────────────────
    def _log(self, msg):
        self._log_box.config(state="normal")
        self._log_box.insert("end", msg + "\n")
        self._log_box.see("end")
        self._log_box.config(state="disabled")

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    def _set_progress(self, pct):
        self._pb["value"] = pct

    def _set_status(self, msg):
        self._status_var.set(msg)

    # ── Validate & launch ──────────────────────────────────────────────────────
    def _on_generate(self):
        if self._running:
            return

        raw = self._script_box.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Empty Script", "Paste your script JSON first.")
            return
        try:
            segments = json.loads(raw)
            if not isinstance(segments, list) or not segments:
                raise ValueError("Must be a non-empty JSON array.")
            for seg in segments:
                seg_id = seg.get("segment", "?")
                if "microsegments" not in seg:
                    raise ValueError(
                        f'Segment {seg_id} missing "microsegments" key.')
                if not isinstance(seg["microsegments"], list) or not seg["microsegments"]:
                    raise ValueError(f'Segment {seg_id} "microsegments" must be a non-empty list.')
                for j, micro in enumerate(seg["microsegments"]):
                    if "text" not in micro:
                        raise ValueError(f'Segment {seg_id}, micro {j+1}: missing "text".')
                    if "image" not in micro:
                        raise ValueError(f'Segment {seg_id}, micro {j+1}: missing "image".')
                    if not isinstance(micro["image"], int) or micro["image"] < 1:
                        raise ValueError(
                            f'Segment {seg_id}, micro {j+1}: '
                            f'"image" must be a positive integer, got {micro["image"]!r}.')
                    valid_poses = {"asking","authority","emphasis","explaining","pointingLeft"}
                    if "pose" in micro and micro["pose"] is not None and micro["pose"] not in valid_poses:
                        raise ValueError(
                            f'Segment {seg_id}, micro {j+1}: '
                            f'"pose" must be one of {sorted(valid_poses)} or null, got {micro["pose"]!r}.')
        except Exception as e:
            messagebox.showerror("Invalid JSON", f"Script JSON error:\n{e}")
            return

        all_image_nums = []
        seen = set()
        for seg in segments:
            for micro in seg["microsegments"]:
                n = micro["image"]
                if n in seen:
                    messagebox.showerror("Duplicate Image Number",
                        f'Image number {n} appears more than once.')
                    return
                seen.add(n)
                all_image_nums.append(n)

        self._scan_and_display_images()
        image_map = self._build_image_map()
        if not image_map:
            messagebox.showerror("No Images",
                "No images found in assets/images/.\n"
                "Place your generated images there first.\n"
                "Name files like: 1_desc.png, 2_name.jpg, 3_idea.webp")
            return

        missing = sorted(set(all_image_nums) - set(image_map.keys()))
        if missing:
            messagebox.showerror("Missing Images",
                f"Script references image number(s) {missing} but no matching files.\n"
                f"Available images for slots: {sorted(image_map.keys())}")
            return

        self._running = True
        self._gen_btn.config(state="disabled")
        self._clear_log()
        self._set_progress(0)
        self._set_status("Starting pipeline...")

        # ── Parse Video Details JSON (optional but warned) ─────────────────────
        details_raw = self._details_box.get("1.0", "end").strip()
        video_title = None
        details_json = None
        if details_raw:
            try:
                details_json = json.loads(details_raw)
                video_title = details_json.get("title", "").strip() or None
            except Exception:
                messagebox.showwarning(
                    "Details JSON Invalid",
                    "The Video Details box does not contain valid JSON.\n"
                    "The video will be saved with a timestamp filename and no .txt will be written.")
                details_json = None

        def run():
            try:
                from render_explainer import render_explainer_video
                out = render_explainer_video(
                    segments=segments,
                    image_map=image_map,
                    output_folder=OUTPUT_FOLDER,
                    kokoro_model=KOKORO_MODEL,
                    kokoro_voice=KOKORO_VOICE,
                    log_fn=lambda m: self.after(0, lambda msg=m: self._log(msg)),
                    progress_fn=lambda p: self.after(0, lambda pct=p: self._set_progress(pct)),
                    status_fn=lambda s: self.after(0, lambda st=s: self._set_status(st)),
                    video_title=video_title,
                )
                # ── Write .txt sidecar with the Prompt 3 JSON ─────────────────
                if details_json is not None:
                    txt_path = os.path.splitext(out)[0] + ".txt"
                    try:
                        with open(txt_path, "w", encoding="utf-8") as fh:
                            fh.write(f"title:\n{details_json.get('title', '')}\n\n")
                            fh.write(f"description:\n{details_json.get('description', '')}\n\n")
                            tags = details_json.get('tags', [])
                            fh.write(f"tags:\n{', '.join(tags)}\n")
                        self.after(0, lambda tp=txt_path: self._log(
                            f"📄 Details saved: output/{os.path.basename(tp)}"))
                    except Exception as te:
                        self.after(0, lambda e=str(te): self._log(f"⚠ Could not write .txt: {e}"))

                self.after(0, lambda: self._set_progress(100))
                self.after(0, lambda: self._set_status(f"Done → {os.path.basename(out)}"))
                self.after(0, lambda: self._log(f"✅ Saved: output/{os.path.basename(out)}"))
            except Exception as ex:
                import traceback
                tb = traceback.format_exc()
                self.after(0, lambda e=str(ex): self._log(f"❌ Error: {e}"))
                self.after(0, lambda t=tb: self._log(t))
                self.after(0, lambda: self._set_status("Failed."))
                self.after(0, lambda: self._set_progress(0))
            finally:
                self._running = False
                self.after(0, lambda: self._gen_btn.config(state="normal"))

        threading.Thread(target=run, daemon=True).start()


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ExplainerApp()
    app.mainloop()
