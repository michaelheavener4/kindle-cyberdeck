#!/bin/sh
echo "kindle linux log"
echo
if [ -f /mnt/us/linux/linux.log ]; then
	tail -n 40 /mnt/us/linux/linux.log
else
	echo "No log yet. Eject USB, then open the Linux book."
fi
if [ -f /mnt/us/alpine-run.log ]; then
	echo
	echo "---- alpine-run.log ----"
	tail -n 20 /mnt/us/alpine-run.log
fi
sleep 20
