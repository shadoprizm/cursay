#!/usr/bin/env bash
set -euo pipefail

install_root=${CURSAY_INSTALL_ROOT:-"$HOME/.local/opt/cursay"}
data_root=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_root=${XDG_CONFIG_HOME:-"$HOME/.config"}
systemd_dir="$config_root/systemd/user"
desktop_dir="$data_root/applications"

systemctl --user disable --now cursay.service cursay-input.service cursay-stt.service 2>/dev/null || true
rm -f -- \
    "$systemd_dir/cursay.service" \
    "$systemd_dir/cursay-input.service" \
    "$systemd_dir/cursay-stt.service" \
    "$desktop_dir/io.github.shadoprizm.Cursay.desktop"
systemctl --user daemon-reload
rm -rf -- "$install_root" "${install_root}.previous"

printf '%s\n' \
    'Cursay was uninstalled.' \
    "Your settings and dictation history remain in $data_root/cursay." \
    "Remove that directory manually only if you also want to erase your data."
