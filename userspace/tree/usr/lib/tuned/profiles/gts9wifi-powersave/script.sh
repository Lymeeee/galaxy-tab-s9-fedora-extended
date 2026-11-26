#!/bin/sh
case "${1:-}" in
    start) exec /usr/bin/gts9wifi-power powersave ;;
    stop|verify) exit 0 ;;
esac
