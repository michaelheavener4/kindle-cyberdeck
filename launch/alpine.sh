#!/bin/sh
#
# alpine.sh - mount the Alpine rootfs image and drop into it (Kindle side).
# Derived from schuhumi/alpine_kindle (GPL-3.0) - see README.md.
#
# Usage on the Kindle:
#   sh alpine.sh              shell inside Alpine
#   sh alpine.sh startgui     mount, then start the JWM desktop
#   sh alpine.sh cleanup      unmount whatever a killed session left behind
#
# Everything this script prints is ALSO appended to alpine-run.log next to the
# image. So instead of copying text off the e-ink screen, plug the Kindle into a
# PC and read /mnt/us/alpine-run.log there.

DIR="$(dirname "$0")"
[ "$DIR" = "." ] && DIR="$(pwd)"
MNT=/var/tmp/chroot/cyberdeck
LOG="$DIR/alpine-run.log"
SWAPDEV=""
BACKING_DIR="$DIR"
# The user-facing /mnt/us is FSP/FUSE on modern Kindles. Keep loop-device
# I/O on the native filesystem, without a userspace daemon in its path.
if [ "$DIR" = /mnt/us ] && [ -f /mnt/base-us/alpine.ext3 ]; then
  BACKING_DIR=/mnt/base-us
fi

# /tmp is a symlink to /var/tmp on current firmware. mount(8) reports the
# resolved path, so string-matching only "/tmp/alpine" misses a live mount.
MNT_PARENT="$(readlink -f "$(dirname "$MNT")" 2>/dev/null)"
[ -n "$MNT_PARENT" ] || MNT_PARENT="$(dirname "$MNT")"
MNT_REAL="$MNT_PARENT/$(basename "$MNT")"
rootfs_is_mounted() {
  awk -v logical="$MNT" -v real="$MNT_REAL" \
    '$2 == logical || $2 == real { found=1 } END { exit !found }' /proc/mounts
}

# ------------------------------------------------------------- logging ------
: > "$LOG" 2>/dev/null
say() {
  echo "$@"
  echo "$@" >> "$LOG" 2>/dev/null
}

# A snapshot taken from inside the chroot, so a failing run leaves useful facts
# behind without anyone having to type them.
snapshot() {
  {
    echo "--- chroot snapshot ---"
    echo "alpine-release: $(cat "$MNT/etc/alpine-release" 2>/dev/null)"
    echo "installed pkgs: $(chroot "$MNT" /bin/sh -c 'apk list --installed 2>/dev/null | wc -l' 2>/dev/null)"
    echo "uname:          $(chroot "$MNT" /bin/sh -c 'uname -m' 2>/dev/null)"
    echo "free -m:";      chroot "$MNT" /bin/sh -c 'free -m' 2>&1 | sed 's/^/  /'
    echo "df -h /:";      chroot "$MNT" /bin/sh -c 'df -h /' 2>&1 | sed 's/^/  /'
    echo "/proc/swaps:";  sed 's/^/  /' /proc/swaps
    echo "--- end snapshot ---"
  } >> "$LOG" 2>&1
}

# ---------------------------------------------------------------- swap ------
# swap.img is a pre-formatted block image: attach it with losetup and swap on
# the loop device (a swap *file* is impossible on the vfat userstore).
#
# Node naming differs between firmwares: some expose /dev/loop<N>, others (e.g.
# firmware 5.19.x on an 11th gen) expose /dev/loop/<N> as a *directory*. So ask
# sysfs which loops exist and which are free instead of guessing paths.
find_free_loop() {
  # 1. sysfs: a loop whose backing_file is empty has nothing attached
  for b in /sys/block/loop*; do
    [ -d "$b" ] || continue
    BF="$b/loop/backing_file"
    [ -r "$BF" ] || continue
    [ -s "$BF" ] && continue
    N="${b##*/}"
    if [ -b "/dev/$N" ]; then echo "/dev/$N"; return 0; fi
    if [ -b "/dev/loop/${N#loop}" ]; then echo "/dev/loop/${N#loop}"; return 0; fi
  done
  # 2. whatever losetup offers, if the node actually exists
  L="$(losetup -f 2>/dev/null)"
  if [ -n "$L" ] && [ -b "$L" ]; then echo "$L"; return 0; fi
  # 3. brute force, both layouts
  for d in /dev/loop[0-9] /dev/loop[0-9][0-9] /dev/loop/[0-9] /dev/loop/[0-9][0-9]; do
    [ -b "$d" ] || continue
    losetup "$d" 2>/dev/null | grep -q . && continue
    echo "$d"; return 0
  done
  return 1
}

