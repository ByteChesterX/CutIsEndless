#!/usr/bin/env bash
# CutIsEndless - Uninstaller
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${RED}${BOLD}CutIsEndless kaldırılıyor...${NC}"
echo ""

# sudo ile çalışırken gerçek kullanıcının HOME'unu bul
if [[ -n "${SUDO_USER:-}" ]]; then
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_HOME="$HOME"
fi

# Remove desktop entry
rm -f "$REAL_HOME/.local/share/applications/com.bytechester.cutisendless.desktop"
echo -e "  ${GREEN}✓${NC} .desktop dosyası kaldırıldı"

# Remove icon
rm -f "$REAL_HOME/.local/share/icons/hicolor/256x256/apps/com.bytechester.cutisendless.png"
echo -e "  ${GREEN}✓${NC} İkon kaldırıldı"

# Remove install directory
rm -rf /opt/CutIsEndless
echo -e "  ${GREEN}✓${NC} /opt/CutIsEndless kaldırıldı"

# Remove history
rm -f "$REAL_HOME/.mediacutter_history.json"
echo -e "  ${GREEN}✓${NC} Geçmiş dosyası kaldırıldı"

# Update desktop database
update-desktop-database "$REAL_HOME/.local/share/applications/" 2>/dev/null || true

echo ""
echo -e "${GREEN}${BOLD}✅ CutIsEndless başarıyla kaldırıldı.${NC}"
