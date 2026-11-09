#!/bin/bash
# Compile the narrowly-scoped IBKR paper-disclaimer AppleScript as a background
# app with a stable macOS Accessibility/TCC identity.
#
# This script cannot grant Accessibility permission (macOS deliberately
# requires a human action). After installation:
#   System Settings > Privacy & Security > Accessibility
#   add/enable ~/Applications/IBGatewayPaperDisclaimerHandler.app
set -euo pipefail

IBKR_UTIL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$IBKR_UTIL_DIR/../.." && pwd)"
SOURCE="$REPO/utils/ibkr/paper_disclaimer.applescript"
APP="$REPO/.runtime/ibkr/IBGatewayPaperDisclaimerHandler.app"

mkdir -p "$REPO/.runtime/ibkr"
rm -rf "$APP"
/usr/bin/osacompile -o "$APP" "$SOURCE"

# Keep the helper out of the Dock. Ignore "already exists" differences across
# macOS/osacompile versions and enforce the final value.
/usr/libexec/PlistBuddy -c "Delete :LSUIElement" "$APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist"

echo "Installed: $APP"
echo
echo "One manual macOS security step remains:"
echo "  System Settings > Privacy & Security > Accessibility"
echo "  Add and enable IBGatewayPaperDisclaimerHandler.app"
echo
echo "After permission is granted, test with:"
echo "  open -gja \"$APP\""
echo
echo "The runtime supervisor's disclaimer warm-up invokes this app only as a"
echo "fallback; IBC remains the primary dialog handler."
