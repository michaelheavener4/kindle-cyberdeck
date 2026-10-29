#!/bin/sh
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
cd /
jwm_pid=$1
params=$2
case "$jwm_pid" in ''|*[!0-9]*) exit 2 ;; esac
n=0
while [ "$jwm_pid" != 0 ] && kill -0 "$jwm_pid" 2>/dev/null; do
  n=$((n+1));[ "$n" -lt 15 ] || exit 1;sleep 1
done
n=0
while awk '$2 == "/var/tmp/chroot/cyberdeck" {f=1} END {exit !f}' /proc/mounts; do
  n=$((n+1));[ "$n" -lt 20 ] || { echo 'Reader handoff retained: Linux is still mounted.';exit 1; }
  sleep 1
done
lipc-set-prop com.lab126.powerd preventScreenSaver 0 2>/dev/null || true
lipc-set-prop com.lab126.kppReader openDocumentWithParams "$params"
echo "Reader handoff status=$? $(date)"
