#!/bin/sh
# Scriptlet. Eject USB, then tap this book.
# Stops the Amazon reader UI and opens the Alpine desktop.
mkdir -p /mnt/us/linux
if command -v setsid >/dev/null 2>&1; then
	setsid sh /mnt/us/linux/run.sh </dev/null >>/mnt/us/linux/linux.log 2>&1 &
elif command -v nohup >/dev/null 2>&1; then
	nohup sh /mnt/us/linux/run.sh </dev/null >>/mnt/us/linux/linux.log 2>&1 &
else
	sh /mnt/us/linux/run.sh </dev/null >>/mnt/us/linux/linux.log 2>&1 &
fi
exit 0
