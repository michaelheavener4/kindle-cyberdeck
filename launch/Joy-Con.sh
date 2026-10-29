#!/bin/sh
# Scriptlet. Eject USB, then tap this book.
# Starts the Joy-Con bridge for the Kindle reader. Tap again to stop it.
# Reboot also stops it. It does not install a boot service.
mkdir -p /mnt/us/linux
if command -v setsid >/dev/null 2>&1; then
	setsid sh /mnt/us/linux/joycon-pages.sh toggle </dev/null >>/mnt/us/linux/joycon-book.log 2>&1 &
else
	sh /mnt/us/linux/joycon-pages.sh toggle </dev/null >>/mnt/us/linux/joycon-book.log 2>&1 &
fi
exit 0
