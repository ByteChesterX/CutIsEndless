#!/usr/bin/env python3
"""
MediaCutter - Modern Video & Audio Cutter
Fast, feature-rich trimming with FFmpeg backend.
"""

import os
import sys
import json
import time
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageTk
import re
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets import ToolTip

APP_TITLE = "MediaCutter"
APP_VERSION = "1.0"
SUPPORTED_VIDEO = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mpg", ".mpeg")
SUPPORTED_AUDIO = (".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus")
SUPPORTED_ALL = SUPPORTED_VIDEO + SUPPORTED_AUDIO
HISTORY_FILE = os.path.expanduser("~/.mediacutter_history.json")


def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_time(text):
    text = text.strip()
    parts = text.replace(",", ".").split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(parts[0])
    except ValueError:
        raise ValueError(f"Geçersiz zaman formatı: {text}")


def get_media_duration(filepath):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", filepath],
            capture_output=True, text=True, timeout=15
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return 0.0


def get_media_info(filepath):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", filepath],
            capture_output=True, text=True, timeout=15
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def is_video_file(filepath):
    return Path(filepath).suffix.lower() in SUPPORTED_VIDEO


def is_audio_file(filepath):
    return Path(filepath).suffix.lower() in SUPPORTED_AUDIO


class ThumbnailGenerator:
    @staticmethod
    def generate(filepath, timestamp=1.0, size=(320, 180)):
        try:
            tmp = os.path.join(os.path.expanduser("~"), ".mediacutter_thumb.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(timestamp), "-i", filepath,
                 "-vframes", "1", "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
                 "-q:v", "3", tmp],
                capture_output=True, timeout=10
            )
            if os.path.exists(tmp):
                img = Image.open(tmp)
                os.remove(tmp)
                return img
        except Exception:
            pass
        return None

    @staticmethod
    def generate_waveform(filepath, width=800, height=120):
        try:
            tmp_raw = os.path.join(os.path.expanduser("~"), ".mediacutter_wave.raw")
            tmp_img = os.path.join(os.path.expanduser("~"), ".mediacutter_wave.png")
            duration = get_media_duration(filepath)
            if duration <= 0:
                return None
            samples = width
            subprocess.run(
                ["ffmpeg", "-y", "-i", filepath, "-ac", "1", "-filter:a",
                 f"aresample={samples},astats=metadata=1:reset=1,ametadata=mode=print:file={tmp_raw}",
                 "-f", "null", "-"],
                capture_output=True, timeout=30
            )
            levels = []
            if os.path.exists(tmp_raw):
                with open(tmp_raw, "r") as f:
                    for line in f:
                        if "lavfi.astats.Overall.RMS_level" in line:
                            val = line.split("=")[1].strip()
                            if val != "-inf":
                                levels.append(abs(float(val)))
                os.remove(tmp_raw)
            if not levels:
                return None
            max_val = max(levels) if levels else 1
            if max_val == 0:
                max_val = 1
            img = Image.new("RGB", (width, height), "#1a1a2e")
            draw_img = ImageDrawDraw(img) if hasattr(Image, 'ImageDraw') else None
            if draw_img is None:
                from PIL import ImageDraw
                draw = ImageDraw.Draw(img)
            else:
                draw = draw_img
            bar_w = max(1, width // len(levels)) if levels else 1
            mid = height // 2
            for i, lvl in enumerate(levels):
                bar_h = int((lvl / max_val) * (height // 2 - 5))
                x = i * bar_w
                color = f"hsl({170 + i * 30 // max(len(levels), 1)}, 80%, 60%)"
                draw.rectangle([x, mid - bar_h, x + bar_w - 1, mid + bar_h], fill="#00d2ff")
            return img
        except Exception:
            return None


try:
    from PIL import ImageDraw
except ImportError:
    ImageDraw = None


class MediaCutterApp:
    def __init__(self):
        self.root = tb.Window(
            title=f"{APP_TITLE} v{APP_VERSION}",
            themename="darkly",
            size=(1100, 780),
            minsize=(900, 650),
        )
        self.root.place_window_center()
        self.filepath = tk.StringVar()
        self.start_time = tk.StringVar(value="00:00:00.000")
        self.end_time = tk.StringVar(value="00:00:00.000")
        self.duration = tk.DoubleVar(value=0.0)
        self.trim_duration = tk.DoubleVar(value=0.0)
        self.output_format = tk.StringVar(value="Kesme (Aynı Format)")
        self.quality = tk.StringVar(value="Yüksek Kalite")
        self.output_dir = tk.StringVar(value="")
        self.is_processing = False
        self.process = None
        self.media_info = {}
        self.cut_history = []
        self.thumbnail_img = None
        self.waveform_img = None
        self.sliderDragging = False
        self.load_history()
        self.build_ui()
        self.root.bind("<Control-o>", lambda e: self.browse_file())
        self.root.bind("<Control-s>", lambda e: self.start_cut())
        self.root.bind("<Escape>", lambda e: self.cancel_cut())

    def build_ui(self):
        self.build_menu()
        main = tb.Frame(self.root, padding=5)
        main.pack(fill=BOTH, expand=True)
        left = tb.Frame(main, width=420)
        left.pack(side=LEFT, fill=BOTH, padx=(0, 5))
        left.pack_propagate(False)
        right = tb.Frame(main)
        right.pack(side=LEFT, fill=BOTH, expand=True)
        self.build_left_panel(left)
        self.build_right_panel(right)
        self.build_statusbar()

    def build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Dosya Aç  Ctrl+O", command=self.browse_file)
        file_menu.add_separator()
        file_menu.add_command(label="Son Kesme Geçmişi", command=self.show_history)
        file_menu.add_separator()
        file_menu.add_command(label="Çıkış", command=self.root.quit)
        menubar.add_cascade(label="Dosya", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Başlangıca Git", command=lambda: self.seek_to("start"))
        edit_menu.add_command(label="Bitişe Git", command=lambda: self.seek_to("end"))
        edit_menu.add_separator()
        edit_menu.add_command(label="Seçimi Tersine Çevir", command=self.invert_selection)
        menubar.add_cascade(label="Düzenle", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Hakkında", command=lambda: Messagebox.show_info(
            f"{APP_TITLE} v{APP_VERSION}\n\nHızlı Video & Ses Kesme Aracı\n"
            "FFmpeg tabanlı, çoklu format desteği\n\n"
            "Klavye Kısayolları:\n"
            "Ctrl+O: Dosya Aç\n"
            "Ctrl+S: Kesmeyi Başlat\n"
            "Escape: İptal\n"
            "Space: Oynat/Duraklat\n"
            "← →: Saniye ileri/geri\n"
            "I: Başlangıç Noktası\n"
            "O: Bitiş Noktası",
            title="Hakkında"
        ))
        menubar.add_cascade(label="Yardım", menu=help_menu)
        self.root.config(menu=menubar)

    def build_left_panel(self, parent):
        file_card = tb.Labelframe(parent, text=" 📁 Dosya Seçimi ", padding=10, bootstyle="info")
        file_card.pack(fill=X, pady=(0, 8))

        path_frame = tb.Frame(file_card)
        path_frame.pack(fill=X)
        self.file_entry = tb.Entry(path_frame, textvariable=self.filepath, state="readonly", font=("", 9))
        self.file_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        tb.Button(path_frame, text="Gözat", bootstyle="info-outline", command=self.browse_file, width=8).pack(side=RIGHT)
        ToolTip(self.file_entry, text="Desteklenen: MP4, MKV, AVI, MOV, MP3, WAV, FLAC, AAC...")

        self.file_info_label = tb.Label(file_card, text="Dosya seçilmedi", font=("", 9, "italic"), bootstyle="secondary")
        self.file_info_label.pack(anchor=W, pady=(5, 0))

        time_card = tb.Labelframe(parent, text=" ⏱️ Zaman Aralığı ", padding=10, bootstyle="warning")
        time_card.pack(fill=X, pady=(0, 8))

        start_frame = tb.Frame(time_card)
        start_frame.pack(fill=X, pady=(0, 5))
        tb.Label(start_frame, text="Başlangıç:", width=10, anchor=W).pack(side=LEFT)
        start_entry = tb.Entry(start_frame, textvariable=self.start_time, font=("Consolas", 11), width=15)
        start_entry.pack(side=LEFT, padx=(0, 5))
        tb.Button(start_entry, text="", bootstyle="success-link", command=lambda: self.set_current_as("start"), width=3).pack(side=LEFT)

        btn_frame1 = tb.Frame(start_frame)
        btn_frame1.pack(side=RIGHT)
        tb.Button(btn_frame1, text="◀ 0.1s", bootstyle="secondary-outline", command=lambda: self.adjust_time("start", -0.1), width=7).pack(side=LEFT, padx=1)
        tb.Button(btn_frame1, text="▶ 0.1s", bootstyle="secondary-outline", command=lambda: self.adjust_time("start", 0.1), width=7).pack(side=LEFT, padx=1)

        end_frame = tb.Frame(time_card)
        end_frame.pack(fill=X, pady=(0, 5))
        tb.Label(end_frame, text="Bitiş:", width=10, anchor=W).pack(side=LEFT)
        end_entry = tb.Entry(end_frame, textvariable=self.end_time, font=("Consolas", 11), width=15)
        end_entry.pack(side=LEFT, padx=(0, 5))
        tb.Button(end_entry, text="", bootstyle="danger-link", command=lambda: self.set_current_as("end"), width=3).pack(side=LEFT)

        btn_frame2 = tb.Frame(end_frame)
        btn_frame2.pack(side=RIGHT)
        tb.Button(btn_frame2, text="◀ 0.1s", bootstyle="secondary-outline", command=lambda: self.adjust_time("end", -0.1), width=7).pack(side=LEFT, padx=1)
        tb.Button(btn_frame2, text="▶ 0.1s", bootstyle="secondary-outline", command=lambda: self.adjust_time("end", 0.1), width=7).pack(side=LEFT, padx=1)

        dur_frame = tb.Frame(time_card)
        dur_frame.pack(fill=X)
        self.trim_label = tb.Label(dur_frame, text="Seçili Süre: 00:00:00.000", font=("Consolas", 10, "bold"), bootstyle="warning")
        self.trim_label.pack(side=LEFT)
        tb.Button(dur_frame, text="Tamamını Seç", bootstyle="warning-outline", command=self.select_all, width=12).pack(side=RIGHT)

        tb.Button(time_card, text="◀ Başlangıç", bootstyle="info-outline", command=lambda: self.seek_to("start")).pack(side=LEFT, padx=(0, 5), pady=(5, 0))
        tb.Button(time_card, text="Bitiş ▶", bootstyle="info-outline", command=lambda: self.seek_to("end")).pack(side=RIGHT, padx=(5, 0), pady=(5, 0))

        output_card = tb.Labelframe(parent, text=" 📤 Çıktı Ayarları ", padding=10, bootstyle="success")
        output_card.pack(fill=X, pady=(0, 8))

        fmt_frame = tb.Frame(output_card)
        fmt_frame.pack(fill=X, pady=(0, 5))
        tb.Label(fmt_frame, text="Format:", width=10, anchor=W).pack(side=LEFT)
        fmt_combo = tb.Combobox(fmt_frame, textvariable=self.output_format, state="readonly",
                                values=["Kesme (Aynı Format)", "MP4 (H.264)", "MP4 (H.265/HEVC)", "MKV", "WebM",
                                         "MP3 (320kbps)", "MP3 (192kbps)", "WAV", "FLAC", "AAC (256kbps)", "OGG Vorbis"],
                                width=25)
        fmt_combo.pack(side=LEFT, padx=(0, 5))

        qual_frame = tb.Frame(output_card)
        qual_frame.pack(fill=X, pady=(0, 5))
        tb.Label(qual_frame, text="Kalite:", width=10, anchor=W).pack(side=LEFT)
        qual_combo = tb.Combobox(qual_frame, textvariable=self.quality, state="readonly",
                                 values=["En Yüksek Kalite", "Yüksek Kalite", "Orta Kalite", "Düşük Kalite", "Sıkıştırılmış"],
                                 width=25)
        qual_combo.pack(side=LEFT, padx=(0, 5))

        out_frame = tb.Frame(output_card)
        out_frame.pack(fill=X)
        tb.Label(out_frame, text="Klasör:", width=10, anchor=W).pack(side=LEFT)
        self.output_entry = tb.Entry(out_frame, textvariable=self.output_dir, font=("", 9))
        self.output_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        tb.Button(out_frame, text="Seç", bootstyle="success-outline", command=self.browse_output_dir, width=6).pack(side=RIGHT)

        action_frame = tb.Frame(parent)
        action_frame.pack(fill=X, pady=(0, 5))
        self.cut_btn = tb.Button(action_frame, text="✂  KESMEYİ BAŞLAT  ✂", bootstyle="danger",
                                  command=self.start_cut)
        self.cut_btn.pack(fill=X)
        self.cancel_btn = tb.Button(action_frame, text="İPTAL", bootstyle="secondary-outline",
                                     command=self.cancel_cut, state=DISABLED)
        self.cancel_btn.pack(fill=X, pady=(3, 0))

        self.progress_frame = tb.Frame(parent)
        self.progress_frame.pack(fill=X)
        self.progress_bar = tb.Progressbar(self.progress_frame, bootstyle="danger-striped", maximum=100)
        self.progress_label = tb.Label(self.progress_frame, text="", font=("", 9))
        self.progress_label.pack(anchor=W)

        extra_card = tb.Labelframe(parent, text="⚡ Hızlı İşlemler", padding=8, bootstyle="info")
        extra_card.pack(fill=X, pady=(5, 0))
        quick = tb.Frame(extra_card)
        quick.pack(fill=X)
        tb.Button(quick, text="İlk 10 sn", bootstyle="info-outline", command=lambda: self.quick_trim(0, 10), width=10).pack(side=LEFT, padx=2)
        tb.Button(quick, text="İlk 30 sn", bootstyle="info-outline", command=lambda: self.quick_trim(0, 30), width=10).pack(side=LEFT, padx=2)
        tb.Button(quick, text="İlk 1 dk", bootstyle="info-outline", command=lambda: self.quick_trim(0, 60), width=10).pack(side=LEFT, padx=2)
        quick2 = tb.Frame(extra_card)
        quick2.pack(fill=X, pady=(3, 0))
        tb.Button(quick2, text="Son 10 sn", bootstyle="info-outline", command=self.last_10, width=10).pack(side=LEFT, padx=2)
        tb.Button(quick2, text="Son 30 sn", bootstyle="info-outline", command=self.last_30, width=10).pack(side=LEFT, padx=2)
        tb.Button(quick2, text="Son 1 dk", bootstyle="info-outline", command=self.last_60, width=10).pack(side=LEFT, padx=2)
        quick3 = tb.Frame(extra_card)
        quick3.pack(fill=X, pady=(3, 0))
        tb.Button(quick3, text="Orta Yarım", bootstyle="info-outline", command=self.mid_half, width=10).pack(side=LEFT, padx=2)
        tb.Button(quick3, text="Ters Seçim", bootstyle="info-outline", command=self.invert_selection, width=10).pack(side=LEFT, padx=2)

    def build_right_panel(self, parent):
        self.notebook = tb.Notebook(parent, bootstyle="info")
        self.notebook.pack(fill=BOTH, expand=True)

        preview_tab = tb.Frame(self.notebook, padding=5)
        self.notebook.add(preview_tab, text=" 🎬 Ön İzleme ")

        self.preview_label = tb.Label(preview_tab, text="Video seçildiğinde\nön izleme burada görünecek",
                                       anchor=CENTER, bootstyle="inverse-secondary", font=("", 11))
        self.preview_label.pack(fill=BOTH, expand=True)

        self.timeline_frame = tb.Frame(preview_tab)
        self.timeline_frame.pack(fill=X, pady=(5, 0))

        self.timeline_slider = tb.Scale(self.timeline_frame, from_=0, to=100, bootstyle="warning",
                                         command=self.on_slider_change, length=400)
        self.timeline_slider.pack(fill=X)

        time_display = tb.Frame(preview_tab)
        time_display.pack(fill=X, pady=(3, 0))
        self.current_time_label = tb.Label(time_display, text="00:00:00.000", font=("Consolas", 10))
        self.current_time_label.pack(side=LEFT)
        self.total_time_label = tb.Label(time_display, text="/ 00:00:00.000", font=("Consolas", 10), bootstyle="secondary")
        self.total_time_label.pack(side=LEFT)

        ctrl_frame = tb.Frame(preview_tab)
        ctrl_frame.pack(fill=X, pady=(5, 0))
        tb.Button(ctrl_frame, text="◀◀", bootstyle="secondary-outline", command=lambda: self.adjust_current(-5), width=5).pack(side=LEFT, padx=2)
        tb.Button(ctrl_frame, text="◀", bootstyle="secondary-outline", command=lambda: self.adjust_current(-1), width=4).pack(side=LEFT, padx=2)
        self.play_btn = tb.Button(ctrl_frame, text="▶ Oynat", bootstyle="success", command=self.toggle_preview, width=10)
        self.play_btn.pack(side=LEFT, padx=5)
        tb.Button(ctrl_frame, text="▶", bootstyle="secondary-outline", command=lambda: self.adjust_current(1), width=4).pack(side=LEFT, padx=2)
        tb.Button(ctrl_frame, text="▶▶", bootstyle="secondary-outline", command=lambda: self.adjust_current(5), width=5).pack(side=LEFT, padx=2)

        set_frame = tb.Frame(preview_tab)
        set_frame.pack(fill=X, pady=(5, 0))
        tb.Button(set_frame, text="I → Başlangıç", bootstyle="success-outline", command=lambda: self.set_current_as("start"), width=15).pack(side=LEFT, padx=3)
        tb.Button(set_frame, text="O → Bitiş", bootstyle="danger-outline", command=lambda: self.set_current_as("end"), width=15).pack(side=LEFT, padx=3)
        tb.Button(set_frame, text="Oynat Seçim", bootstyle="warning-outline", command=self.play_selection, width=15).pack(side=LEFT, padx=3)

        info_tab = tb.Frame(self.notebook, padding=10)
        self.notebook.add(info_tab, text=" 📊 Medya Bilgisi ")
        self.info_text = ScrolledText(info_tab, height=15, autohide=True)
        self.info_text.pack(fill=BOTH, expand=True)

        history_tab = tb.Frame(self.notebook, padding=10)
        self.notebook.add(history_tab, text=" 📜 Geçmiş ")
        self.history_tree = tb.Treeview(history_tab, columns=("file", "start", "end", "format", "date"),
                                         show="headings", height=12, bootstyle="info")
        self.history_tree.heading("file", text="Dosya")
        self.history_tree.heading("start", text="Başlangıç")
        self.history_tree.heading("end", text="Bitiş")
        self.history_tree.heading("format", text="Format")
        self.history_tree.heading("date", text="Tarih")
        self.history_tree.column("file", width=200)
        self.history_tree.column("start", width=100)
        self.history_tree.column("end", width=100)
        self.history_tree.column("format", width=150)
        self.history_tree.column("date", width=120)
        self.history_tree.pack(fill=BOTH, expand=True)
        self.refresh_history_tree()

    def build_statusbar(self):
        self.statusbar = tb.Frame(self.root, padding=(10, 3))
        self.statusbar.pack(side=BOTTOM, fill=X)
        self.status_label = tb.Label(self.statusbar, text="Hazır", font=("", 9))
        self.status_label.pack(side=LEFT)
        self.version_label = tb.Label(self.statusbar, text=f"v{APP_VERSION} | FFmpeg", font=("", 8), bootstyle="secondary")
        self.version_label.pack(side=RIGHT)

    def browse_file(self):
        filetypes = [
            ("Tüm Medya Dosyaları", " ".join(f"*{e}" for e in SUPPORTED_ALL)),
            ("Video Dosyaları", " ".join(f"*{e}" for e in SUPPORTED_VIDEO)),
            ("Ses Dosyaları", " ".join(f"*{e}" for e in SUPPORTED_AUDIO)),
            ("Tüm Dosyalar", "*.*"),
        ]
        path = filedialog.askopenfilename(filetypes=filetypes, title="Medya Dosyası Seç")
        if path:
            self.load_file(path)

    def load_file(self, filepath):
        if not os.path.exists(filepath):
            return
        self.filepath.set(filepath)
        dur = get_media_duration(filepath)
        self.duration.set(dur)
        self.start_time.set("00:00:00.000")
        self.end_time.set(format_time(dur))
        self.trim_duration.set(dur)

        ext = Path(filepath).suffix.lower()
        info = get_media_info(filepath)
        self.media_info = info

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        is_vid = is_video_file(filepath)
        type_str = "Video" if is_vid else "Ses"

        streams_info = ""
        if "streams" in info:
            for s in info["streams"]:
                codec = s.get("codec_long_name", s.get("codec_type", "?"))
                if s.get("codec_type") == "video":
                    w, h = s.get("width", "?"), s.get("height", "?")
                    fps = s.get("r_frame_rate", "?")
                    streams_info += f"  Video: {codec} | {w}x{h} | {fps} fps\n"
                elif s.get("codec_type") == "audio":
                    sr = s.get("sample_rate", "?")
                    ch = s.get("channels", "?")
                    streams_info += f"  Ses: {codec} | {sr} Hz | {ch} kanal\n"

        info_str = (
            f"📁 {os.path.basename(filepath)}\n"
            f"📌 {type_str} | {ext.upper()} | {size_mb:.1f} MB\n"
            f"⏱️ Süre: {format_time(dur)}\n"
            f"📊 Boyut: {size_mb:.1f} MB\n"
            f"\n{streams_info}"
        )
        self.file_info_label.config(text=f"{type_str} | {ext.upper()} | {size_mb:.1f} MB | {format_time(dur)}")

        self.info_text.text.config(state=NORMAL)
        self.info_text.text.delete("1.0", END)
        self.info_text.text.insert("1.0", info_str)
        self.info_text.text.config(state=DISABLED)

        self.timeline_slider.configure(to=max(1, int(dur * 10)))
        self.timeline_slider.set(0)
        self.current_time_label.config(text="00:00:00.000")
        self.total_time_label.config(text=f"/ {format_time(dur)}")

        self.update_trim_label()
        self.set_status(f"Yüklendi: {os.path.basename(filepath)} ({format_time(dur)})")

        threading.Thread(target=self._load_thumbnail, args=(filepath,), daemon=True).start()

    def _load_thumbnail(self, filepath):
        if is_video_file(filepath):
            img = ThumbnailGenerator.generate(filepath, timestamp=min(1.0, self.duration.get() / 4))
            if img:
                self.thumbnail_img = ImageTk.PhotoImage(img)
                self.root.after(0, lambda: self.preview_label.config(image=self.thumbnail_img, text=""))

    def on_slider_change(self, value):
        if self.duration.get() <= 0:
            return
        pos = float(value) / 10.0
        self.current_time_label.config(text=format_time(pos))

    def adjust_current(self, delta):
        if self.duration.get() <= 0:
            return
        current = self.timeline_slider.get() / 10.0
        new_pos = max(0, min(self.duration.get(), current + delta))
        self.timeline_slider.set(new_pos * 10)
        self.current_time_label.config(text=format_time(new_pos))

    def set_current_as(self, which):
        current = self.timeline_slider.get() / 10.0
        if which == "start":
            self.start_time.set(format_time(current))
        else:
            self.end_time.set(format_time(current))
        self.update_trim_label()

    def adjust_time(self, which, delta):
        try:
            current = parse_time(self.start_time.get() if which == "start" else self.end_time.get())
        except ValueError:
            return
        new_val = max(0, min(self.duration.get(), current + delta))
        if which == "start":
            self.start_time.set(format_time(new_val))
        else:
            self.end_time.set(format_time(new_val))
        self.update_trim_label()

    def seek_to(self, which):
        try:
            t = parse_time(self.start_time.get() if which == "start" else self.end_time.get())
            self.timeline_slider.set(t * 10)
            self.current_time_label.config(text=format_time(t))
        except ValueError:
            pass

    def select_all(self):
        self.start_time.set("00:00:00.000")
        self.end_time.set(format_time(self.duration.get()))
        self.update_trim_label()

    def invert_selection(self):
        try:
            s = parse_time(self.start_time.get())
            e = parse_time(self.end_time.get())
            self.start_time.set(format_time(e))
            self.end_time.set(format_time(s))
            self.update_trim_label()
        except ValueError:
            pass

    def quick_trim(self, start_sec, end_sec):
        self.start_time.set(format_time(start_sec))
        self.end_time.set(format_time(min(end_sec, self.duration.get())))
        self.update_trim_label()

    def last_10(self):
        d = self.duration.get()
        self.quick_trim(max(0, d - 10), d)

    def last_30(self):
        d = self.duration.get()
        self.quick_trim(max(0, d - 30), d)

    def last_60(self):
        d = self.duration.get()
        self.quick_trim(max(0, d - 60), d)

    def mid_half(self):
        d = self.duration.get()
        quarter = d / 4
        self.start_time.set(format_time(quarter))
        self.end_time.set(format_time(d - quarter))
        self.update_trim_label()

    def update_trim_label(self):
        try:
            s = parse_time(self.start_time.get())
            e = parse_time(self.end_time.get())
            diff = max(0, e - s)
            self.trim_duration.set(diff)
            self.trim_label.config(text=f"Seçili Süre: {format_time(diff)}")
        except ValueError:
            pass

    def browse_output_dir(self):
        d = filedialog.askdirectory(title="Çıktı Klasörü Seç")
        if d:
            self.output_dir.set(d)

    def get_ffmpeg_args(self, input_file, output_file, start, end):
        args = ["ffmpeg", "-y"]
        args += ["-ss", str(start)]
        args += ["-i", input_file]
        args += ["-to", str(end - start)]

        fmt = self.output_format.get()
        qual = self.quality.get()

        if "Kesme (Aynı Format)" in fmt:
            args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
        elif "MP4 (H.264)" in fmt:
            if qual == "En Yüksek Kalite":
                args += ["-c:v", "libx264", "-crf", "14", "-preset", "slow", "-c:a", "aac", "-b:a", "320k"]
            elif qual == "Yüksek Kalite":
                args += ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "256k"]
            elif qual == "Orta Kalite":
                args += ["-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"]
            elif qual == "Düşük Kalite":
                args += ["-c:v", "libx264", "-crf", "32", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k"]
            else:
                args += ["-c:v", "libx264", "-crf", "35", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "96k"]
            output_file = output_file.rsplit(".", 1)[0] + ".mp4"
        elif "MP4 (H.265" in fmt:
            if qual == "En Yüksek Kalite":
                args += ["-c:v", "libx265", "-crf", "16", "-preset", "slow", "-c:a", "aac", "-b:a", "320k"]
            elif qual == "Yüksek Kalite":
                args += ["-c:v", "libx265", "-crf", "22", "-preset", "medium", "-c:a", "aac", "-b:a", "256k"]
            else:
                args += ["-c:v", "libx265", "-crf", "28", "-preset", "fast", "-c:a", "aac", "-b:a", "192k"]
            output_file = output_file.rsplit(".", 1)[0] + ".mp4"
        elif "MKV" in fmt:
            args += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
            output_file = output_file.rsplit(".", 1)[0] + ".mkv"
        elif "WebM" in fmt:
            args += ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"]
            output_file = output_file.rsplit(".", 1)[0] + ".webm"
        elif "MP3" in fmt:
            br = "320" if "320" in fmt else "192"
            args += ["-vn", "-c:a", "libmp3lame", "-b:a", f"{br}k"]
            output_file = output_file.rsplit(".", 1)[0] + ".mp3"
        elif "WAV" in fmt:
            args += ["-vn", "-c:a", "pcm_s16le"]
            output_file = output_file.rsplit(".", 1)[0] + ".wav"
        elif "FLAC" in fmt:
            args += ["-vn", "-c:a", "flac"]
            output_file = output_file.rsplit(".", 1)[0] + ".flac"
        elif "AAC" in fmt:
            args += ["-vn", "-c:a", "aac", "-b:a", "256k"]
            output_file = output_file.rsplit(".", 1)[0] + ".m4a"
        elif "OGG" in fmt:
            args += ["-vn", "-c:a", "libvorbis", "-q:a", "6"]
            output_file = output_file.rsplit(".", 1)[0] + ".ogg"

        args += ["-map_metadata", "-1"]
        args.append(output_file)
        return args, output_file

    def start_cut(self):
        if not self.filepath.get():
            Messagebox.show_warning("Lütfen bir dosya seçin!", title="Uyarı")
            return
        if self.is_processing:
            return
        try:
            start = parse_time(self.start_time.get())
            end = parse_time(self.end_time.get())
        except ValueError:
            Messagebox.show_error("Geçersiz zaman formatı!", title="Hata")
            return
        if start >= end:
            Messagebox.show_error("Başlangıç zamanı, bitiş zamanından küçük olmalı!", title="Hata")
            return

        input_file = self.filepath.get()
        out_dir = self.output_dir.get() if self.output_dir.get() else os.path.dirname(input_file)
        base_name = Path(input_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_cut_{timestamp}"

        fmt = self.output_format.get()
        ext_map = {
            "MP3": ".mp3", "WAV": ".wav", "FLAC": ".flac",
            "AAC": ".m4a", "OGG": ".ogg", "MKV": ".mkv",
            "WebM": ".webm"
        }
        ext = ".mp4"
        for key, val in ext_map.items():
            if key in fmt:
                ext = val
                break
        output_file = os.path.join(out_dir, f"{output_name}{ext}")
        args, output_file = self.get_ffmpeg_args(input_file, output_file, start, end)

        self.is_processing = True
        self.cut_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.progress_bar["value"] = 0
        self.progress_frame.pack(fill=X)

        threading.Thread(target=self._run_ffmpeg, args=(args, output_file, start, end), daemon=True).start()

    def _run_ffmpeg(self, args, output_file, start, end):
        try:
            self.root.after(0, lambda: self.set_status("Kesme işlemi başlıyor..."))
            self.process = subprocess.Popen(
                args, stderr=subprocess.PIPE, universal_newlines=True
            )
            dur = end - start
            for line in self.process.stderr:
                if "time=" in line:
                    match = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", line)
                    if match:
                        h, m, s, cs = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                        current = h * 3600 + m * 60 + s + cs / 100.0
                        pct = min(100, (current / dur) * 100) if dur > 0 else 0
                        self.root.after(0, lambda p=pct, c=current: self._update_progress(p, c))
                if "fps=" in line:
                    self.root.after(0, lambda l=line: self.set_status(f"İşleniyor... {l.strip()[:80]}"))

            self.process.wait()
            if self.process.returncode == 0:
                self.root.after(0, lambda: self._cut_complete(output_file))
            else:
                self.root.after(0, lambda: self._cut_failed("FFmpeg hatası oluştu"))
        except Exception as e:
            self.root.after(0, lambda: self._cut_failed(str(e)))

    def _update_progress(self, pct, current):
        self.progress_bar["value"] = pct
        self.progress_label.config(text=f"%{pct:.1f} — {format_time(current)}")

    def _cut_complete(self, output_file):
        self.is_processing = False
        self.process = None
        self.cut_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.progress_bar["value"] = 100
        self.progress_label.config(text="Tamamlandı!")
        size = os.path.getsize(output_file) / (1024 * 1024)
        self.set_status(f"Tamamlandı! → {os.path.basename(output_file)} ({size:.1f} MB)")

        self.add_history(output_file)
        self.save_history()

        result = Messagebox.yesnocancel(
            f"Kesme tamamlandı!\n\n📁 {os.path.basename(output_file)}\n📊 {size:.1f} MB\n\n"
            "Dosyayı açmak ister misiniz?",
            title="Tamamlandı"
        )
        if result == "Yes":
            try:
                subprocess.Popen(["xdg-open", output_file])
            except Exception:
                pass
        elif result == "Cancel":
            folder = os.path.dirname(output_file)
            try:
                subprocess.Popen(["xdg-open", folder])
            except Exception:
                pass

    def _cut_failed(self, error):
        self.is_processing = False
        self.process = None
        self.cut_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Hata!")
        self.set_status(f"Hata: {error}")
        Messagebox.show_error(f"Kesme sırasında hata:\n{error}", title="Hata")

    def cancel_cut(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.is_processing = False
        self.cut_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="İptal edildi")
        self.set_status("İptal edildi")

    def toggle_preview(self):
        if not self.filepath.get():
            return
        if hasattr(self, '_preview_proc') and self._preview_proc and self._preview_proc.poll() is None:
            self._preview_proc.terminate()
            self._preview_proc = None
            self.play_btn.config(text="▶ Oynat", bootstyle="success")
            return
        try:
            ss = parse_time(self.start_time.get())
            duration = self.trim_duration.get()
            args = ["ffplay", "-nodisp", "-autoexit", "-ss", str(ss), "-t", str(duration), self.filepath.get()]
            self._preview_proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.play_btn.config(text="⏹ Durdur", bootstyle="danger")
        except Exception:
            pass

    def play_selection(self):
        self.toggle_preview()

    def add_history(self, output_file):
        entry = {
            "file": os.path.basename(output_file),
            "path": output_file,
            "start": self.start_time.get(),
            "end": self.end_time.get(),
            "format": self.output_format.get(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.cut_history.insert(0, entry)
        if len(self.cut_history) > 50:
            self.cut_history = self.cut_history[:50]
        self.refresh_history_tree()

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.cut_history, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r") as f:
                    self.cut_history = json.load(f)
        except Exception:
            self.cut_history = []

    def refresh_history_tree(self):
        self.history_tree.delete(*self.history_tree.get_children())
        for entry in self.cut_history:
            self.history_tree.insert("", END, values=(
                entry.get("file", ""),
                entry.get("start", ""),
                entry.get("end", ""),
                entry.get("format", ""),
                entry.get("date", ""),
            ))

    def show_history(self):
        self.notebook.select(2)

    def set_status(self, text):
        self.status_label.config(text=text)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = MediaCutterApp()
    app.run()
