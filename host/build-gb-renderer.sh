#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$HERE/release/gb" "$HERE/overlay/usr/local/lib"
clang --target=armv7-linux-musleabihf -march=armv7-a \
  -mfloat-abi=hard -mfpu=vfpv3-d16 -fPIC -shared -nostdlib \
  -fuse-ld=lld -O2 -Wall -Wextra -Werror \
  "$HERE/host/kindle-sdl-software.c" \
  -o "$HERE/release/gb/libkindle-sdl-software.so"
cp "$HERE/release/gb/libkindle-sdl-software.so" "$HERE/overlay/usr/local/lib/"
echo 'Built Kindle mGBA software renderer.'
