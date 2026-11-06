#!/usr/bin/env python3
"""Validate the libwacom definition shipped for the Tab S9 S Pen."""

import configparser
import pathlib
import sys

TABLET = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tree/usr/share/libwacom/samsung-gts9wifi-spen.tablet"
)


def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)


config = configparser.ConfigParser()
if not config.read(TABLET):
    fail(f"missing {TABLET}")

if "Device" not in config or "Features" not in config:
    fail("Device and Features sections are required")

device = config["Device"]
features = config["Features"]

matches = {item.strip() for item in device.get("DeviceMatch", "").split(";")}
for required in ("i2c|056a|0000", "i2c|0000|0000"):
    if required not in matches:
        fail(f"DeviceMatch is missing {required}")

if device.get("Class") != "ISDV4":
    fail("Class must be ISDV4")

integrated = device.get("IntegratedIn", "")
if "Display" not in integrated or "System" not in integrated:
    fail("IntegratedIn must contain Display and System")

for key in ("Width", "Height"):
    try:
        value = int(device[key])
    except (KeyError, ValueError):
        fail(f"{key} must be an integer in millimetres")
    if value <= 0:
        fail(f"{key} must be positive")

if features.get("Stylus") != "true":
    fail("Features/Stylus must be true")
if features.get("Touch") != "false":
    fail("Features/Touch must be false")

if not device.get("Styli", "").startswith("@generic-no-eraser"):
    fail("the S Pen has no eraser; Styli must use @generic-no-eraser")

print("libwacom S Pen definition OK")
