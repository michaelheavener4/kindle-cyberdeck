#!/bin/sh
# Joy-Con page turns for the Kindle reader, and the on/off switch for the
# Bluetooth bridge. This never remounts the system partition and never
# installs an upstart job. A reboot leaves it stopped.
#
# The bridge is zampierilucas/kindle-hid-passthrough. Its own installer is
# not used.

if [ -n "$JOYCON_ROOT" ]; then
	ROOT=$JOYCON_ROOT
elif [ -d /mnt/us ]; then
	ROOT=/mnt/us
elif [ -d /mnt/kindle ]; then
	ROOT=/mnt/kindle
else
	ROOT=/mnt/us
fi

LINUX=$ROOT/linux
HID=$ROOT/kindle_hid_passthrough
BIN=$HID/kindle-hid-passthrough
PAGES_PID=$LINUX/joycon-pages.pid
DAEMON_PID=$LINUX/joycon-daemon.pid
MAP_LEARNED=$ROOT/joycon/map
MAP_DEFAULT=$LINUX/joycon.map
ALPINE_FLAG=$LINUX/joycon.alpine
PAIR_FLAG=$LINUX/joycon.pair
ON_FLAG=$LINUX/joycon.on
LOG=$LINUX/joycon-pages.log

say() {
	printf '%s\n' "$*"
	printf '%s\n' "$*" >>"$LOG" 2>/dev/null || true
}

map_file() {
	if [ -f "$MAP_LEARNED" ]; then
		printf '%s\n' "$MAP_LEARNED"
	else
		printf '%s\n' "$MAP_DEFAULT"
	fi
}

lookup_name() {
	code=$1
	file=$(map_file)
	[ -f "$file" ] || return 1
	awk -v c="$code" '
		/^#/ || NF < 2 { next }
		$1 == c { print $2; exit }
	' "$file"
}

side_of() {
	case "$1" in
	b|l|zl|minus|left|up) printf '%s\n' prev ;;
	a|r|zr|plus|right|down) printf '%s\n' next ;;
	*) return 1 ;;
	esac
}

pages_alive() {
	pid=$(cat "$PAGES_PID" 2>/dev/null) || return 1
	kill -0 "$pid" 2>/dev/null
}

daemon_alive() {
	pid=$(cat "$DAEMON_PID" 2>/dev/null) || pid=
	if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
		return 0
	fi
	for dir in /proc/[0-9]*; do
		[ -r "$dir/cmdline" ] || continue
		cmd=$(tr '\0' ' ' <"$dir/cmdline" 2>/dev/null) || continue
		case "$cmd" in
		*kindle-hid-passthrough*|*kindle_hid_passthrough/dist/main.bin*)
			return 0
			;;
		esac
	done
	return 1
}

have_pair() {
	[ -f "$HID/devices.conf" ] || return 1
	awk '
		/^#/ || NF < 2 { next }
		$1 ~ /^[0-9A-Fa-f][0-9A-Fa-f]:/ { found=1; exit }
		END { exit !found }
	' "$HID/devices.conf"
}

start_daemon() {
	mkdir -p "$LINUX" "$HID" 2>/dev/null || true
	# Pairing needs the radio. A retry from the desktop must not start
	# the bridge again until that prompt is done.
	if [ -f "$PAIR_FLAG" ]; then
		return 0
	fi
	if daemon_alive; then
		return 0
	fi
	if [ ! -x "$BIN" ] && [ ! -f "$BIN" ]; then
		if [ "$JOYCON_QUIET" != 1 ]; then
			say "The Joy-Con bridge is not on this Kindle yet."
		fi
		return 1
	fi
	if ! have_pair; then
		if [ "$JOYCON_QUIET" != 1 ]; then
			say "No Joy-Con is paired. Open Linux and press y."
		fi
		return 1
	fi
	if [ -f /etc/upstart/hid-passthrough.conf ]; then
		say "A boot service for the bridge is already installed. Leaving it alone."
		return 0
	fi
	chmod 755 "$BIN" "$HID/dist/ld-linux-armhf.so.3" "$HID/dist/main.bin" 2>/dev/null || true
	say "Starting the Joy-Con bridge."
	(
		cd "$HID" || exit 1
		"$BIN" --daemon
	) >>"$LINUX/hid-passthrough.log" 2>&1 &
	echo $! >"$DAEMON_PID"
	return 0
}

