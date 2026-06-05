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

HINT_JSON = (
    'Each segment has microsegments — one image per microsegment:\n'
    '[\n'
    '  {"segment": 1, "microsegments": [\n'
    '    {"text": "Hook line.", "image": 1},\n'
    '    {"text": "Next beat.", "image": 2}\n'
    '  ]},\n'
    '  {"segment": 2, "microsegments": [\n'
    '    {"text": "New idea.", "image": 3}\n'
    '  ]}\n'
    ']\n'
    "image numbers: global, sequential, no duplicates, no gaps."
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
        self._image_slots = []
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
        tk.Label(f, text="AI Script  •  Equal Segments  •  Kokoro TTS  •  YouTube MP4  •  Local",
                 bg=BG, fg=FG_MUTED,
                 font=("Consolas", 9)).pack(pady=(0, 12))

        # ── Copy Prompt buttons ────────────────────────────────────────────────
        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill="x", padx=24, pady=(0, 12))

        self._copy_btn1 = tk.Button(
            btn_row, text="📋  COPY PROMPT 1  (Script)",
            bg=BORDER, fg="#a8d8ea",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a", activeforeground=FG_GREEN,
            command=self._copy_prompt1)
        self._copy_btn1.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 6))

        self._copy_btn2 = tk.Button(
            btn_row, text="📋  COPY PROMPT 2  (Images)",
            bg=BORDER, fg="#a8d8ea",
            font=("Consolas", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground="#1a472a", activeforeground=FG_GREEN,
            command=self._copy_prompt2)
        self._copy_btn2.pack(side="left", fill="x", expand=True, ipady=7)

        # ── Transcript ────────────────────────────────────────────────────────
        lf_t = tk.LabelFrame(f, text=" Reference Transcript (paste from famous video) ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_t.pack(fill="x", padx=24, pady=(0, 10))

        self._transcript_box = tk.Text(lf_t, bg=SURFACE2, fg="#d4a8d4",
                                       insertbackground=ACCENT,
                                       font=("Consolas", 10),
                                       height=7, relief="flat", bd=8, wrap="word")
        self._transcript_box.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(lf_t,
                 text="Paste the transcript here. Prompt 1 will use it as the flow reference.",
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7)).pack(anchor="w", padx=12, pady=(0, 8))

        # ── Script JSON ────────────────────────────────────────────────────────
        lf_s = tk.LabelFrame(f, text=" Script Segments (JSON) ",
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

        # ── Images panel ───────────────────────────────────────────────────────
        lf_i = tk.LabelFrame(f, text=" Images — Content frames only (thumbnail generated separately) ",
                             bg=SURFACE, fg="#aaa", bd=1, relief="flat",
                             font=("Consolas", 9))
        lf_i.pack(fill="x", padx=24, pady=(0, 10))

        self._img_canvas = tk.Canvas(lf_i, bg=SURFACE, height=160, highlightthickness=0)
        self._img_scrollbar = ttk.Scrollbar(lf_i, orient="vertical",
                                            command=self._img_canvas.yview)
        self._img_canvas.configure(yscrollcommand=self._img_scrollbar.set)
        self._img_scrollbar.pack(side="right", fill="y", pady=6)
        self._img_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=6)

        self._img_inner = tk.Frame(self._img_canvas, bg=SURFACE)
        self._img_canvas_win = self._img_canvas.create_window(
            (0, 0), window=self._img_inner, anchor="nw")
        self._img_inner.bind("<Configure>", self._on_inner_configure)
        self._img_canvas.bind("<Configure>", self._on_img_canvas_configure)

        add_row = tk.Frame(lf_i, bg=SURFACE)
        add_row.pack(fill="x", padx=10, pady=(0, 8))
        tk.Button(add_row, text="＋  ADD IMAGE SLOT",
                  bg=SURFACE2, fg=FG_GREEN,
                  font=("Consolas", 9, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=BORDER, activeforeground=FG_GREEN,
                  command=self._add_image_slot).pack(side="left", padx=(0, 8), ipady=4, ipadx=8)
        tk.Label(add_row,
                 text="Add one slot per image beat (expect 30-80 total). Thumbnail NOT uploaded here.",
                 bg=SURFACE, fg=FG_MUTED,
                 font=("Consolas", 7)).pack(side="left")

        for _ in range(5):
            self._add_image_slot()

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

    # ── Canvas scroll helpers ──────────────────────────────────────────────────
    def _on_inner_configure(self, _e):
        self._img_canvas.configure(scrollregion=self._img_canvas.bbox("all"))

    def _on_img_canvas_configure(self, e):
        self._img_canvas.itemconfig(self._img_canvas_win, width=e.width)

    # ── Image slot management ──────────────────────────────────────────────────
    def _add_image_slot(self):
        idx  = len(self._image_slots) + 1
        slot = {"path": None}

        row = tk.Frame(self._img_inner, bg=SURFACE)
        row.pack(fill="x", padx=4, pady=3)

        num_lbl = tk.Label(row, text=f"[{idx:02d}]",
                           bg=SURFACE, fg=FG_MUTED,
                           font=("Consolas", 9, "bold"), width=10)
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

        tk.Button(row, text="📂", bg=BORDER, fg="#a8d8ea",
                  font=("Consolas", 9), relief="flat", cursor="hand2",
                  command=browse).pack(side="left", padx=(4, 2), ipady=3, ipadx=4)

        tk.Button(row, text="✕", bg=SURFACE2, fg=ACCENT,
                  font=("Consolas", 9), relief="flat", cursor="hand2",
                  command=remove).pack(side="left", padx=(0, 4), ipady=3, ipadx=4)

        slot["frame"]   = row
        slot["num_lbl"] = num_lbl
        slot["path_lbl"]= path_lbl
        self._image_slots.append(slot)

    def _renumber_slots(self):
        for i, slot in enumerate(self._image_slots, 1):
            slot["num_lbl"].config(text=f"[{i:02d}]", fg=FG_MUTED)

    # ── Clear all ──────────────────────────────────────────────────────────────
    def _clear_all(self):
        if self._running:
            return
        if not messagebox.askyesno("Clear All Data",
                                   "Clear the transcript, script JSON, all image slots, and the log?"):
            return
        self._script_box.delete("1.0", "end")
        self._transcript_box.delete("1.0", "end")
        for slot in self._image_slots:
            slot["frame"].destroy()
        self._image_slots.clear()
        for _ in range(5):
            self._add_image_slot()
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

        image_map = {}
        for i, slot in enumerate(self._image_slots, 1):
            if slot["path"] is None:
                messagebox.showwarning("Missing Image",
                    f"Image slot [{i:02d}] has no file selected.")
                return
            image_map[i] = slot["path"]

        missing = sorted(set(all_image_nums) - set(image_map.keys()))
        if missing:
            messagebox.showerror("Missing Image Slots",
                f"Segments reference image(s) {missing} but those slots don't exist.\n"
                f"You have {len(self._image_slots)} slot(s).")
            return

        unused = sorted(set(image_map.keys()) - set(all_image_nums))
        if unused:
            if not messagebox.askyesno("Unused Slots",
                f"Image slot(s) {unused} are loaded but not referenced.\n"
                f"They will be ignored. Continue?"):
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