# Detach any loop device backed by file $1. Not every firmware releases the loop
# device on unmount, and there are only ~16 of them.
detach_loop_for() {
  BASE="$(basename "$1")"
  for b in /sys/block/loop*; do
    [ -d "$b" ] || continue
    BF="$b/loop/backing_file"
    [ -r "$BF" ] || continue
    case "$(cat "$BF" 2>/dev/null)" in
      *"$BASE")
        N="${b##*/}"
        if [ -b "/dev/$N" ]; then DEV="/dev/$N"
        else DEV="/dev/loop/${N#loop}"; fi
        if losetup -d "$DEV" 2>/dev/null; then
          say "Detached loop device ${N#loop}"
        else
          say "WARNING: could not detach loop device ${N#loop}"
        fi
        ;;
    esac
  done
}

enable_swap() {
  # Loop-backed swap through FUSE can stall reclaim and freeze the device.
  # This 1 GB Kindle runs the desktop and GB core without file-backed swap.
  [ -f "$DIR/linux/enable-swap" ] || { say "File-backed swap disabled."; return 0; }
  [ "$BACKING_DIR" = /mnt/base-us ] || { say "Swap requires native backing storage."; return 0; }
  [ -f "$BACKING_DIR/swap.img" ] || return 0
  # A previous session (or tools/diag.sh) may already have it attached.
  for b in /sys/block/loop*; do
    [ -r "$b/loop/backing_file" ] || continue
    case "$(cat "$b/loop/backing_file" 2>/dev/null)" in
      *swap.img) say "Swap already active - leaving it as is."; return 0 ;;
    esac
  done
  L="$(find_free_loop)" || { say "No free loop device for swap - continuing without it."; return 0; }
  if ! losetup "$L" "$BACKING_DIR/swap.img" 2>/dev/null; then
    say "Could not attach $L to swap.img - continuing without swap."
    return 0
  fi
  if swapon "$L" 2>/dev/null; then
    SWAPDEV="$L"
    say "Swap enabled on $SWAPDEV"
  else
    losetup -d "$L" 2>/dev/null
    say "swapon failed (kernel without CONFIG_SWAP?) - continuing without swap."
  fi
}

disable_swap() {
  [ -n "$SWAPDEV" ] || return 0
  swapoff "$SWAPDEV" 2>/dev/null
  losetup -d "$SWAPDEV" 2>/dev/null
  say "Swap disabled ($SWAPDEV)"
  SWAPDEV=""
}

# -------------------------------------------------------------- mounting ---
mount_rootfs() {
  say "Mounting Alpine rootfs ($BACKING_DIR/alpine.ext3)"
  mkdir -p "$MNT"
  mount -o loop,noatime -t ext3 "$BACKING_DIR/alpine.ext3" "$MNT" || return 1
  mount -o bind /dev     "$MNT/dev"
  mount -o bind /dev/pts "$MNT/dev/pts"
  mount -o bind /proc    "$MNT/proc"
  mount -o bind /sys     "$MNT/sys"
  mount -o bind /var/run/dbus "$MNT/run/dbus" 2>/dev/null
  mkdir -p "$MNT/mnt/kindle"
  if mount -o bind /mnt/us "$MNT/mnt/kindle" 2>/dev/null; then
    say "Bound the Kindle userstore at /mnt/kindle"
  else
    say "WARNING: could not bind /mnt/us into Alpine"
  fi

  # Live network + host config from the Kindle itself.
  [ -r /etc/hosts ] && cp /etc/hosts "$MNT/etc/hosts"
  if [ -r /etc/resolv.conf ]; then
    cp -L /etc/resolv.conf "$MNT/etc/resolv.conf"
  else
    echo "nameserver 8.8.8.8" > "$MNT/etc/resolv.conf"
  fi
  chmod a+w /dev/shm 2>/dev/null

  enable_swap
  snapshot
}

