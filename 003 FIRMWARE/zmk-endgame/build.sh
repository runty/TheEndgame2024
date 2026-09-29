#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${ENDGAME_ZMK_WORKSPACE:-/tmp/endgame-zmk-workspace}"

if ! command -v west >/dev/null 2>&1; then
  echo "west is required; install it with: python3 -m pip install --user west" >&2
  exit 2
fi

mkdir -p "$workspace"
workspace="$(cd "$workspace" && pwd)"
if [ ! -d "$workspace/.west" ]; then
  mkdir -p "$workspace/config"
  rsync -a --delete "$root_dir/config/" "$workspace/config/"
  git -C "$workspace/config" init -q -b main
  # west init creates .west in the current directory, so enter the workspace
  # explicitly instead of depending on the caller's working directory.
  cd "$workspace"
  west init -l config
else
  rsync -a --delete --exclude='.git' "$root_dir/config/" "$workspace/config/"
fi
cd "$workspace"
west config manifest.path config
west update
west zephyr-export

zmk_dir="$(west list zmk -f '{abspath}')"
if ! git -C "$zmk_dir" apply --check "$root_dir/patches/zmk-kscan-spi-irq.patch" 2>/dev/null; then
  if git -C "$zmk_dir" apply --reverse --check "$root_dir/patches/zmk-kscan-spi-irq.patch" 2>/dev/null; then
    echo "ZMK SPI-backed matrix IRQ patch is already applied."
  else
    echo "The ZMK source does not match the bundled IRQ patch base." >&2
    exit 3
  fi
else
  git -C "$zmk_dir" apply "$root_dir/patches/zmk-kscan-spi-irq.patch"
fi

build_dir="$workspace/build/endgame"

west build -p always -d "$build_dir" -s "$zmk_dir/app" \
  -b xiao_ble/nrf52840/zmk -- \
  -DSHIELD=endgame \
  -DZMK_CONFIG="$workspace/config" \
  -DCONFIG_ZMK_SLEEP=y \
  -DCONFIG_ZMK_IDLE_SLEEP_TIMEOUT=900000

if [ -f "$build_dir/zephyr/zmk.uf2" ]; then
  cp "$build_dir/zephyr/zmk.uf2" "$root_dir/firmware/endgame-xiao-nrf52840.uf2"
else
  cp "$build_dir/zephyr/zephyr.uf2" "$root_dir/firmware/endgame-xiao-nrf52840.uf2"
fi
