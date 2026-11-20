#!/usr/bin/env python3
"""Exercise the DTB finder and partition writer of the BT provisioner."""

import importlib.machinery
import importlib.util
import pathlib
import struct
import subprocess
import sys
import tempfile

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
ADDR = "00:2B:70:33:A9:D0"
LE = bytes.fromhex(ADDR.replace(":", ""))[::-1]


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

assert module.parse_address(ADDR) == LE
assert module.parse_address("not-an-address") is None

DTS = """
/dts-v1/;
/ {
    soc@0 {
        geniqup@8c0000 {
            serial@898000 {
                bluetooth {
                    compatible = "gts9-bt-test";
                };
            };
        };
    };
};
"""


def prop_of(blob):
    with tempfile.NamedTemporaryFile() as f:
        f.write(blob)
        f.flush()
        out = subprocess.run(
            ["fdtget", "-t", "bx", f.name, module.NODE, module.PROP],
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        return bytes(int(v, 16) for v in out.stdout.split())


def boot_dtb(path):
    data = path.read_bytes()
    ksize = struct.unpack_from("<I", data, 8)[0]
    kernel = data[4096:4096 + ksize]
    off = module.find_appended_dtb(kernel, ksize)
    assert off is not None
    total = struct.unpack_from(">I", kernel, off + 4)[0]
    return kernel[off:off + total]


def vendor_dtb(path):
    data = path.read_bytes()
    vrsize = struct.unpack_from("<I", data, 24)[0]
    hsize, dtb_size = struct.unpack_from("<II", data, 2096)
    off = module.page_align(hsize) + module.page_align(vrsize)
    return data[off:off + dtb_size]


with tempfile.TemporaryDirectory() as name:
    tmp = pathlib.Path(name)
    dts = tmp / "test.dts"
    dtb_path = tmp / "test.dtb"
    dts.write_text(DTS)
    subprocess.run(
        ["dtc", "-q", "-I", "dts", "-O", "dtb", "-o",
         str(dtb_path), str(dts)],
        check=True,
    )
    blob = dtb_path.read_bytes()

    boot = tmp / "boot.img"
    head = bytearray(4096)
    head[:8] = b"ANDROID!"
    kernel = b"\x01" * 128 + blob + b"\x00" * 37
    struct.pack_into("<I", head, 8, len(kernel))
    boot.write_bytes(bytes(head) + kernel + b"\x00" * 8192)

    vendor = tmp / "vendor_boot.img"
    head = bytearray(4096)
    head[:8] = b"VNDRBOOT"
    struct.pack_into("<I", head, 24, 0)
    struct.pack_into("<II", head, 2096, 2112, len(blob))
    envelope = module.page_align(len(blob))
    vendor.write_bytes(
        bytes(head) + blob + b"\x00" * (envelope - len(blob))
        + b"\x00" * 4096
    )

    module.BOOT = str(boot)
    module.VENDOR_BOOT = str(vendor)
    assert module.provision_boot(LE) is True
    assert module.provision_vendor_boot(LE) is True
    assert module.provision_boot(LE) is False
    assert module.provision_vendor_boot(LE) is False
    assert prop_of(boot_dtb(boot)) == LE
    assert prop_of(vendor_dtb(vendor)) == LE

    module.CACHE = str(tmp / "bt-address")
    module.cache_address(ADDR)
    assert (tmp / "bt-address").read_text().strip() == ADDR
    module.cache_address(ADDR)

print("bt-provision DTB writer OK")
