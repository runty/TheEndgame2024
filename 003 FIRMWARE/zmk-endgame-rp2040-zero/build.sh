#!/usr/bin/env bash
# Build the sample-keymap firmware for the wired RP2040-Zero Choc V2 Endgame.
# Needs an initialized ZMK west workspace pinned at the revision below and
# the gnuarmemb toolchain (arm-none-eabi-gcc). Set ENDGAME_ZMK_WORKSPACE and
# WEST_BIN to point at them.
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${ENDGAME_ZMK_WORKSPACE:-/tmp/endgame-zmk-workspace}"
west_bin="${WEST_BIN:-/tmp/zmk-endgame-venv/bin/west}"
toolchain="${GNUARMEMB_TOOLCHAIN_PATH:-/opt/homebrew}"
revision="5b51501fead672c41b5cfb396f3dafe0894bf4e9"

if [ ! -x "$west_bin" ]; then
  echo "west not found at $west_bin; set WEST_BIN to an installed west command" >&2
  exit 2
fi
if [ ! -d "$workspace/.west" ]; then
  echo "Expected an initialized ZMK workspace at $workspace" >&2
  exit 2
fi
# Keep a symlinked, space-free workspace path as given.
workspace="$(cd "$workspace" && pwd)"
if [ "$(git -C "$workspace/zmk" rev-parse HEAD)" != "$revision" ]; then
  echo "ZMK checkout must be pinned at $revision" >&2
  exit 3
fi

staging_dir="$workspace/endgame-rp2040-zero"
mkdir -p "$root_dir/firmware" "$staging_dir/config"
# The RP2040 boot_stage2 link passes --specs=nosys.specs and links libc.
# Bare toolchains without newlib (e.g. Homebrew arm-none-eabi-gcc) have
# neither. boot_stage2 is self-contained assembly, so wrap gcc with a
# stand-in specs file that drops the libc link.
if [ "$("$toolchain/bin/arm-none-eabi-gcc" -print-file-name=nosys.specs)" = nosys.specs ]; then
  wrapped="$staging_dir/toolchain"
  mkdir -p "$wrapped/bin" "$wrapped/specs"
  printf '%%rename lib nosys_old_lib\n\n*lib:\n%%{!nostdlib:}\n\n' > "$wrapped/specs/nosys.specs"
  for tool in "$toolchain"/bin/arm-none-eabi-*; do
    ln -sf "$tool" "$wrapped/bin/$(basename "$tool")"
  done
  for compiler in gcc g++; do
    rm -f "$wrapped/bin/arm-none-eabi-$compiler"
    printf '#!/bin/sh\nexec "%s" -B"%s/" "$@"\n' \
      "$toolchain/bin/arm-none-eabi-$compiler" "$wrapped/specs" > "$wrapped/bin/arm-none-eabi-$compiler"
    chmod +x "$wrapped/bin/arm-none-eabi-$compiler"
  done
  toolchain="$wrapped"
fi
# ZMK's overlay list is split on whitespace, so stage this repository's
# space-containing path under a path without spaces for CMake/devicetree.
rsync -a --delete "$root_dir/config/" "$staging_dir/config/"
cd "$workspace"
for shield in endgame settings_reset; do
  build_dir="$workspace/build/endgame-rp2040-zero-$shield"
  ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb GNUARMEMB_TOOLCHAIN_PATH="$toolchain" \
    "$west_bin" build -p always -d "$build_dir" -s "$workspace/zmk/app" \
    -b rp2040_zero//zmk -- \
    -DSHIELD="$shield" \
    -DZMK_CONFIG="$staging_dir/config" \
    2>&1 | tee "$root_dir/firmware/build-$shield.log"
  name="endgame-rp2040-zero"
  [ "$shield" = settings_reset ] && name="endgame-rp2040-zero-settings-reset"
  cp "$build_dir/zephyr/zmk.uf2" "$root_dir/firmware/$name.uf2"
  shasum -a 256 "$root_dir/firmware/$name.uf2"
done
