#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$HERE/overlay/usr/local/lib"
clang --target=armv7-linux-musleabihf -march=armv7-a \
  -mfloat-abi=hard -mfpu=vfpv3-d16 -fPIC -shared -nostdlib \
  -fuse-ld=lld -O2 -Wall -Wextra -Werror \
  "$HERE/host/kindle-touch-browser.c" \
  -o "$HERE/overlay/usr/local/lib/libkindle-touch-browser.so"
echo 'Built the touch browser front end.'
