# -*- coding: utf-8 -*-
# explainer-video-maker.py — AI Explainer Video Maker
# Run via run_explainer-video-maker.vbs

import tkinter as tk
from tkinter import messagebox, filedialog
import threading
import os
import json

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "output")
IMAGES_FOLDER = os.path.join(SCRIPT_DIR, "images")
KOKORO_MODEL  = os.path.join(SCRIPT_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICE  = os.path.join(SCRIPT_DIR, "voices-v1.0.bin")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
SURFACE  = "#16213e"
SURFACE2 = "#0d0d1a"
BORDER   = "#0f3460"
ACCENT   = "#e94560"
FG_GREEN = "#7fcc7f"
FG_MUTED = "#888888"


MASTER_PROMPT = """\
Generate a viral TikTok educational visual package for the given topic.
TOPIC: [INSERT TOPIC HERE]
GOAL:
Create:
1. A JSON array of script segments (for direct use in the app)
2. A flexible number of standalone image prompts (plain text, for copy-pasting to an image AI)
Each segment maps one chunk of narration to one image number.
Each image must fully explain one idea from the script and must be usable independently without any shared context.
---
OUTPUT FORMAT (STRICT):

Script Segments JSON:
Output a raw JSON array. No markdown fences, no explanation before or after — just the array.
Each object must have exactly these three fields:
  "segment" — integer, starting from 1
  "text"    — the narration chunk for that segment, optimized for TTS
  "image"   — integer matching the Image Prompt number below

Example structure (do not copy this content, only the shape):
[
  {"segment": 1, "text": "Hook line here.", "image": 1},
  {"segment": 2, "text": "Explanation here.", "image": 2},
  {"segment": 3, "text": "Payoff here.", "image": 3}
]

Rules for splitting segments:
- Each segment must correspond to exactly ONE image
- Split at natural breath/idea boundaries — not mid-sentence
- Every idea in the script must be covered — no leftover narration
- Add as many segments as needed (NO LIMIT)

---
Image Prompts:
Image 1:
[Standalone visual prompt fully explaining one key idea from the script]
Image 2:
[Standalone visual prompt fully explaining another key idea]
Image 3:
[Standalone visual prompt fully explaining another key idea]
Image 4:
[Add more images as needed until ALL ideas in the script are visually covered]
---
CRITICAL IMAGE RULE (MOST IMPORTANT):
Each image prompt must be FULLY SELF-CONTAINED.
That means EVERY image must include BOTH:
1. The visual concept (what is happening)
2. The full drawing + style instruction (so it works independently)
You MUST repeat the STYLE BLOCK inside EVERY IMAGE PROMPT.
---
STYLE BLOCK (MUST BE APPENDED TO EVERY IMAGE):
Draw the subject as a rough artist sketch using loose, confident pencil lines. Keep visible construction lines, exploratory strokes, and unfinished details. The artwork should feel like an artist's first draft rather than a finished illustration. Use simple graphite-style linework, natural hand-drawn imperfections, overlapping sketch marks, and light rough shading where needed. Avoid polished rendering, vector art, digital painting, realism, or clean cartoon outlines. Maintain an authentic concept-sketch appearance with expressive line variation and organic strokes. Pure white background, isolated subject, no notebook, no paper texture, no shadows, no text, no borders, no additional objects.
AND ALSO INCLUDE THIS VISUAL CONSTRAINT:
Strict monochrome graphite pencil sketch ONLY. No color, no gradients, no lighting effects, no 3D rendering, no ink wash, no realism.
---
IMAGE STRUCTURE RULE (VERY IMPORTANT):
Each image must follow this format:
Image X:
[Core idea / scene description]
STYLE:
[PASTE FULL STYLE BLOCK HERE]
---
VIRAL CONTENT RULES:
- Script must be continuous and optimized for TTS
- Must include hook → explanation → payoff structure
- Each image must represent ONE distinct idea from the script
- Add as many segments/images as needed (NO LIMIT)
- No overlapping meaning between images
- Prioritize clarity, speed of understanding, and rewatchability
- The number of JSON segments MUST equal the number of Image Prompts\
"""


HINT_JSON = (
    "JSON format — one entry per image:\n"
    '[\n'
    '  {"segment": 1, "text": "Hook line here.", "image": 1},\n'
    '  {"segment": 2, "text": "Explanation here.", "image": 2},\n'
    '  {"segment": 3, "text": "Payoff here.", "image": 3}\n'
    ']\n'
    "Each segment maps one script chunk to one image number."
)


# ── Main App ───────────────────────────────────────────────────────────────────
class ExplainerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Explainer Video Maker")
        self.geometry("720x900")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._running = False
        self._image_slots = []   # list of {"path": str, "frame": Frame, "label": Label}
        self._build_ui()

    def _build_ui(self):
        import tkinter.ttk as ttk

        # ── Title ──────────────────────────────────────────────────────────────
        tk.Label(self, text="EXPLAINER VIDEO MAKER",
                 bg=BG, fg=ACCENT,
                 font=("Consolas", 15, "bold")).pack(pady=(18, 2))
        tk.Label(self, text="AI Script  •  Kokoro TTS  •  MP4 output  •  Local",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 9)).pack(pady=(0, 12))

        # ── Copy Master Prompt ─────────────────────────────────────────────────
        self._copy_btn = tk.Button(
            self, text="📋  COPY MASTER PROMPT",
            bg=BORDER, fg="#a8d8ea",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a",
            activeforeground=FG_GREEN,
            command=self._copy_prompt)
        self._copy_btn.pack(fill="x", padx=24, pady=(0, 12), ipady=7)

        # ── Script JSON input ──────────────────────────────────────────────────
        lf_script = tk.LabelFrame(self, text=" Script Segments (JSON) ",
                                  bg=SURFACE, fg="#aaa",
                                  bd=1, relief="flat",
                                  font=("Consolas", 9))
        lf_script.pack(fill="x", padx=24, pady=(0, 10))

        self._script_box = tk.Text(lf_script,
                                   bg=SURFACE2, fg="#a8d8a8",
                                   insertbackground=ACCENT,
                                   font=("Consolas", 10),
                                   height=10, relief="flat", bd=8,
                                   wrap="word")
        self._script_box.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(lf_script, text=HINT_JSON,
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7),
                 justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        # ── Images panel ───────────────────────────────────────────────────────
        lf_images = tk.LabelFrame(self, text=" Images (in sequence) ",
                                  bg=SURFACE, fg="#aaa",
                                  bd=1, relief="flat",
                                  font=("Consolas", 9))
        lf_images.pack(fill="x", padx=24, pady=(0, 10))

        # Scrollable canvas for image slots
        self._img_canvas = tk.Canvas(lf_images, bg=SURFACE,
                                     height=160, highlightthickness=0)
        self._img_scrollbar = ttk.Scrollbar(lf_images, orient="vertical",
                                            command=self._img_canvas.yview)
        self._img_canvas.configure(yscrollcommand=self._img_scrollbar.set)
        self._img_scrollbar.pack(side="right", fill="y", pady=6)
        self._img_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6)

        self._img_inner = tk.Frame(self._img_canvas, bg=SURFACE)
        self._img_canvas_win = self._img_canvas.create_window(
            (0, 0), window=self._img_inner, anchor="nw")
        self._img_inner.bind("<Configure>", self._on_inner_configure)
        self._img_canvas.bind("<Configure>", self._on_canvas_configure)

        # + Add Image button
        add_row = tk.Frame(lf_images, bg=SURFACE)
        add_row.pack(fill="x", padx=10, pady=(0, 8))
        tk.Button(add_row, text="＋  ADD IMAGE SLOT",
                  bg=SURFACE2, fg=FG_GREEN,
                  font=("Consolas", 9, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=BORDER,
                  activeforeground=FG_GREEN,
                  command=self._add_image_slot).pack(side="left", padx=(0, 8), ipady=4, ipadx=8)
        tk.Label(add_row,
                 text="Slots are ordered — Image 1 maps to segment image:1",
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7)).pack(side="left")

        # Seed 3 slots by default
        for _ in range(3):
            self._add_image_slot()


        # ── Progress ───────────────────────────────────────────────────────────
        lf_prog = tk.LabelFrame(self, text=" Progress ",
                                bg=SURFACE, fg="#aaa",
                                bd=1, relief="flat",
                                font=("Consolas", 9))
        lf_prog.pack(fill="x", padx=24, pady=(0, 10))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("EXP.Horizontal.TProgressbar",
                         troughcolor=SURFACE2,
                         background=ACCENT,
                         thickness=8)
        self._pb = ttk.Progressbar(lf_prog, style="EXP.Horizontal.TProgressbar",
                                   orient="horizontal", length=640, mode="determinate")
        self._pb.pack(padx=14, pady=10)

        self._status_var = tk.StringVar(value="Ready.")
        tk.Label(lf_prog, textvariable=self._status_var,
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 8)).pack(anchor="w", padx=14, pady=(0, 6))

        # ── Log ────────────────────────────────────────────────────────────────
        lf_log = tk.LabelFrame(self, text=" Log ",
                               bg=SURFACE, fg="#aaa",
                               bd=1, relief="flat",
                               font=("Consolas", 9))
        lf_log.pack(fill="x", padx=24, pady=(0, 12))

        self._log_box = tk.Text(lf_log,
                                bg=SURFACE2, fg=FG_GREEN,
                                font=("Consolas", 9),
                                height=5, relief="flat", bd=6,
                                state="disabled", wrap="word")
        self._log_box.pack(fill="x", padx=10, pady=8)

        # ── Generate Button ────────────────────────────────────────────────────
        self._gen_btn = tk.Button(self,
                                  text="GENERATE VIDEO",
                                  bg=ACCENT, fg="white",
                                  font=("Consolas", 12, "bold"),
                                  relief="flat", cursor="hand2",
                                  activebackground="#c73652",
                                  activeforeground="white",
                                  command=self._on_generate)
        self._gen_btn.pack(fill="x", padx=24, pady=(0, 20), ipady=10)

    # ── Canvas scroll helpers ──────────────────────────────────────────────────
    def _on_inner_configure(self, _event):
        self._img_canvas.configure(scrollregion=self._img_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._img_canvas.itemconfig(self._img_canvas_win, width=event.width)

    # ── Image slot management ──────────────────────────────────────────────────
    def _add_image_slot(self):
        idx = len(self._image_slots) + 1
        slot = {"path": None}

        row = tk.Frame(self._img_inner, bg=SURFACE)
        row.pack(fill="x", padx=4, pady=3)

        num_lbl = tk.Label(row, text=f"[{idx:02d}]",
                           bg=SURFACE, fg=FG_MUTED,
                           font=("Consolas", 9, "bold"), width=5)
        num_lbl.pack(side="left")

        path_lbl = tk.Label(row, text="— no image selected —",
                            bg=SURFACE2, fg=FG_MUTED,
                            font=("Consolas", 9), anchor="w",
                            relief="flat", padx=8)
        path_lbl.pack(side="left", fill="x", expand=True, ipady=4)

        def browse(s=slot, lbl=path_lbl):
            p = filedialog.askopenfilename(
                title="Select Image",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp")])
            if p:
                s["path"] = p
                lbl.config(text=os.path.basename(p), fg=FG_GREEN)

        def remove(r=row, s=slot):
            r.destroy()
            self._image_slots.remove(s)
            self._renumber_slots()

        tk.Button(row, text="📂",
                  bg=BORDER, fg="#a8d8ea",
                  font=("Consolas", 9),
                  relief="flat", cursor="hand2",
                  command=browse).pack(side="left", padx=(4, 2), ipady=3, ipadx=4)

        tk.Button(row, text="✕",
                  bg=SURFACE2, fg="#e94560",
                  font=("Consolas", 9),
                  relief="flat", cursor="hand2",
                  command=remove).pack(side="left", padx=(0, 4), ipady=3, ipadx=4)

        slot["frame"] = row
        slot["num_lbl"] = num_lbl
        slot["path_lbl"] = path_lbl
        self._image_slots.append(slot)

    def _renumber_slots(self):
        for i, slot in enumerate(self._image_slots, 1):
            slot["num_lbl"].config(text=f"[{i:02d}]")


    # ── Copy prompt ────────────────────────────────────────────────────────────
    def _copy_prompt(self):
        self.clipboard_clear()
        self.clipboard_append(MASTER_PROMPT)
        self._copy_btn.config(bg="#1a472a", fg=FG_GREEN, text="✅  COPIED!")
        self.after(2000, lambda: self._copy_btn.config(
            bg=BORDER, fg="#a8d8ea", text="📋  COPY MASTER PROMPT"))

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

        # Parse JSON
        raw = self._script_box.get("1.0", "end").strip()
        if not raw:
            messagebox.showwarning("Empty Script", "Paste your script JSON first.")
            return
        try:
            segments = json.loads(raw)
            if not isinstance(segments, list) or not segments:
                raise ValueError("Must be a non-empty JSON array.")
            for seg in segments:
                if "text" not in seg or "image" not in seg:
                    raise ValueError('Each segment needs "text" and "image" keys.')
        except Exception as e:
            messagebox.showerror("Invalid JSON", f"Script JSON error:\n{e}")
            return

        # Validate image slots
        image_map = {}
        for i, slot in enumerate(self._image_slots, 1):
            if slot["path"] is None:
                messagebox.showwarning("Missing Image",
                    f"Image slot [{i:02d}] has no file selected.")
                return
            image_map[i] = slot["path"]

        # Check all referenced image numbers exist
        missing = set()
        for seg in segments:
            n = seg["image"]
            if n not in image_map:
                missing.add(n)
        if missing:
            messagebox.showerror("Missing Image Slots",
                f"Segments reference image(s) {sorted(missing)} but those slots don't exist.\n"
                f"You have {len(self._image_slots)} slot(s).")
            return

        self._running = True
        self._gen_btn.config(state="disabled")
        self._clear_log()
        self._set_progress(0)
        self._set_status("Starting pipeline...")

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
                )
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
