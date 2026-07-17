#!/usr/bin/env bash
# ============================================================
#  CutIsEndless - Install Script
#  Automated setup for CutIsEndless Video & Audio Cutter
#  https://github.com/ByteChesterX/CutIsEndless
# ============================================================

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/ByteChesterX/CutIsEndless.git"
INSTALL_DIR="/opt/CutIsEndless"
APP_NAME="CutIsEndless"

# sudo ile çalışırken gerçek kullanıcının HOME'unu bul
if [[ -n "${SUDO_USER:-}" ]]; then
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_HOME="$HOME"
fi
DESKTOP_FILE="$REAL_HOME/.local/share/applications/com.bytechester.cutisendless.desktop"
ICON_DIR="$REAL_HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="$ICON_DIR/com.bytechester.cutisendless.png"

# ── Helpers ─────────────────────────────────────────────────
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; }
divider() { echo -e "${CYAN}────────────────────────────────────────────${NC}"; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Bu script root yetkisiyle çalışmalıdır."
        echo -e "  Kullanım: ${BOLD}sudo bash install.sh${NC}"
        exit 1
    fi
}

# ── Distro Detection ───────────────────────────────────────
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-}"
    elif command -v lsb_release &>/dev/null; then
        DISTRO_ID=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
        DISTRO_LIKE=""
    else
        DISTRO_ID="unknown"
        DISTRO_LIKE=""
    fi

    if [[ "$DISTRO_ID" == "cachyos" || "$DISTRO_ID" == "arch" || "$DISTRO_LIKE" == *"arch"* ]]; then
        PKG_MANAGER="pacman"
    elif [[ "$DISTRO_ID" == "ubuntu" || "$DISTRO_ID" == "debian" || "$DISTRO_ID" == "linuxmint" || "$DISTRO_LIKE" == *"debian"* ]]; then
        PKG_MANAGER="apt"
    elif [[ "$DISTRO_ID" == "fedora" ]]; then
        PKG_MANAGER="dnf"
    elif [[ "$DISTRO_ID" == "opensuse"* || "$DISTRO_ID" == "suse"* ]]; then
        PKG_MANAGER="zypper"
    elif [[ "$DISTRO_ID" == "arch"* || "$DISTRO_LIKE" == *"arch"* ]]; then
        PKG_MANAGER="pacman"
    else
        PKG_MANAGER="unknown"
    fi

    info "Tespit edilen distro: ${BOLD}$DISTRO_ID${NC} (paketcı: $PKG_MANAGER)"
}

# ── Package Installation ───────────────────────────────────
install_system_deps() {
    divider
    info "Sistem bağımlılıkları kuruluyor..."
    divider

    case "$PKG_MANAGER" in
        pacman)
            pacman -S --needed --noconfirm ffmpeg python tk
            ;;
        apt)
            apt-get update -qq
            apt-get install -y -qq ffmpeg python3 python3-tk
            ;;
        dnf)
            dnf install -y ffmpeg python3 python3-tkinter
            ;;
        zypper)
            zypper install -y ffmpeg python3 python3-tk
            ;;
        *)
            warn "Bilinmeyen distro. Lütfen şunları manuel kurun:"
            warn "  - ffmpeg"
            warn "  - python3"
            warn "  - tk (Tcl/Tk)"
            echo ""
            read -rp "Devam etmek için ENTER'a basın..." _
            ;;
    esac
    success "Sistem bağımlılıkları kuruldu."
}

# ── Python Dependencies ────────────────────────────────────
install_python_deps() {
    divider
    info "Python bağımlılıkları kuruluyor..."
    divider

    local PIP="pip3"
    local PIP_FLAGS=""
    if [[ $EUID -eq 0 ]]; then
        PIP_FLAGS="--break-system-packages"
    fi

    $PIP install --upgrade $PIP_FLAGS ttkbootstrap Pillow 2>/dev/null || {
        warn "pip install başarısız, --user ile deneniyor..."
        pip3 install --user ttkbootstrap Pillow || {
            error "Python bağımlılıkları kurulamadı!"
            exit 1
        }
    }
    success "Python bağımlılıkları kuruldu (ttkbootstrap, Pillow)."
}

# ── Clone / Update Repo ────────────────────────────────────
clone_repo() {
    divider
    info "Proje klonlanıyor..."
    divider

    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Dizin zaten mevcut, güncelleniyor: $INSTALL_DIR"
        cd "$INSTALL_DIR"
        git pull --ff-only 2>/dev/null || warn "Git pull başarısız, mevcut sürüm kullanılıyor."
    else
        if [[ -d "$INSTALL_DIR" ]]; then
            warn "Dizin mevcut ama git repo değil. Yedekleniyor..."
            mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
        fi
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi

    chmod +x "$INSTALL_DIR/video_cutter.py"
    success "Proje hazır: $INSTALL_DIR"
}

