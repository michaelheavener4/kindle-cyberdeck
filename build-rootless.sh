#!/bin/bash
# Build the Alpine image without root. qemu-arm-static is a static binary, and
# a user namespace provides the chroot. mke2fs -d packs the tree into ext3.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VENDOR="$HERE/vendor/alpine-kindle"
WORK="$HERE/build/root"
CACHE="$HERE/build/cache"
OUT="$HERE/release"
IMAGE="$OUT/alpine.ext3"
SWAP="$OUT/swap.img"
KEYDIR="$OUT/ssh"
BRANCH="${ALPINE_BRANCH:-v3.24}"
ARCH="${ARCH:-armv7}"
IMAGESIZE_MB="${IMAGESIZE_MB:-1536}"
SWAP_MB="${SWAP_MB:-512}"
REPO="https://dl-cdn.alpinelinux.org/alpine"
QEMU="$(command -v qemu-arm-static)"

log() { printf '\n==> %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ -n "$QEMU" ] || die "qemu-arm-static is not installed"
[ -d "$VENDOR/rootfs" ] || die "missing $VENDOR (clone adiglase/alpine-kindle)"
command -v mke2fs >/dev/null || die "mke2fs is not installed"
command -v mkswap >/dev/null || die "mkswap is not installed"
command -v curl >/dev/null || die "curl is not installed"

PKGS=(
	alpine-base
	xorg-server-xephyr xwininfo xdpyinfo xauth xdotool xinput xset xterm xrandr xprop
	dbus dbus-x11
	jwm
	onboard
	py3-pillow py3-gobject3 py3-cairo tzdata
	netsurf
	sudo bash nano git curl unzip desktop-file-utils htop
	font-dejavu font-liberation font-noto hicolor-icon-theme
	openssh-client tmux tailscale
	mgba
)

log "Resolving Alpine $BRANCH $ARCH minirootfs"
MINI="$(curl -fsSL "$REPO/$BRANCH/releases/$ARCH/" \
	| grep -oE "alpine-minirootfs-[0-9.]+-$ARCH\\.tar\\.gz" | sort -uV | tail -1)"
[ -n "$MINI" ] || die "no minirootfs at $REPO/$BRANCH/releases/$ARCH/"
log "Using $MINI"

mkdir -p "$CACHE" "$OUT" "$KEYDIR"
TARBALL="$CACHE/$MINI"
if [ ! -f "$TARBALL" ]; then
	curl -fL -o "$TARBALL.part" "$REPO/$BRANCH/releases/$ARCH/$MINI"
	curl -fsSL -o "$CACHE/$MINI.sha256" "$REPO/$BRANCH/releases/$ARCH/$MINI.sha256"
	EXPECTED="$(awk '{print $1; exit}' "$CACHE/$MINI.sha256")"
	ACTUAL="$(sha256sum "$TARBALL.part" | awk '{print $1}')"
	[ -n "$EXPECTED" ] && [ "$EXPECTED" = "$ACTUAL" ] || die "checksum mismatch for $MINI"
	mv "$TARBALL.part" "$TARBALL"
fi

if [ ! -f "$KEYDIR/id_ed25519" ]; then
	log "Generating a Kindle SSH key"
	ssh-keygen -t ed25519 -N "" -C "kindle-cyberdeck" -f "$KEYDIR/id_ed25519"
fi
AUTH="$HOME/.ssh/authorized_keys"
touch "$AUTH"
PUB="$(cat "$KEYDIR/id_ed25519.pub")"
if ! grep -qxF "$PUB" "$AUTH"; then
	echo "$PUB" >>"$AUTH"
	log "Added the Kindle public key to $AUTH"
else
	log "Omarchy already trusts the Kindle public key"
fi

log "Unpacking rootfs"
rm -rf "$WORK"
mkdir -p "$WORK"
tar -xzf "$TARBALL" -C "$WORK"
cat >"$WORK/etc/apk/repositories" <<EOF
http://dl-cdn.alpinelinux.org/alpine/$BRANCH/main
http://dl-cdn.alpinelinux.org/alpine/$BRANCH/community
EOF
echo kindle >"$WORK/etc/hostname"
mkdir -p "$WORK/run/dbus" "$WORK/tmp"
cp "$QEMU" "$WORK/usr/bin/qemu-arm-static"

cat >"$WORK/tmp/setup.sh" <<EOF
set -e
export PATH=/sbin:/usr/sbin:/bin:/usr/bin
apk update
apk upgrade
# Triggers redirect to /dev/null. The build namespace cannot open real
# device nodes, so a trigger failure here is not a missing package.
apk add --no-cache ${PKGS[*]} || true
command -v jwm >/dev/null
command -v ssh >/dev/null
command -v tmux >/dev/null
command -v tailscale >/dev/null
command -v xterm >/dev/null
addgroup -S sudo 2>/dev/null || true
if ! grep -q '^alpine:' /etc/passwd; then
	echo 'alpine:x:1000:1000:Linux User:/home/alpine:/bin/bash' >> /etc/passwd
fi
if ! grep -q '^alpine:' /etc/shadow; then
	echo 'alpine:!:19000:0:99999:7:::' >> /etc/shadow
fi
if ! grep -q '^alpine:' /etc/group; then
	echo 'alpine:x:1000:alpine' >> /etc/group
fi
for g in sudo video audio input dialout; do
	addgroup -S "\$g" 2>/dev/null || true
	addgroup alpine "\$g" 2>/dev/null || true
done
grep -q '^%sudo' /etc/sudoers || echo '%sudo ALL=(ALL) ALL' >> /etc/sudoers
mkdir -p /home/alpine /run/dbus
EOF

run_chroot() {
	local script="$1"
	# A user namespace on this kernel can mount proc and individual device
	# nodes. It cannot mount sysfs or the whole of /dev.
	unshare --user --map-root-user --mount --pid --fork bash -c "
		set -euo pipefail
		mount -t proc proc '$WORK/proc'
		mkdir -p '$WORK/dev' '$WORK/dev/shm' '$WORK/dev/pts'
		mount -t tmpfs tmpfs '$WORK/dev'
		# Device nodes from the host cannot be opened inside this user
		# namespace. Regular files are enough for the package triggers.
		: > '$WORK/dev/null'
		dd if=/dev/zero of='$WORK/dev/zero' bs=1024 count=256 status=none
		dd if=/dev/urandom of='$WORK/dev/urandom' bs=1024 count=256 status=none
		cp -a '$WORK/dev/urandom' '$WORK/dev/random'
		chmod 666 '$WORK/dev/null' '$WORK/dev/zero' '$WORK/dev/urandom' '$WORK/dev/random'
		cp -L /etc/resolv.conf '$WORK/etc/resolv.conf'
		# Drop the host PATH. Arch has no /bin, and Alpine keeps apk in /sbin.
		chroot '$WORK' /usr/bin/qemu-arm-static /usr/bin/env -i \
			PATH=/sbin:/usr/sbin:/bin:/usr/bin \
			HOME=/root TERM=linux \
			/bin/sh '$script'
		umount '$WORK/dev' || true
		umount '$WORK/proc' || true
	"
}

log "Installing packages (qemu-arm, this is the slow part)"
run_chroot /tmp/setup.sh
rm -f "$WORK/tmp/setup.sh"

log "Patching Onboard for X11-only use"
ONBOARD_PYDIR="$(find "$WORK/usr/lib" -type d -path '*/site-packages/Onboard' -print -quit)"
[ -n "$ONBOARD_PYDIR" ] || die "Onboard Python package not found"
grep -q '^import unicodedata$' "$ONBOARD_PYDIR/TextContext.py" || die "unexpected Onboard TextContext.py"
grep -q 'self.text_context = self.atspi_text_context' "$ONBOARD_PYDIR/WordSuggestions.py" || die "unexpected Onboard WordSuggestions.py"
sed -i '/^import unicodedata$/a import os' "$ONBOARD_PYDIR/TextContext.py"
sed -i 's/_state_tracker = AtspiStateTracker()/_state_tracker = None if os.environ.get("ONBOARD_X11_ONLY") == "1" else AtspiStateTracker()/' \
	"$ONBOARD_PYDIR/TextContext.py"
sed -i 's/^        self.text_context.enable(True)$/        if os.environ.get("ONBOARD_X11_ONLY") != "1":\n            self.text_context.enable(True)/' \
	"$ONBOARD_PYDIR/WordSuggestions.py"

log "Installing desktop and cyberdeck overlay"
cp -a "$VENDOR/rootfs/." "$WORK/"
cp -a "$HERE/overlay/." "$WORK/"
chmod 755 "$WORK/usr/local/bin/"* "$WORK/startgui.sh"
# Shipped by upstream as a non-executable file. The session invokes it by path.
chmod 755 "$WORK/usr/local/bin/kindle-session" "$WORK/usr/local/bin/kindle-onboard" \
	"$WORK/usr/local/bin/kindle-keyboard" "$WORK/usr/local/bin/kindle-close-window" \
	"$WORK/usr/local/bin/kindle-chromium" 2>/dev/null || true

mkdir -p "$WORK/home/alpine/.ssh" "$WORK/home/alpine/.tailscale"
cp "$KEYDIR/id_ed25519" "$WORK/home/alpine/.ssh/id_ed25519"
cp "$KEYDIR/id_ed25519.pub" "$WORK/home/alpine/.ssh/id_ed25519.pub"
cat >"$WORK/home/alpine/.ssh/config" <<'EOF'
Host omarchy
  HostName omarchy.example.invalid
  User zephyrillius
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  ServerAliveInterval 15
  ServerAliveCountMax 4
  ProxyCommand /usr/bin/tailscale --socket=/run/tailscale/tailscaled.sock nc %h %p

Host mac
  HostName mac.example.invalid
  User a.
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  ServerAliveInterval 15
  ServerAliveCountMax 4
  ProxyCommand /usr/bin/tailscale --socket=/run/tailscale/tailscaled.sock nc %h %p
EOF
chmod 700 "$WORK/home/alpine/.ssh"
chmod 600 "$WORK/home/alpine/.ssh/id_ed25519" "$WORK/home/alpine/.ssh/config"
chmod 644 "$WORK/home/alpine/.ssh/id_ed25519.pub"
chown -R 1000:1000 "$WORK/home/alpine"

log "Checking JWM config and the tools the menu calls"
cat >"$WORK/tmp/check.sh" <<'EOF'
set -e
jwm -p -f /etc/jwm/system.jwmrc
command -v ssh
command -v tmux
command -v tailscale
command -v tailscaled
command -v mgba
tailscale --help 2>&1 | grep -q nc
tailscaled --help 2>&1 | grep -q userspace-networking
test -x /usr/local/bin/cyberdeck
test -x /usr/local/bin/deck-connect
test -f /home/alpine/.ssh/id_ed25519
EOF
run_chroot /tmp/check.sh
rm -f "$WORK/tmp/check.sh" "$WORK/usr/bin/qemu-arm-static"

# The guest install marks busybox and bbsuid execute-only. mke2fs has to
# read every file, and this user owns them, so owner-read is enough.
chmod -R u+r "$WORK"

log "Packing ${IMAGESIZE_MB} MiB ext3 image"
rm -f "$IMAGE"
mke2fs -t ext3 -F -L alpine -d "$WORK" "$IMAGE" "${IMAGESIZE_MB}M"
tune2fs -i 0 -c 0 "$IMAGE" >/dev/null

if [ "$SWAP_MB" -gt 0 ]; then
	log "Creating ${SWAP_MB} MiB swap image"
	rm -f "$SWAP"
	dd if=/dev/zero of="$SWAP" bs=1M count="$SWAP_MB" status=progress
	chmod 600 "$SWAP"
	mkswap "$SWAP" >/dev/null
fi

cp "$HERE/launch/alpine.sh" "$OUT/alpine.sh"
chmod 755 "$OUT/alpine.sh"
printf '%s\n' "$MINI" >"$OUT/SOURCE.txt"
log "Image ready: $IMAGE"
ls -lh "$IMAGE" "$SWAP" "$OUT/alpine.sh"
