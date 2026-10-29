#!/bin/sh
# Keep Kindle's reader below Xephyr. Its power manager owns suspend/frontlight.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
echo "=== kindle-linux $(date) ==="
rm -f /mnt/us/linux/sleep-after-exit
cleanup() {
  lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null || true
  # Never start framework over a live /var/tmp/alpine mount: its pre-start
  # script recursively changes /var/tmp permissions.
  if ! awk '$2 == "/tmp/alpine" || $2 == "/var/tmp/alpine" || $2 == "/var/tmp/chroot/cyberdeck" {f=1} END {exit !f}' /proc/mounts; then
    /sbin/initctl start lab126_gui 2>/dev/null || true
    /sbin/initctl start framework 2>/dev/null || true
  fi
  if [ -f /mnt/us/linux/sleep-after-exit ]; then
    rm -f /mnt/us/linux/sleep-after-exit
    lipc-set-prop com.lab126.powerd powerButton 1 2>/dev/null || true
  fi
  echo "Kindle power management restored."
}
trap cleanup EXIT
trap 'exit 143' TERM HUP INT
if [ ! -f /mnt/us/alpine.ext3 ] || [ ! -f /mnt/us/alpine.sh ]; then
  echo "Alpine image is missing from /mnt/us"; exit 1
fi
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null || true
/sbin/initctl start pillow 2>/dev/null || true
/sbin/initctl start x 2>/dev/null || true
sh /mnt/us/alpine.sh startgui
status=$?
echo "Alpine exit $status"
exit "$status"