stop_daemon() {
	pid=$(cat "$DAEMON_PID" 2>/dev/null) || pid=
	if [ -n "$pid" ]; then
		kill -TERM "$pid" 2>/dev/null || true
	fi
	for dir in /proc/[0-9]*; do
		[ -r "$dir/cmdline" ] || continue
		cmd=$(tr '\0' ' ' <"$dir/cmdline" 2>/dev/null) || continue
		case "$cmd" in
		*kindle_hid_passthrough/dist/main.bin*|*kindle_hid_passthrough/kindle-hid-passthrough*)
			kill -TERM "${dir#/proc/}" 2>/dev/null || true
			;;
		esac
	done
	rm -f "$DAEMON_PID"
}

list_devices() {
	[ -r /proc/bus/input/devices ] || return 0
	awk '
		/^$/ { name = ""; handler = "" }
		/^N: Name=/ { name = tolower($0) }
		/^H: Handlers=/ {
			handler = ""
			for (i = 1; i <= NF; i++) {
				t = $i
				sub(/^Handlers=/, "", t)
				if (t ~ /^event[0-9]+$/) handler = t
			}
			if (handler != "" && name ~ /joy-con|joycon|nintendo/)
				print "/dev/input/" handler
		}
	' /proc/bus/input/devices
}

decode_bytes() {
	# 16 decimal bytes, the 32-bit input_event this Kindle kernel writes.
	[ "$#" -eq 16 ] || return 1
	type=$(( ${9} + ${10} * 256 ))
	code=$(( ${11} + ${12} * 256 ))
	value=${13}
	printf '%s %s %s\n' "$type" "$code" "$value"
}

read_event() {
	dev=$1
	# shellcheck disable=SC2046
	set -- $(od -An -tu1 -N16 "$dev" 2>/dev/null) || return 1
	decode_bytes "$@"
}

touch_node() {
	[ -r /proc/bus/input/devices ] || return 1
	awk '
		/^$/ { name = ""; prop = ""; abs = ""; handler = "" }
		/^N: Name=/ { name = tolower($0) }
		/^B: PROP=/ { prop = $2; sub(/PROP=/, "", prop) }
		/^B: ABS=/ { abs = $2 }
		/^H: Handlers=/ {
			handler = ""
			for (i = 1; i <= NF; i++) {
				t = $i
				sub(/^Handlers=/, "", t)
				if (t ~ /^event[0-9]+$/) handler = t
			}
		}
		{
			if (handler != "" && abs != "" &&
				prop ~ /[23671abefABEF]$/ &&
				name !~ /(wacom|stylus|pen)/) {
				print "/dev/input/" handler
				exit
			}
		}
	' /proc/bus/input/devices
}

screen_size() {
	modes=${TAP_MODES:-/sys/class/graphics/fb0/modes}
	sed -n 's/^[^:]*:\([0-9]*\)x\([0-9]*\).*/\1 \2/p' \
		"$modes" 2>/dev/null | head -n 1
}

# Screen percentages, turned into the panel's orientation. Portrait is 0.
# R, D, and L are the values com.lab126.winmgr reports.
orient_point() {
	x_pct=$1
	y_pct=$2
	rot=$TAP_ROTATION
	if [ -z "$rot" ]; then
		o=
		if command -v timeout >/dev/null 2>&1; then
			o=$(timeout 1 lipc-get-prop com.lab126.winmgr orientation 2>/dev/null) || o=
		elif command -v lipc-get-prop >/dev/null 2>&1; then
			o=$(lipc-get-prop com.lab126.winmgr orientation 2>/dev/null) || o=
		fi
		case "$o" in
		R) rot=270 ;;
		D) rot=180 ;;
		L) rot=90 ;;
		*) rot=0 ;;
		esac
	fi
	case "$rot" in
	90) printf '%s %s\n' $((100 - y_pct)) "$x_pct" ;;
	180) printf '%s %s\n' $((100 - x_pct)) $((100 - y_pct)) ;;
	270) printf '%s %s\n' "$y_pct" $((100 - x_pct)) ;;
	*) printf '%s %s\n' "$x_pct" "$y_pct" ;;
	esac
}

