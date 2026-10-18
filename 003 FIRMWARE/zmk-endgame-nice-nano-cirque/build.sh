#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${ENDGAME_ZMK_WORKSPACE:-/tmp/endgame-zmk-workspace}"
west_bin="${WEST_BIN:-/tmp/zmk-endgame-venv/bin/west}"
revision="5b51501fead672c41b5cfb396f3dafe0894bf4e9"

if [ ! -x "$west_bin" ]; then
  echo "west not found at $west_bin; set WEST_BIN to an installed west command" >&2
  exit 2
fi
if [ ! -d "$workspace/.west" ]; then
  echo "Expected an initialized ZMK workspace at $workspace" >&2
  exit 2
fi
workspace="$(cd "$workspace" && pwd -P)"

source_checkout="$workspace/zmk"
if [ "$(git -C "$source_checkout" rev-parse HEAD)" != "$revision" ]; then
  echo "ZMK checkout must be pinned at $revision" >&2
  exit 3
fi

# The known-good Cirque setup needs a small Zephyr Pinnacle driver patch:
# only act on SW_DR, report tap changes only, and kick the data-ready work
# once at init. Apply it to the workspace's Zephyr checkout exactly once.
pinnacle_patch="$root_dir/patches/zephyr/input-pinnacle-cirque.patch"
if git -C "$workspace/zephyr" apply --check "$pinnacle_patch" 2>/dev/null; then
  git -C "$workspace/zephyr" apply "$pinnacle_patch"
elif ! git -C "$workspace/zephyr" apply --reverse --check "$pinnacle_patch" 2>/dev/null; then
  echo "Unable to apply $pinnacle_patch to $workspace/zephyr" >&2
  exit 4
fi

staging_dir="$workspace/endgame-nice-nano-cirque"
zmk_dir="$staging_dir/zmk"
mkdir -p "$root_dir/firmware"
mkdir -p "$staging_dir/config" "$staging_dir/status-pulse" "$staging_dir/rgbled-widget"
# Extract the pinned, tracked source into this build's own tree. The older
# XIAO workspace may have the old 74HC595 kscan IRQ patch applied locally;
# this firmware must compile the stock direct-matrix driver instead.
if [ ! -f "$zmk_dir/.endgame-pinned-source" ]; then
  mkdir -p "$zmk_dir"
  git -C "$source_checkout" archive "$revision" | tar -xf - -C "$zmk_dir"
  touch "$zmk_dir/.endgame-pinned-source"
fi
# ZMK's overlay list is split on whitespace, so stage this repository's
# space-containing path under a path without spaces for CMake/devicetree.
rsync -a --delete "$root_dir/config/" "$staging_dir/config/"
rsync -a --delete "$root_dir/status-pulse/" "$staging_dir/status-pulse/"
rsync -a --delete "$root_dir/rgbled-widget/" "$staging_dir/rgbled-widget/"
cd "$workspace"

build() {
  local shield="$1" out="$2" build_dir="$workspace/build/endgame-nice-nano-cirque-$1"
  shift 2
  # Build logs contain local paths; firmware/*.log is ignored by git.
  ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb GNUARMEMB_TOOLCHAIN_PATH=/opt/homebrew \
    "$west_bin" build -p always -d "$build_dir" -s "$zmk_dir/app" \
    -b nice_nano//zmk -- -DSHIELD="$shield" "$@" \
    2>&1 | tee "$root_dir/firmware/$out.log"

  if [ -f "$build_dir/zephyr/zmk.uf2" ]; then
    cp "$build_dir/zephyr/zmk.uf2" "$root_dir/firmware/$out.uf2"
  else
    cp "$build_dir/zephyr/zephyr.uf2" "$root_dir/firmware/$out.uf2"
  fi
}

build endgame endgame-nice-nano-cirque \
  -DZMK_CONFIG="$staging_dir/config" \
  -DZMK_EXTRA_MODULES="$staging_dir/status-pulse;$staging_dir/rgbled-widget"
build settings_reset settings-reset-nice-nano

shasum -a 256 "$root_dir"/firmware/*.uf2
