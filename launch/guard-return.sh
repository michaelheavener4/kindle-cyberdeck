#!/bin/sh
# One-session native bridge for a desktop started by the previous runner.
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
jwm_pid=$1
case "$jwm_pid" in ''|*[!0-9]*) exit 2 ;; esac
while kill -0 "$jwm_pid" 2>/dev/null; do sleep 1; done
for sig in TERM KILL; do
  for process in /proc/[0-9]*; do
    root=$(readlink "$process/root" 2>/dev/null) || continue
    case "$root" in /tmp/alpine|/var/tmp/alpine|/var/tmp/alpine/*|/var/tmp/chroot/cyberdeck|/var/tmp/chroot/cyberdeck/*) kill -"$sig" "${process#/proc/}" 2>/dev/null || true ;; esac
  done
  [ "$sig" = TERM ] && sleep 2
done
# The old runner performs its normal unmount and native reader restoration.
n=0
while [ "$n" -lt 45 ]; do
  n=$((n+1))
  if ! awk '$2 == "/tmp/alpine" || $2 == "/var/tmp/alpine" || $2 == "/var/tmp/chroot/cyberdeck" {f=1} END {exit !f}' /proc/mounts; then
    lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null || true
    if /sbin/initctl status framework 2>/dev/null | grep -q start/running; then
      if [ -f /mnt/us/linux/sleep-after-exit ]; then
        rm -f /mnt/us/linux/sleep-after-exit
        sleep 4
        lipc-set-prop com.lab126.powerd powerButton 1 2>/dev/null || true
      fi
      exit 0
    fi
  fi
  sleep 1
done
