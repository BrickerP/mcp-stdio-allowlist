#!/usr/bin/env python3
"""Write docs/demo-eval.gif — animated terminal-style held-out eval demo.

Pure Python GIF89a (stdlib only). No ffmpeg, no Pillow.
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo-eval.gif"
W, H = 480, 140

FRAMES = [
    [
        "MCP-STDIO-ALLOWLIST  PROMPT-INJECTION EVAL",
        "POLICY TUNED ON DEV ONLY",
        "HELD-OUT  SCRIPTED AGENT  NO API KEY",
        "",
        "REPLAYING PRESCRIBED TOOL CALLS",
    ],
    [
        "INJECTION  FILESYSTEM.READ  ETC/PASSWD",
        "ALLOWLIST ON  ->  BLOCKED",
        "BENIGN  FILESYSTEM.READ  DOCS/GUIDE.MD",
        "ALLOWLIST ON  ->  ALLOWED",
        "BASELINE OFF LETS INJECTIONS ESCAPE",
    ],
    [
        "HELD-OUT RESULT",
        "BLOCK_RATE=1.0000",
        "FALSE_BLOCK_RATE=0.0000",
        "N=16  INJECTION=8  BENIGN=8",
        "SOURCES: HAND-WRITTEN (ORIGINAL)",
    ],
]

# 5x7 glyphs, 7 ints of 5 bits. Covers A-Z 0-9 and the punctuation we print.
_G = {
    " ": "0000000",
    "-": "0001000",
    ".": "0000006",
    "/": "0122440",
    ":": "0060060",
    ">": "0010201",
    "=": "0001010",
    "_": "0000001",
    "0": "7555557",
    "1": "6222227",
    "2": "7116471",
    "3": "7117117",
    "4": "1123471",
    "5": "7471171",
    "6": "7175571",
    "7": "7111222",
    "8": "7575571",
    "9": "7557117",
    "A": "2557555",
    "B": "6556556",
    "C": "7444447",
    "D": "6555556",
    "E": "7447447",
    "F": "7447444",
    "G": "7455547",
    "H": "5557555",
    "I": "7222227",
    "J": "1111152",
    "K": "5566555",
    "L": "4444447",
    "M": "5775555",
    "N": "5655555",
    "O": "7555557",
    "P": "6556444",
    "Q": "7555653",
    "R": "6556555",
    "S": "7447117",
    "T": "7222222",
    "U": "5555557",
    "V": "5555522",
    "W": "5555755",
    "X": "5522555",
    "Y": "5522222",
    "Z": "7124447",
}


def _bits(spec: str) -> list[int]:
    # spec is 7 octal-ish digits; we store real bit rows instead.
    del spec
    return []


# Real 5-bit rows (bit 4 = leftmost pixel).
FONT: dict[str, list[int]] = {
    " ": [0, 0, 0, 0, 0, 0, 0],
    "-": [0, 0, 0, 31, 0, 0, 0],
    ".": [0, 0, 0, 0, 0, 12, 12],
    "/": [1, 2, 4, 8, 16, 0, 0],
    ":": [0, 12, 12, 0, 12, 12, 0],
    ">": [16, 8, 4, 2, 4, 8, 16],
    "=": [0, 0, 31, 0, 31, 0, 0],
    "_": [0, 0, 0, 0, 0, 0, 31],
    "0": [14, 17, 19, 21, 25, 17, 14],
    "1": [4, 12, 4, 4, 4, 4, 14],
    "2": [14, 17, 1, 6, 8, 16, 31],
    "3": [14, 17, 1, 6, 1, 17, 14],
    "4": [2, 6, 10, 18, 31, 2, 2],
    "5": [31, 16, 30, 1, 1, 17, 14],
    "6": [6, 8, 16, 30, 17, 17, 14],
    "7": [31, 1, 2, 4, 8, 8, 8],
    "8": [14, 17, 17, 14, 17, 17, 14],
    "9": [14, 17, 17, 15, 1, 2, 12],
    "A": [14, 17, 17, 31, 17, 17, 17],
    "B": [30, 17, 17, 30, 17, 17, 30],
    "C": [14, 17, 16, 16, 16, 17, 14],
    "D": [30, 17, 17, 17, 17, 17, 30],
    "E": [31, 16, 16, 30, 16, 16, 31],
    "F": [31, 16, 16, 30, 16, 16, 16],
    "G": [14, 17, 16, 23, 17, 17, 14],
    "H": [17, 17, 17, 31, 17, 17, 17],
    "I": [14, 4, 4, 4, 4, 4, 14],
    "J": [7, 2, 2, 2, 2, 18, 12],
    "K": [17, 18, 20, 24, 20, 18, 17],
    "L": [16, 16, 16, 16, 16, 16, 31],
    "M": [17, 27, 21, 21, 17, 17, 17],
    "N": [17, 25, 21, 19, 17, 17, 17],
    "O": [14, 17, 17, 17, 17, 17, 14],
    "P": [30, 17, 17, 30, 16, 16, 16],
    "Q": [14, 17, 17, 17, 21, 18, 13],
    "R": [30, 17, 17, 30, 20, 18, 17],
    "S": [14, 17, 16, 14, 1, 17, 14],
    "T": [31, 4, 4, 4, 4, 4, 4],
    "U": [17, 17, 17, 17, 17, 17, 14],
    "V": [17, 17, 17, 17, 10, 10, 4],
    "W": [17, 17, 17, 21, 21, 27, 17],
    "X": [17, 17, 10, 4, 10, 17, 17],
    "Y": [17, 17, 10, 4, 4, 4, 4],
    "Z": [31, 1, 2, 4, 8, 16, 31],
}


def raster(lines: list[str]) -> bytearray:
    px = bytearray(W * H)  # 0 = bg
    for i, line in enumerate(lines[:8]):
        y0 = 10 + i * 16
        x = 10
        accent = any(k in line for k in ("BLOCK", "ALLOW", "FALSE", "HELD-OUT RESULT"))
        color = 2 if accent else 1
        for ch in line:
            glyph = FONT.get(ch, FONT[" "])
            for gy, bits in enumerate(glyph):
                for gx in range(5):
                    if bits & (1 << (4 - gx)):
                        xx, yy = x + gx, y0 + gy
                        if 0 <= xx < W and 0 <= yy < H:
                            px[yy * W + xx] = color
            x += 6
            if x >= W - 6:
                break
    return px


def lzw(indices: bytes, min_code_size: int = 8) -> bytes:
    """GIF LZW image-data sub-blocks. clear/eoi live outside the symbol table."""
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    next_code = eoi + 1
    table: dict[bytes, int] = {bytes([i]): i for i in range(clear)}

    bits = 0
    nbits = 0
    raw = bytearray()

    def write(code: int) -> None:
        nonlocal bits, nbits, code_size
        bits |= code << nbits
        nbits += code_size
        while nbits >= 8:
            raw.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8
        # Width increases after a code that filled the current range is written.
        if code_size < 12 and next_code >= (1 << code_size):
            code_size += 1

    def reset() -> None:
        nonlocal next_code, code_size
        write(clear)
        table.clear()
        table.update({bytes([i]): i for i in range(clear)})
        next_code = eoi + 1
        code_size = min_code_size + 1

    reset()
    w = b""
    for byte in indices:
        k = bytes([byte])
        wk = w + k
        if wk in table:
            w = wk
            continue
        write(table[w])
        if next_code < 4096:
            table[wk] = next_code
            next_code += 1
        else:
            reset()
        w = k
    if w:
        write(table[w])
    write(eoi)
    if nbits:
        raw.append(bits & 0xFF)

    out = bytearray([min_code_size])
    for i in range(0, len(raw), 255):
        block = raw[i : i + 255]
        out.append(len(block))
        out += block
    out.append(0)
    return bytes(out)


def build_gif(frames: list[bytearray]) -> bytes:
    # 3-color palette padded to 256: bg, fg, accent
    pal = bytearray([12, 16, 20, 186, 214, 176, 232, 176, 64])
    pal += bytes(3 * (256 - 3))
    g = bytearray(b"GIF89a")
    g += struct.pack("<HH", W, H)
    g += bytes([0xF7, 0x00, 0x00])
    g += pal
    # Netscape loop
    g += b"!\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    for frame in frames:
        g += b"!\xf9\x04\x04\x64\x00\x00\x00"  # delay 1.0s, dispose background
        g += b"," + struct.pack("<HHHH", 0, 0, W, H) + b"\x00"
        g += lzw(bytes(frame))
    g += b";"
    return bytes(g)


def main() -> None:
    data = build_gif([raster(lines) for lines in FRAMES])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    print(f"wrote {OUT} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
