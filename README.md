# CutIsEndless

Hızlı video ve ses kesme aracı. FFmpeg tabanlı, modern arayüzlü.

## Kurulum

curl -fsSL https://raw.githubusercontent.com/ByteChesterX/CutIsEndless/main/install.sh | sudo bash

Veya manuel:

  git clone https://github.com/ByteChesterX/CutIsEndless.git /opt/CutIsEndless
    pip install ttkbootstrap Pillow
    python3 /opt/CutIsEndless/video_cutter.py

## Kaldırma

  sudo bash /opt/CutIsEndless/uninstall.sh

## Özellikler

- **Format desteği:** MP4, MKV, AVI, MOV, WebM, MP3, WAV, FLAC, AAC, OGG
- **Çıktı seçenekleri:** H.264, H.265, VP9, copy (aynı format), yeniden kodlama
- **5 kalite seviyesi**
- **Hızlı seçim:** İlk/son 10sn, 30sn, 1dk, orta yarım
- **Video ön izleme** ve timeline slider
- **İşlem geçmişi**
- **Klavye kısayolları:** Ctrl+O aç, Ctrl+S kes, I/O başlangıç/bitiş noktası

## Gereksinimler

- Python 3.8+
- FFmpeg, FFprobe
- ttkbootstrap, Pillow

## Lisans
GPL-3.0
