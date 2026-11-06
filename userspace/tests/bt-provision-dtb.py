#!/usr/bin/env python3
"""Exercise the appended-DTB finder used by the BT address provisioner."""

import importlib.machinery
import importlib.util
import pathlib
import struct
import sys

sys.dont_write_bytecode = True

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tree/usr/libexec/gts9wifi-bt-provision"
)
loader = importlib.machinery.SourceFileLoader(
    "gts9wifi_bt_provision", str(SCRIPT)
)
spec = importlib.util.spec_from_loader("gts9wifi_bt_provision", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

MAGIC = b"\xd0\x0d\xfe\xed"


def dtb(total):
    return MAGIC + struct.pack(">I", total) + b"\x00" * (total - 8)


exact = dtb(64)
assert module.find_appended_dtb(exact, len(exact)) == 0

padded = dtb(64) + b"\x00" * 37
assert module.find_appended_dtb(padded, len(padded)) == 0

prefix = b"\x01" * 128
kernel = prefix + dtb(64) + b"\x00" * 37
assert module.find_appended_dtb(kernel, len(kernel)) == 128

assert module.find_appended_dtb(dtb(64) + b"\x01", 65) is None
assert module.find_appended_dtb(b"\x00" * 100, 100) is None

print("bt-provision DTB finder OK")
