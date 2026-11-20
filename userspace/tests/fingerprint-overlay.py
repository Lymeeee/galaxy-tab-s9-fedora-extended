#!/usr/bin/env python3
"""Check the fingerprint overlay's lease parsing and screen geometry."""

import importlib.machinery
import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tree/usr/bin/gts9wifi-fingerprint-overlay"
)
loader = importlib.machinery.SourceFileLoader(
    "gts9wifi_fingerprint_overlay", str(SCRIPT)
)
spec = importlib.util.spec_from_loader("gts9wifi_fingerprint_overlay", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

now = 10_000_000
assert module.parse_active_lease("active 12000000 enroll\n", now) == "enroll"
assert module.parse_active_lease("active 12000000 identify\n", now) == "identify"
assert module.parse_active_lease("active 12000000\n", now) == "verify"
assert module.parse_active_lease("active 9000000 enroll\n", now) is None
assert module.parse_active_lease("active 14000000 enroll\n", now) is None
assert module.parse_active_lease("blocked 12000000\n", now) is None
assert module.parse_light_request("prepare 9999000\n") == 9999000
assert module.parse_light_request("prepare 0\n") == 0
assert module.parse_light_request("bogus\n") == 0
assert module.light_token_fresh(9_999_000, now)
assert not module.light_token_fresh(9_000_000, now)
assert not module.light_token_fresh(10_000_001, now)

assert module.prompt_for_action("enroll") == "请求指纹录入"
assert module.prompt_for_action("verify") == "请求指纹验证"
assert module.prompt_for_action("identify") == "请求指纹验证"
assert module.prompt_for_action("bogus") == "请求指纹验证"

rect = module.parse_fod_rect("700 2250 960 2480\n")
assert rect == (700, 2250, 960, 2480)
assert module.parse_fod_rect("0 0 0 0") is None
assert module.parse_fod_rect("700 2250") is None

u, v = module.sensor_fractions(rect, 0)
assert abs(u - 2365 / 2560) < 1e-12
assert abs(v - (1 - 830 / 1600)) < 1e-12
u, v = module.sensor_fractions(rect, 1)
assert abs(u - (1 - (1 - 830 / 1600))) < 1e-12
assert abs(v - 2365 / 2560) < 1e-12

cx, cy, radius = module.sensor_geometry(rect, 0, 1536, 960)
assert abs(cx - 1419.0) < 0.01
assert abs(cy - 462.0) < 0.01
assert radius == 48

text_width, text_height = 140, 28
x, y = module.layout_text(1536, 960, cx, cy, radius, text_width, text_height)
ring_left, ring_right = cx - radius, cx + radius
gap = 1536 - ring_right
assert abs(x + text_width - (ring_left - gap)) < 0.01
assert abs(y - (cy - text_height / 2)) < 0.01

cx, cy, radius = module.sensor_geometry(rect, 1, 1536, 960)
x, y = module.layout_text(1536, 960, cx, cy, radius, text_width, text_height)
ring_top, ring_bottom = cy - radius, cy + radius
gap = 960 - ring_bottom
assert abs(y + text_height - (ring_top - gap)) < 0.01
assert abs(x - (cx - text_width / 2)) < 0.01

x, y = module.layout_text(1536, 960, 100, 480, 48, text_width, text_height)
assert abs(x - 200) < 0.01
assert abs(y - (480 - text_height / 2)) < 0.01