unmount_rootfs() {
  say "Leaving Alpine, cleaning up"
  pkill Xephyr 2>/dev/null
  sleep 1
  # Release surviving session buses/loaders, scoped strictly to this chroot.
  for sig in TERM KILL; do
    for process in /proc/[0-9]*; do
      process_root=$(readlink "$process/root" 2>/dev/null) || continue
      case "$process_root" in
        "$MNT"|"$MNT_REAL"|"$MNT_REAL"/*) kill -"$sig" "${process#/proc/}" 2>/dev/null || true ;;
      esac
    done
    [ "$sig" = TERM ] && sleep 2
  done
  disable_swap
  umount "$MNT/mnt/kindle" 2>/dev/null
  umount "$MNT/run/dbus" 2>/dev/null
  umount "$MNT/sys" 2>/dev/null
  umount "$MNT/proc" 2>/dev/null
  umount "$MNT/dev/pts" 2>/dev/null
  umount "$MNT/dev" 2>/dev/null
  if command -v timeout >/dev/null 2>&1; then timeout 5 sync || true; else sync; fi
  umount "$MNT" 2>/dev/null
  # Desktop processes can take a moment to release the rootfs. Retry for at most
  # ten seconds, checking both the logical and resolved mountpoint names.
  i=0
  while rootfs_is_mounted; do
    i=$((i + 1))
    [ "$i" -gt 10 ] && { say "WARNING: $MNT still mounted - reboot to clean up."; break; }
    say "Still busy, retrying (${i}/10)..."
    sleep 1
    umount "$MNT" 2>/dev/null
  done
  if rootfs_is_mounted; then
    say "ERROR: Alpine rootfs is still mounted at $MNT_REAL."
    return 1
  fi
  # Free the loop devices too - firmware does not always do it for us.
  detach_loop_for "$DIR/alpine.ext3"
  detach_loop_for "$DIR/swap.img"
  say "Alpine unmounted."
}

# Scripts in linux/bin replace the copies baked into the image, so a menu
# fix does not need another 1.5 GB copy. The userstore is vfat, so the
# executable bit is applied after the copy onto ext3.
install_launchers() {
  if [ -d "$DIR/linux/bin" ]; then
    mkdir -p "$MNT/usr/local/bin"
    n=0
    for f in "$DIR/linux/bin/"*; do
      [ -f "$f" ] || continue
      base="$(basename "$f")"
      if cp "$f" "$MNT/usr/local/bin/$base"; then
        chmod 755 "$MNT/usr/local/bin/$base"
        n=$((n + 1))
      else
        say "WARNING: could not install $base"
      fi
    done
    say "Installed $n launcher scripts from $DIR/linux/bin"
  fi
  if [ -f "$MNT/home/alpine/.ssh/config" ]; then
    # Kindle sed -i is not reliable. Rewrite, then keep ssh's required mode.
    sed 's|^[[:space:]]*ProxyCommand .*|  ProxyCommand /usr/bin/tailscale --socket=/run/tailscale/tailscaled.sock nc %h %p|' \
      "$MNT/home/alpine/.ssh/config" >"$MNT/home/alpine/.ssh/config.new" \
      && mv "$MNT/home/alpine/.ssh/config.new" "$MNT/home/alpine/.ssh/config" \
      && chmod 600 "$MNT/home/alpine/.ssh/config" \
      && say "Pointed SSH at the userspace Tailscale socket"
  fi
}

# ------------------------------------------------------------------ main ---
# Recovery mode: clean up mounts left behind by a session that was killed rather
# than exited (e.g. connecting USB stops the framework and kills kterm without
# running any cleanup). Safe to run when nothing is mounted.
if [ "$1" = "cleanup" ]; then
  say "Cleaning up any leftover Alpine mounts..."
  unmount_rootfs
  exit $?
fi

if rootfs_is_mounted; then
  say "Rootfs already mounted - entering the existing session."
  ALREADY=yes
else
  ALREADY=no
  mount_rootfs || { say "ERROR: could not mount $DIR/alpine.ext3"; exit 1; }
fi

install_launchers

status=0
if [ "$1" = "startgui" ] || [ "$1" = "gui" ]; then
  say "Starting the JWM desktop (Xephyr on the Kindle's X server)..."
  if [ -f "$DIR/linux/startgui.sh" ]; then
    chroot "$MNT" /bin/sh /mnt/kindle/linux/startgui.sh
  else
    chroot "$MNT" /startgui.sh
  fi
  status=$?
else
  say "Dropping into Alpine. Type 'exit' to come back to the Kindle."
  chroot "$MNT" /bin/sh
  status=$?
fi

if [ "$ALREADY" = "yes" ] && [ "$1" != startgui ] && [ "$1" != gui ]; then
  say "Another Alpine session is still using $MNT - leaving it mounted."
else
  unmount_rootfs || {
    say "ERROR: unmount failed"
    [ "$status" -eq 0 ] && status=1
  }
fi

say "Log written to $LOG"
exit "$status"
