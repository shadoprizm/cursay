#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rule_source="$source_dir/packaging/udev/70-cursay-uinput.rules"
rule_target=/etc/udev/rules.d/70-cursay-uinput.rules

if [ ! -f "$rule_source" ]; then
    printf 'Missing Cursay udev rule: %s\n' "$rule_source" >&2
    exit 1
fi

sudo install -m 0644 "$rule_source" "$rule_target"
sudo udevadm control --reload-rules
sudo udevadm trigger --name-match=uinput

if [ -w /dev/uinput ]; then
    systemctl --user restart cursay-input.service
    printf '%s\n' 'Cursay automatic paste is enabled.'
else
    printf '%s\n' \
        'The rule is installed, but this session has not received uinput access yet.' \
        'Sign out and back in, then restart Cursay.'
fi
