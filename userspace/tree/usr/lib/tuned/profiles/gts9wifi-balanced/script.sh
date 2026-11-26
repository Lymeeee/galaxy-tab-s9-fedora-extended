#!/bin/sh
case "${1:-}" in
    start) exec /usr/bin/gts9wifi-power balanced ;;
    stop|verify) exit 0 ;;
esac
