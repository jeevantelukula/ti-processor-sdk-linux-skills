#!/usr/bin/env python3
"""Decode K3 pad-configuration register values using the SDK's own header.

The bit layout and the PIN_* macro values are read from the kernel's
k3-pinctrl.h (arch/arm64/boot/dts/ti/k3-pinctrl.h), so nothing about a
specific SoC is hard-coded here. Every <SOC>_IOPAD() macro in that header
shares the same layout.

Usage:
  decode-iopad.py [--header PATH] VALUE [VALUE ...]   # hex or decimal
  decode-iopad.py [--header PATH] --pins-file FILE    # debugfs pinctrl 'pins' file ('-' = stdin)
  decode-iopad.py [--header PATH] --macros            # list IOPAD macros and PIN_* values

Header lookup: --header, else $TI_KERNEL_SRC_DIR (or $TI_SDK_ROOT/board-support/ti-linux-kernel-*).
"""
import argparse
import ast
import glob
import os
import re
import signal
import sys

HEADER_REL = "arch/arm64/boot/dts/ti/k3-pinctrl.h"
DEFINE_RE = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+(\(.*\)|\d+)\s*(?:/\*.*)?$")
PINS_RE = re.compile(r"^pin\s+(\d+)\s+\((\S+)\)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s")


def find_header(explicit):
    if explicit:
        return explicit
    candidates = []
    ksrc = os.environ.get("TI_KERNEL_SRC_DIR", "")
    if ksrc:
        candidates.append(os.path.join(ksrc, HEADER_REL))
    root = os.environ.get("TI_SDK_ROOT", "")
    if root:
        candidates += sorted(glob.glob(os.path.join(root, "board-support", "ti-linux-kernel-*", HEADER_REL)))
    for c in candidates:
        if os.path.isfile(c):
            return c
    sys.exit("error: k3-pinctrl.h not found; pass --header or source lib/ti-sdk-env.sh")


def parse_header(path):
    defs, funcs = {}, []
    with open(path) as fh:
        for line in fh:
            m = re.match(r"^\s*#define\s+(\w+)\(", line)
            if m:
                funcs.append(m.group(1))
                continue
            m = DEFINE_RE.match(line)
            if m:
                defs[m.group(1)] = m.group(2)
    return defs, funcs


def evaluate(expr, defs, stack=()):
    """Evaluate a C integer expression using only << | and parentheses."""
    def sub(match):
        n = match.group(0)
        if n in stack:
            raise ValueError("recursive define " + n)
        if n not in defs:
            raise ValueError("unknown name " + n)
        return str(evaluate(defs[n], defs, stack + (n,)))
    text = re.sub(r"[A-Za-z_]\w*", sub, expr)
    node = ast.parse(text.strip(), mode="eval")
    for sub_node in ast.walk(node):
        if not isinstance(sub_node, (ast.Expression, ast.BinOp, ast.Constant, ast.LShift, ast.BitOr)):
            raise ValueError("unsupported expression: " + expr)
    return eval(compile(node, "<hdr>", "eval"), {"__builtins__": {}})


class Layout:
    def __init__(self, path):
        self.path = path
        defs, self.funcs = parse_header(path)
        self.defs = defs
        # Flags/fields: <NAME>_SHIFT. Width = bit_length of the largest N used as (N << NAME_SHIFT).
        self.fields = {}
        for name, expr in defs.items():
            if name.endswith("_SHIFT"):
                self.fields[name[:-6]] = [evaluate(expr, defs), 1]
        for expr in defs.values():
            for n, shift in re.findall(r"\((\d+)\s*<<\s*(\w+)_SHIFT\)", expr):
                if shift in self.fields:
                    self.fields[shift][1] = max(self.fields[shift][1], int(n).bit_length())
        self.pin_macros = {}
        for name, expr in defs.items():
            if name.startswith("PIN_"):
                try:
                    self.pin_macros[name] = evaluate(expr, defs)
                except ValueError:
                    pass

    def decode(self, value, mux_mask):
        """Return (mux + set fields, exact PIN_* macro names). Zero-valued fields are omitted."""
        parts, known = [], mux_mask
        parts.append("MUX=%d" % (value & mux_mask))
        for name, (shift, width) in sorted(self.fields.items(), key=lambda kv: kv[1][0]):
            mask = ((1 << width) - 1) << shift
            known |= mask
            if value & mask:
                parts.append("%s=%d" % (name, (value & mask) >> shift))
        rest = value & ~known & 0xFFFFFFFF
        if rest:
            parts.append("unnamed_bits=0x%08x" % rest)
        base = value & ~mux_mask & 0xFFFFFFFF
        # A zero-valued macro (PIN_DEBOUNCE_DISABLE, PIN_DS_*...) matches everything with the
        # corresponding bits clear; only report zero-valued direction/pull combinations.
        exact = sorted(n for n, v in self.pin_macros.items()
                       if v == base and (v != 0 or re.match(r"PIN_(INPUT|OUTPUT)", n)))
        return parts, exact


def parse_value(text):
    try:
        return int(text, 0)
    except ValueError:
        return int(text, 16)


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("values", nargs="*")
    ap.add_argument("--header", help="path to k3-pinctrl.h")
    ap.add_argument("--pins-file", help="debugfs pinctrl 'pins' file, '-' for stdin")
    ap.add_argument("--macros", action="store_true", help="list <SOC>_IOPAD macros and PIN_* values")
    ap.add_argument("--mux-mask", type=lambda s: int(s, 0), default=0xF,
                    help="mask of the mux-mode field (default 0xf; confirm in the TRM)")
    args = ap.parse_args()

    layout = Layout(find_header(args.header))
    if args.macros:
        print("# header: " + layout.path)
        print("IOPAD macros: " + " ".join(f for f in layout.funcs if f.endswith("IOPAD")))
        for n, v in sorted(layout.pin_macros.items(), key=lambda kv: (kv[1], kv[0])):
            print("%-28s 0x%08x" % (n, v))
        return 0

    rows = []
    if args.pins_file:
        fh = sys.stdin if args.pins_file == "-" else open(args.pins_file)
        for line in fh:
            m = PINS_RE.match(line)
            if m:
                rows.append(("pin %s %s @%s" % (m.group(1), m.group(2), m.group(4)), int(m.group(5), 16)))
    for v in args.values:
        rows.append(("", parse_value(v)))
    if not rows:
        ap.print_usage(sys.stderr)
        return 2
    for label, value in rows:
        parts, exact = layout.decode(value, args.mux_mask)
        print("%s0x%08x  %s  => %s" % (label + " " if label else "", value, " ".join(parts),
                                       " / ".join(exact) if exact else "no exact PIN_* macro"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
