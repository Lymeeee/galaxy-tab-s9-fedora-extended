#!/usr/bin/env python3
"""Check the PMIC RTC anchor arithmetic and validation."""

import importlib.machinery
import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tree/usr/libexec/gts9wifi-rtc-time"
)
loader = importlib.machinery.SourceFileLoader("gts9wifi_rtc_time", str(SCRIPT))
spec = importlib.util.spec_from_loader("gts9wifi_rtc_time", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

anchor = {"counter": 1000, "utc": 1760000000}
assert module.restore_value(anchor, 1000) == 1760000000
assert module.restore_value(anchor, 1600) == 1760000600

for counter in (900, 1000 + 10 * 366 * 86400 + 1):
    try:
        module.restore_value(anchor, counter)
    except ValueError:
        pass
    else:
        raise AssertionError(f"counter {counter} should have been rejected")

try:
    module.restore_value({"counter": 0, "utc": 100}, 100)
except ValueError:
    pass
else:
    raise AssertionError("an anchor before 2025 should have been rejected")

print("RTC anchor arithmetic OK")