tap_at() {
	x_pct=$1
	y_pct=$2
	size=$(screen_size)
	w=${size% *}
	h=${size#* }
	case "$w$h" in
	''|*[!0-9]*) w=1272; h=1696 ;;
	esac
	oriented=$(orient_point "$x_pct" "$y_pct") || return 1
	x_pct=${oriented% *}
	y_pct=${oriented#* }
	if [ "$w" -gt "$h" ]; then
		t=$w
		w=$h
		h=$t
	fi
	x=$(( w * x_pct / 100 ))
	y=$(( h * y_pct / 100 ))
	if [ -n "$TAP_DRY_RUN" ]; then
		printf '%s %s\n' "$x" "$y"
		return 0
	fi
	dev=$(touch_node) || {
		say "No touchscreen to tap."
		return 1
	}
	byte() { printf '\\0%03o' $(( $1 & 255 )); }
	le16() { byte "$1"; byte "$(( $1 >> 8 ))"; }
	le32() {
		if [ "$1" -lt 0 ]; then
			byte 255; byte 255; byte 255; byte 255
			return 0
		fi
		byte "$1"
		byte "$(( $1 >> 8 ))"
		byte "$(( $1 >> 16 ))"
		byte "$(( $1 >> 24 ))"
	}
	ev() { le32 0; le32 0; le16 "$1"; le16 "$2"; le32 "$3"; }
	down=$(
		ev 1 330 1
		ev 3 47 0
		ev 3 55 0
		ev 3 57 0
		ev 3 58 18
		ev 3 53 "$x"
		ev 3 54 "$y"
		ev 3 48 18
		ev 3 50 18
		ev 0 0 0
	)
	up=$(
		ev 1 330 0
		ev 3 47 0
		ev 3 57 -1
		ev 0 0 0
	)
	printf '%b' "$down" >"$dev" || return 1
	usleep 80000 2>/dev/null || sleep 0
	printf '%b' "$up" >"$dev" || return 1
}

turn_page() {
	case "$1" in
	next) tap_at 85 50 ;;
	prev) tap_at 12 50 ;;
	esac
}

hold_page() {
	[ -f "$ALPINE_FLAG" ] && return 0
	[ -f "$PAIR_FLAG" ] && return 0
	return 1
}

watch_one() {
	dev=$1
	while [ -e "$PAGES_PID" ]; do
		if ! parsed=$(read_event "$dev"); then
			sleep 1
			continue
		fi
		# shellcheck disable=SC2086
		set -- $parsed
		type=$1
		code=$2
		value=$3
		[ "$type" = 1 ] || continue
		[ "$value" = 1 ] || continue
		hold_page && continue
		name=$(lookup_name "$code") || continue
		side=$(side_of "$name") || continue
		turn_page "$side" || say "Page tap failed."
	done
}

