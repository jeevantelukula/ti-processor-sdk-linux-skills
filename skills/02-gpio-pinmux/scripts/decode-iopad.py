#!/usr/bin/env python3
"""Decode a K3 PADCONFIG register value into human-readable fields."""

import sys
import argparse


def decode_padconfig(value: int) -> dict:
    mux_mode      = value & 0x7
    pull_up_dis   = (value >> 16) & 1   # PULLUDDIS: 1=pull disabled
    pull_type_sel = (value >> 17) & 1   # PULLTYPESEL: 1=pull-up, 0=pull-down
    rx_active     = (value >> 18) & 1   # RXACTIVE: 1=input buffer enabled

    pull_state = "disabled" if pull_up_dis else ("pull-up" if pull_type_sel else "pull-down")
    direction  = "input" if rx_active else "output"

    return {
        "raw": f"0x{value:06x}",
        "mux_mode": mux_mode,
        "rx_active": bool(rx_active),
        "direction": direction,
        "pull_up_dis": bool(pull_up_dis),
        "pull_type_sel": bool(pull_type_sel),
        "pull_state": pull_state,
        "dt_macro": _guess_macro(rx_active, pull_up_dis, pull_type_sel),
    }


def _guess_macro(rx_active, pull_up_dis, pull_type_sel) -> str:
    if not rx_active and pull_up_dis:
        return "PIN_OUTPUT"
    elif not rx_active and not pull_up_dis and pull_type_sel:
        return "PIN_OUTPUT_PULLUP"
    elif not rx_active and not pull_up_dis and not pull_type_sel:
        return "PIN_OUTPUT_PULLDOWN"
    elif rx_active and pull_up_dis:
        return "PIN_INPUT"
    elif rx_active and not pull_up_dis and pull_type_sel:
        return "PIN_INPUT_PULLUP"
    elif rx_active and not pull_up_dis and not pull_type_sel:
        return "PIN_INPUT_PULLDOWN"
    return "UNKNOWN"


def main():
    parser = argparse.ArgumentParser(
        description="Decode TI K3 PADCONFIG register value",
        epilog="Example: decode-iopad.py 0x50000 0x40010")
    parser.add_argument("values", nargs="+", help="PADCONFIG value(s) in hex or decimal")
    args = parser.parse_args()

    for raw in args.values:
        try:
            val = int(raw, 0)
        except ValueError:
            print(f"ERROR: cannot parse '{raw}' as a number", file=sys.stderr)
            continue

        d = decode_padconfig(val)
        print(f"\nPADCONFIG value: {d['raw']}")
        print(f"  Mux mode:     {d['mux_mode']}" +
              (" (GPIO)" if d['mux_mode'] == 7 else ""))
        print(f"  Direction:    {d['direction']} (RXACTIVE={int(d['rx_active'])})")
        print(f"  Pull:         {d['pull_state']}"
              f"  (PULLUDDIS={int(d['pull_up_dis'])}, PULLTYPESEL={int(d['pull_type_sel'])})")
        print(f"  DT macro:     {d['dt_macro']}")
        print(f"  DTS snippet:  AM625_IOPAD(0xOFFSET, {d['dt_macro']}, {d['mux_mode']})")


if __name__ == "__main__":
    main()
