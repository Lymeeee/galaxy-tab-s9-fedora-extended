#!/usr/bin/env python3
"""Validate the libwacom definition shipped for the Tab S9 S Pen."""

import configparser
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tree/usr/share/libwacom"
TABLET = ROOT / "samsung-gts9wifi-spen.tablet"
STYLUS = ROOT / "samsung-gts9wifi-spen.stylus"


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

if device.get("Name") != "Samsung Galaxy Tab S9":
    fail("the tablet must be named Samsung Galaxy Tab S9")
if "@samsung-spen" not in device.get("Styli", ""):
    fail("Styli must use the shipped @samsung-spen description")

stylus_config = configparser.ConfigParser()
if not stylus_config.read(STYLUS):
    fail(f"missing {STYLUS}")
if not stylus_config.has_section("0x56a:0xffe0"):
    fail("the stylus description must define 0x56a:0xffe0")
stylus = stylus_config["0x56a:0xffe0"]
if stylus.get("Name") != "Samsung S Pen":
    fail("the stylus must be named Samsung S Pen")
if stylus.get("Group") != "samsung-spen":
    fail("the stylus group must be samsung-spen")
if stylus.get("Buttons") != "1":
    fail("the S Pen has one side button")

print("libwacom S Pen definition OK")
