#!/usr/bin/python3
# SPDX-License-Identifier: MIT
"""Build-time test for the gts9wifi-camera-calib Chromatix parser."""

import importlib.machinery
import importlib.util
import os
import struct
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "..", "tree", "usr", "libexec",
                      "gts9wifi-camera-calib")

loader = importlib.machinery.SourceFileLoader("camera_calib", HELPER)
spec = importlib.util.spec_from_loader("camera_calib", loader)
camera_calib = importlib.util.module_from_spec(spec)
loader.exec_module(camera_calib)

PARSER = b"Parameter Parser V3.5.1 (2207122229)"

MATRIX_A = (1.2, -0.1, -0.1,
            -0.1, 1.2, -0.1,
            -0.1, -0.1, 1.2)
MATRIX_B = (1.1, -0.05, -0.05,
            -0.2, 1.3, -0.1,
            -0.1, -0.1, 1.2)


def node_row(node_id, name, relative, size, reference):
    row = bytearray(60)
    struct.pack_into("<I", row, 0, node_id)
    encoded = name.encode("ascii")
    row[4:4 + len(encoded)] = encoded
    struct.pack_into("<III", row, 48, relative, size, reference)
    return bytes(row)


def descriptor():
    payloads = [
        struct.pack("<2f4I", 1.0, 16.0, 1, 2, 0, 3),
        struct.pack("<2f4I", 2000.0, 3000.0, 0, 4, 1, 5) +
        struct.pack("<2f4I", 4000.0, 6000.0, 0, 4, 1, 6),
        b"",
        struct.pack("<9f", *MATRIX_A),
        struct.pack("<9f", *MATRIX_B),
    ]
    rows = [
        node_row(1, "mod_cc14_trigger_data", 0, len(payloads[0]), 1),
        node_row(2, "trigger", len(payloads[0]), len(payloads[1]), 2),
        node_row(4, "trigger", 0, 0, 4),
        node_row(5, "region", len(payloads[0]) + len(payloads[1]),
                 len(payloads[3]), 5),
        node_row(6, "region",
                 len(payloads[0]) + len(payloads[1]) + len(payloads[3]),
                 len(payloads[4]), 6),
    ]
    schema = b"".join(rows)
    data = b"".join(payloads)
    schema_offset = 204
    data_offset = schema_offset + len(schema)
    blob = bytearray(schema_offset)
    blob[:20] = b"QTI Chromatix Header"
    blob[40:40 + len(PARSER)] = PARSER
    struct.pack_into("<II", blob, 160, 168, 3)
    struct.pack_into("<III", blob, 168, 0, schema_offset, len(schema))
    struct.pack_into("<III", blob, 180, 1, data_offset, len(data))
    struct.pack_into("<III", blob, 192, 2, data_offset + len(data), 0)
    blob += schema + data
    struct.pack_into("<I", blob, 28, len(blob))
    blob += struct.pack("<I", zlib.crc32(blob))
    return bytes(blob)


def main():
    blob = descriptor()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as stream:
        stream.write(blob)
        path = stream.name
    try:
        digest, points = camera_calib.extract(path)
        assert len(digest) == 64
        assert [ct for ct, _matrix in points] == [2500, 5000], points
        for got, expected in ((points[0][1], MATRIX_A),
                              (points[1][1], MATRIX_B)):
            assert all(abs(a - b) < 1e-6 for a, b in zip(got, expected)), got
        text = camera_calib.render_yaml(path, digest, points)
        assert "ct: 2500" in text and "ct: 5000" in text
        assert "2.198100" not in text

        broken = bytearray(blob)
        broken[-1] ^= 0xff
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as stream:
            stream.write(broken)
            broken_path = stream.name
        try:
            camera_calib.extract(broken_path)
        except camera_calib.CalibrationError:
            pass
        else:
            raise AssertionError("corrupt CRC was accepted")
        finally:
            os.unlink(broken_path)
    finally:
        os.unlink(path)

    assert camera_calib.matrix_from_region(
        struct.pack("<9f", 1.0, 2.0, 2.0, 0, 1, 0, 0, 0, 1)) is None
    print("camera-calib test OK")


if __name__ == "__main__":
    main()
