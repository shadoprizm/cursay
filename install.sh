#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install_root=${CURSAY_INSTALL_ROOT:-"$HOME/.local/opt/cursay"}
data_root=${XDG_DATA_HOME:-"$HOME/.local/share"}
config_root=${XDG_CONFIG_HOME:-"$HOME/.config"}
runtime_root="$data_root/cursay/runtime"
systemd_dir="$config_root/systemd/user"
desktop_dir="$data_root/applications"
backup_dir="$data_root/cursay/migration-backup"
start_services=true
install_backend=true
download_model=true

for argument in "$@"; do
    case "$argument" in
        --no-start) start_services=false ;;
        --skip-backend) install_backend=false; download_model=false ;;
        --skip-model) download_model=false ;;
        -h|--help)
            printf '%s\n' \
                'Usage: ./install.sh [--no-start] [--skip-backend] [--skip-model]' \
                '' \
                '  --no-start       Install without starting the user services.' \
                '  --skip-backend   Do not create the local Whisper runtime.' \
                '  --skip-model     Install the runtime but download the model on first use.'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$argument" >&2; exit 2 ;;
    esac
done

for command in apt dpkg-deb python3 systemctl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Missing required command: %s\n' "$command" >&2
        exit 1
    fi
done

if ! /usr/bin/python3 -c 'import dbus, gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' 2>/dev/null; then
    printf '%s\n' \
        'Cursay needs the Ubuntu GTK runtime. Install it, then run this installer again:' \
        '  sudo apt install python3 python3-gi python3-dbus gir1.2-gtk-4.0 gir1.2-adw-1 pipewire-bin python3-venv'
    exit 1
fi

stage_root=$(mktemp -d)
cleanup() {
    rm -rf -- "$stage_root"
}
trap cleanup EXIT
stage_app="$stage_root/cursay"
mkdir -p "$stage_app"
cp -a "$source_dir/cursay" "$stage_app/"
cp -a "$source_dir/assets" "$stage_app/"
cp -a "$source_dir/backend" "$stage_app/"
cp -a "$source_dir/bin" "$stage_app/"
cp -a "$source_dir/pyproject.toml" "$stage_app/"
chmod 0755 "$stage_app/bin/cursay"

install_vendor_package() {
    package=$1
    destination=$2
    bundled_binary=$3
    if [ -x "$source_dir/$bundled_binary" ]; then
        cp -a "$source_dir/vendor/$destination" "$stage_app/vendor/"
        return
    fi

    package_dir="$stage_root/packages/$package"
    mkdir -p "$package_dir" "$stage_app/vendor/$destination"
    (
        cd "$package_dir"
        apt download "$package" >/dev/null
    )
    deb_file=$(find "$package_dir" -maxdepth 1 -type f -name '*.deb' -print -quit)
    if [ -z "$deb_file" ]; then
        printf 'Could not download Ubuntu package: %s\n' "$package" >&2
        exit 1
    fi
    dpkg-deb -x "$deb_file" "$stage_app/vendor/$destination"
}

mkdir -p "$stage_app/vendor"
install_vendor_package wl-clipboard wl-clipboard vendor/wl-clipboard/usr/bin/wl-copy
install_vendor_package ydotool ydotool vendor/ydotool/usr/bin/ydotoold

if [ "$install_backend" = true ]; then
    if [ ! -x "$runtime_root/venv/bin/python" ]; then
        mkdir -p "$runtime_root"
        if ! /usr/bin/python3 -m venv "$runtime_root/venv"; then
            printf '%s\n' 'Could not create the local runtime. Install python3-venv and retry.' >&2
            exit 1
        fi
    fi
    "$runtime_root/venv/bin/python" -m pip install \
        --disable-pip-version-check \
        --requirement "$stage_app/backend/requirements.txt"
    if [ "$download_model" = true ]; then
        CURSAY_MODEL_DIR="$data_root/cursay/models" \
            "$runtime_root/venv/bin/python" "$stage_app/backend/download_model.py"
    fi
fi

systemctl --user stop cursay.service cursay-input.service cursay-stt.service 2>/dev/null || true
if [ -d "$install_root" ]; then
    previous_root="${install_root}.previous"
    rm -rf -- "$previous_root"
    mv -- "$install_root" "$previous_root"
fi
mkdir -p "$(dirname -- "$install_root")"
mv -- "$stage_app" "$install_root"

mkdir -p "$systemd_dir" "$desktop_dir" "$backup_dir"
install -m 0644 "$source_dir/packaging/systemd/cursay.service" "$systemd_dir/cursay.service"
install -m 0644 "$source_dir/packaging/systemd/cursay-input.service" "$systemd_dir/cursay-input.service"
if [ "$install_backend" = true ]; then
    install -m 0644 "$source_dir/packaging/systemd/cursay-stt.service" "$systemd_dir/cursay-stt.service"
fi
sed "s|@INSTALL_ROOT@|$install_root|g" \
    "$source_dir/packaging/desktop/io.github.shadoprizm.Cursay.desktop.in" \
    > "$desktop_dir/io.github.shadoprizm.Cursay.desktop"
chmod 0644 "$desktop_dir/io.github.shadoprizm.Cursay.desktop"

# Retire the pre-release Local Flow integration while keeping a recoverable copy.
systemctl --user disable --now local-flow.service local-flow-input.service 2>/dev/null || true
for legacy_file in \
    "$systemd_dir/local-flow.service" \
    "$systemd_dir/local-flow-input.service" \
    "$desktop_dir/io.astradevs.LocalFlow.desktop"; do
    if [ -f "$legacy_file" ]; then
        mv -- "$legacy_file" "$backup_dir/$(basename -- "$legacy_file")"
    fi
done

systemctl --user daemon-reload
systemctl --user enable cursay-input.service >/dev/null
if [ "$install_backend" = true ]; then
    systemctl --user enable cursay-stt.service >/dev/null
fi
systemctl --user enable cursay.service >/dev/null
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
fi

if [ "$start_services" = true ]; then
    systemctl --user start cursay-input.service
    if [ "$install_backend" = true ]; then
        systemctl --user start cursay-stt.service
    fi
    systemctl --user start cursay.service
fi

printf '%s\n' \
    '' \
    'Cursay is installed.' \
    "Application: $install_root" \
    "Data:        $data_root/cursay"
if [ ! -w /dev/uinput ]; then
    printf '%s\n' \
        '' \
        'Clipboard copy is ready. Automatic paste needs one Ubuntu permission first:' \
        '  ./scripts/enable-autopaste.sh'
fi
printf '%s\n' \
    '' \
    'Open Cursay from the app launcher and approve its one-time Global Shortcut request.'