# ── Icon ────────────────────────────────────────────────────
create_icon() {
    divider
    info "İkon oluşturuluyor..."
    divider

    mkdir -p "$ICON_DIR"

    if [[ -f "$INSTALL_DIR/icon.png" ]]; then
        cp "$INSTALL_DIR/icon.png" "$ICON_FILE"
    else
        # Generate a simple PNG icon using Python + Pillow
        python3 -c "
from PIL import Image, ImageDraw, ImageFont
import os

size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle
draw.rounded_rectangle([8, 8, 248, 248], radius=40, fill=(30, 30, 60, 255))

# Scissors shape
cx, cy = size // 2, size // 2
# Blade 1
draw.ellipse([60, 80, 120, 140], outline=(0, 210, 255), width=6)
# Blade 2
draw.ellipse([136, 80, 196, 140], outline=(0, 210, 255), width=6)
# Handles
draw.line([(90, 140), (90, 200)], fill=(0, 210, 255), width=6)
draw.line([(166, 140), (166, 200)], fill=(0, 210, 255), width=6)
# Cross point
draw.line([(90, 140), (166, 140)], fill=(255, 75, 75), width=4)
# Cut line
draw.line([(60, 155), (196, 155)], fill=(255, 75, 75), width=3)

img.save('$ICON_FILE')
" 2>/dev/null || {
            warn "İkon oluşturulamadı, varsayılan kullanılıyor."
            return
        }
    fi
    success "İkon kuruldu: $ICON_FILE"
}

# ── Desktop Entry ───────────────────────────────────────────
create_desktop_entry() {
    divider
    info ".desktop dosyası oluşturuluyor..."
    divider

    mkdir -p "$(dirname "$DESKTOP_FILE")"

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Hızlı Video & Ses Kesme Aracı
Exec=/usr/bin/env python3 $INSTALL_DIR/video_cutter.py
Icon=com.bytechester.cutisendless
Terminal=false
Type=Application
Categories=AudioVideo;Video;Audio;Utility;
MimeType=video/mp4;video/x-matroska;video/avi;video/quicktime;video/webm;audio/mpeg;audio/x-wav;audio/flac;audio/x-flac;audio/aac;audio/ogg;
Keywords=video;audio;cut;trim;editor;ffmpeg;kesme;düzenleme;
StartupWMClass=mediacutter
EOF

    chmod +x "$DESKTOP_FILE"

    # Update desktop database
    update-desktop-database "$(dirname "$DESKTOP_FILE")" 2>/dev/null || true

    success ".desktop dosyası oluşturuldu: $DESKTOP_FILE"
}

# ── Uninstall helper ───────────────────────────────────────
create_uninstall() {
    cat > "$INSTALL_DIR/uninstall.sh" <<'UNINSTALLEOF'
#!/usr/bin/env bash
# CutIsEndless Uninstaller
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}CutIsEndless kaldırılıyor...${NC}"

# sudo ile çalışırken gerçek kullanıcının HOME'unu bul
if [[ -n "${SUDO_USER:-}" ]]; then
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_HOME="$HOME"
fi

# Remove desktop entry
rm -f "$REAL_HOME/.local/share/applications/com.bytechester.cutisendless.desktop"

# Remove icon
rm -f "$REAL_HOME/.local/share/icons/hicolor/256x256/apps/com.bytechester.cutisendless.png"

# Remove install directory
rm -rf /opt/CutIsEndless

# Remove history
rm -f "$REAL_HOME/.mediacutter_history.json"

# Update desktop database
update-desktop-database "$REAL_HOME/.local/share/applications/" 2>/dev/null || true

echo -e "${GREEN}CutIsEndless başarıyla kaldırıldı.${NC}"
UNINSTALLEOF
    chmod +x "$INSTALL_DIR/uninstall.sh"
}

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
main() {
    echo ""
    echo -e "${BOLD}${CYAN}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║       CutIsEndless - Kurulum           ║"
    echo "  ║   Video & Audio Cutter Installer       ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"

    check_root
    detect_distro
    install_system_deps
    install_python_deps
    clone_repo
    create_icon
    create_desktop_entry
    create_uninstall

    divider
    echo ""
    echo -e "${GREEN}${BOLD}  ✅ Kurulum tamamlandı!${NC}"
    echo ""
    echo -e "  Uygulamayı çalıştırmak için:"
    echo -e "    ${BOLD}1)${NC} Menüden \"${APP_NAME}\" arayın"
    echo -e "    ${BOLD}2)${NC} veya terminalden: ${CYAN}python3 $INSTALL_DIR/video_cutter.py${NC}"
    echo ""
    echo -e "  Kaldırmak için: ${CYAN}sudo bash $INSTALL_DIR/uninstall.sh${NC}"
    echo ""
    divider
}

main "$@"