stop_watchers() {
	for pidf in /tmp/joycon-watch-*.pid; do
		[ -f "$pidf" ] || continue
		pid=$(cat "$pidf" 2>/dev/null) || true
		[ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null || true
		rm -f "$pidf"
	done
}

watch_loop() {
	while [ -e "$PAGES_PID" ]; do
		for dev in $(list_devices); do
			tag=$(basename "$dev")
			pidf=/tmp/joycon-watch-$tag.pid
			pid=$(cat "$pidf" 2>/dev/null) || pid=
			if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
				continue
			fi
			watch_one "$dev" &
			echo $! >"$pidf"
		done
		sleep 2
	done
}

alert() {
	title=$1
	text=$2
	title_esc=$(printf '%s' "$title" | sed 's/"/\\"/g')
	text_esc=$(printf '%s' "$text" | sed 's/"/\\"/g')
	json='{ "clientParams":{ "alertId":"appAlert1", "show":true, "customStrings":[ { "matchStr":"alertTitle", "replaceStr":"'"$title_esc"'" }, { "matchStr":"alertText", "replaceStr":"'"$text_esc"'" } ] } }'
	lipc-set-prop com.lab126.pillow pillowAlert "$json" 2>/dev/null || true
}

cmd_start() {
	mkdir -p "$LINUX" 2>/dev/null || true
	if pages_alive; then
		say "Joy-Con pages are already on."
		return 0
	fi
	if ! start_daemon; then
		alert "Joy-Con" "Open Linux and press y to pair. Hold the sync button on the rail until the lights slide."
		return 1
	fi
	echo $$ >"$PAGES_PID"
	echo 1 >"$ON_FLAG"
	trap 'rm -f "$PAGES_PID" "$ON_FLAG"; stop_watchers; exit 0' TERM INT
	say "Joy-Con pages on. L or B goes back. R or A goes forward."
	alert "Joy-Con" "Page turns are on. Press L or B for the previous page, R or A for the next. Tap this book again to stop."
	watch_loop
}

cmd_stop() {
	leader=$(cat "$PAGES_PID" 2>/dev/null) || leader=
	rm -f "$PAGES_PID" "$ON_FLAG"
	stop_watchers
	if [ -n "$leader" ]; then
		kill -TERM "$leader" 2>/dev/null || true
	fi
	stop_daemon
	say "Joy-Con off."
}

cmd_toggle() {
	if pages_alive; then
		cmd_stop
		alert "Joy-Con" "Page turns are off. A reboot leaves them off too."
		return 0
	fi
	setsid sh "$0" start </dev/null >>"$LOG" 2>&1 &
}

self_test() {
	fail=0
	check() {
		got=$1
		want=$2
		label=$3
		if [ "$got" = "$want" ]; then
			return 0
		fi
		printf 'FAIL %s: got [%s] want [%s]\n' "$label" "$got" "$want" >&2
		fail=1
	}
	check "$(side_of b)" prev "b"
	check "$(side_of a)" next "a"
	check "$(side_of l)" prev "l"
	check "$(side_of zr)" next "zr"
	check "$(side_of up)" prev "up"
	check "$(side_of down)" next "down"
	check "$(TAP_ROTATION=0 orient_point 85 50)" "85 50" "rot0"
	check "$(TAP_ROTATION=90 orient_point 85 50)" "50 85" "rot90"
	check "$(TAP_ROTATION=180 orient_point 85 50)" "15 50" "rot180"
	check "$(TAP_ROTATION=270 orient_point 85 50)" "50 15" "rot270"
	check "$(TAP_DRY_RUN=1 TAP_ROTATION=0 TAP_MODES=/dev/null tap_at 85 50)" "1081 848" "next-tap"
	check "$(TAP_DRY_RUN=1 TAP_ROTATION=0 TAP_MODES=/dev/null tap_at 12 50)" "152 848" "prev-tap"
	raw=$(printf '\0\0\0\0\0\0\0\0\1\0\061\1\1\0\0\0' | od -An -tu1 -N16)
	# shellcheck disable=SC2086
	set -- $raw
	parsed=$(decode_bytes "$@") || parsed=bad
	check "$parsed" "1 305 1" "event"
	[ "$fail" -eq 0 ] || exit 1
	echo "joycon-pages self-test ok"
}

case "$1" in
start) cmd_start ;;
stop) cmd_stop ;;
toggle) cmd_toggle ;;
start-daemon) start_daemon ;;
stop-daemon) stop_daemon ;;
action)
	name=$(lookup_name "$2") || exit 1
	side_of "$name"
	;;
decode)
	# shellcheck disable=SC2046
	set -- $(od -An -tu1 -N16)
	decode_bytes "$@"
	;;
self-test) self_test ;;
*)
	echo "usage: joycon-pages.sh start|stop|toggle|start-daemon|stop-daemon|self-test" >&2
	exit 1
	;;
esac
