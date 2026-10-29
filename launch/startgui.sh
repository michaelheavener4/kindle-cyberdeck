#!/bin/sh
# Runs inside the chroot. Nests an X server on the Kindle's :0 and starts JWM.
# The image's /bin/su is a setuid helper owned by uid 1000, so it cannot
# set groups. The session runs as root with the alpine home directory.
# The Kindle scriptlet does not source Alpine's profile, so sbin is missing
# and `tailscaled` would fail with no output.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
chmod a+w /dev/shm 2>/dev/null

mkdir -p /run/dbus
[ -S /run/dbus/system_bus_socket ] || dbus-daemon --system --fork 2>/dev/null

SIZE="$(xwininfo -root -display :0 | awk '/-geometry/{print $2; exit}')"
[ -n "$SIZE" ] || SIZE=1272x1696
echo "Xephyr screen $SIZE"

env DISPLAY=:0 Xephyr :1 -title "L:A_N:application_ID:xephyr_WS:true_O:U" \
	-ac -br -screen "$SIZE" -cc 4 -reset &
xephyr_pid=$!

attempt=0
until env DISPLAY=:1 xdpyinfo >/dev/null 2>&1; do
	attempt=$((attempt + 1))
	if [ "$attempt" -ge 20 ] || ! kill -0 "$xephyr_pid" 2>/dev/null; then
		echo "ERROR: Xephyr display :1 did not become ready." >&2
		kill "$xephyr_pid" 2>/dev/null || true
		wait "$xephyr_pid" 2>/dev/null || true
		exit 1
	fi
	sleep 1
done

export HOME=/home/alpine
export USER=root
export LOGNAME=root
if [ -x /usr/local/bin/deck-fix-ssh ]; then
  /usr/local/bin/deck-fix-ssh || exit 1
fi
if [ -x /usr/local/bin/deck-ssh-server ]; then
  /usr/local/bin/deck-ssh-server >>/mnt/kindle/linux/sshd.log 2>&1 || \
    echo 'SSH server could not start; see linux/sshd.log'
fi
# Start the saved Tailscale connection without tying it to a terminal window.
nohup sh -c '. /usr/local/bin/deck-net; deck_net_prepare' \
  </dev/null >/mnt/kindle/linux/network-start.log 2>&1 &
network_pid=$!
cd /home/alpine || exit 1
env DISPLAY=:1 HOME=/home/alpine GSETTINGS_BACKEND=keyfile NO_AT_BRIDGE=1 \
  dbus-run-session -- /usr/local/bin/kindle-session
status=$?
kill "$network_pid" 2>/dev/null || true
wait "$network_pid" 2>/dev/null || true
# The session restores the USB port. Do it again if the session was killed.
if [ -x /usr/local/bin/deck-usb-host ]; then
	deck-usb-host down >/dev/null 2>&1 || true
fi
kill "$xephyr_pid" 2>/dev/null || true
wait "$xephyr_pid" 2>/dev/null || true
exit "$status"
