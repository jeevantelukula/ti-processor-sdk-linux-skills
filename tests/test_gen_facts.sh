#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Manual test for lib/gen-sdk-facts.py. Needs an installed AM62P SDK, so it is NOT run in CI.
#   tests/test_gen_facts.sh /path/to/ti-processor-sdk-linux-am62pxx-evm-<version>
# Checks the AM62P output: exactly three remote cores (MCU R5F, WKUP R5F, HSM M4F), no PRU,
# firmware names present, evidence on every found section. Exit 77 (skip) without an SDK.
set -euo pipefail

sdk=${1:-${TI_SDK_ROOT:-}}
if [[ -z "$sdk" || ! -f "$sdk/Rules.make" ]]; then
  echo "SKIP: pass an AM62P SDK root (or set TI_SDK_ROOT)"; exit 77
fi
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT

python3 "$here/../lib/gen-sdk-facts.py" --sdk-root "$sdk" --out-dir "$out" >/dev/null

python3 - "$out" <<'PY'
import glob, json, sys
files = glob.glob(sys.argv[1] + "/*.json")
assert len(files) == 1, "expected one json, got %r" % files
d = json.load(open(files[0]))
assert glob.glob(sys.argv[1] + "/*.md"), "markdown missing"
S = d["sections"]
if d["meta"]["soc"] != "am62p":
    print("SKIP: SDK SOC is %r, test expects am62p" % d["meta"]["soc"]); sys.exit(77)
assert not d["meta"]["skipped_sections"], "skipped: %r" % d["meta"]["skipped_sections"]
rp = S["remoteprocs"]["data"]
kinds = sorted(r["kind"] for r in rp)
assert kinds == ["HSM M4F", "R5F", "R5F"], kinds
assert not [r for r in rp if "PRU" in r["kind"] or "pru" in r["node"]], "unexpected PRU"
fw = sorted(r["firmware_name"] for r in rp)
assert all(fw), fw
hsm = [r for r in rp if r["kind"] == "HSM M4F"][0]
assert hsm["status"] == "reserved", hsm
assert "wkup" in " ".join(m["node"] for r in rp for m in r["memory_regions"])
assert any(t["cpu_table"] and t["count"] > 0 for t in S["opp"]["data"]), "no CPU OPP table"
assert any(u["macro"].endswith("_IOPAD") for u in S["pinmux"]["data"]["iopad_macros_used"]), "no IOPAD"
for k, s in S.items():
    if s["found"]:
        assert s["evidence"], "section %s has no evidence" % k
print("PASS: %d cores %s" % (len(rp), fw))
PY
