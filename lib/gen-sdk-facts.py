#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""gen-sdk-facts.py - generate a per-platform fact sheet from an installed TI Processor SDK.

Everything is derived from the SDK (Rules.make, manifest, board-support, kernel DTS).
Nothing is hardcoded per SoC. Unknown facts are omitted with a 'not found' note.
Needs only python3 stdlib; uses host `cpp` and `dtc` for the device-tree sections
(falls back to the SDK devkit dtc / kernel scripts/dtc/dtc; skipped sections are reported).

Usage: gen-sdk-facts.py [--sdk-root DIR] [--kernel-dir DIR] [--dts FILE]
                        [--out-dir DIR] [--format md,json] [--name NAME]
"""
import argparse, datetime, glob, hashlib, json, os, re, shutil, subprocess, sys

GENERATOR_VERSION = "1.0"

# ----------------------------------------------------------------- helpers

def rel(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path

def sdk_env(*names):
    """Values of TI_* names: from the environment, else from the ti-sdk-env.sh next to this
    script (each skill bundles a copy; shell variables do not persist between agent commands)."""
    vals = {n: os.environ.get(n, "") for n in names}
    lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ti-sdk-env.sh")
    if all(vals.values()) or not os.path.isfile(lib):
        return vals
    script = 'source "$1" >/dev/null 2>&1; shift; for n; do printf "%s\\0" "${!n}"; done'
    r = subprocess.run(["bash", "-c", script, "_", lib, *names], stdout=subprocess.PIPE, universal_newlines=True)
    got = r.stdout.split("\0")
    return {n: vals[n] or (got[i] if i < len(got) else "") for i, n in enumerate(names)}

def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, **kw)

def first_dir(pattern):
    m = sorted(glob.glob(pattern))
    return m[0] if m else None

class Report:
    """Collects sections: {key: {title, found, evidence[], data, note}} and skip notes."""
    def __init__(self):
        self.sections = {}
        self.order = []
        self.skipped = []
    def add(self, key, title, data=None, evidence=None, note=None):
        found = data not in (None, [], {}, "")
        self.sections[key] = {"title": title, "found": found, "data": data,
                              "evidence": evidence or [], "note": note}
        self.order.append(key)
    def skip(self, key, title, reason):
        self.skipped.append({"section": key, "reason": reason})
        self.add(key, title, None, [], "skipped: " + reason)

# ------------------------------------------------------------- Rules.make

RULE_VARS = ["SOC", "PLATFORM", "ARCH", "UBOOT_MACHINE", "UBOOT_MACHINE_R5",
             "UBOOT_MACHINE_ARMV7", "KERNEL_DEVICETREE_PREFIX", "CROSS_COMPILE",
             "CROSS_COMPILE_ARMV7", "MKIMAGE_DTB_FILE", "TI_DM", "SOC_TYPE",
             "YOCTO_MACHINE", "LINUXKERNEL_INSTALL_DIR", "UBOOT_SRC_DIR"]

def eval_rules(root):
    """Same approach as lib/ti-sdk-env.sh: evaluate Rules.make with GNU make."""
    rules = os.path.join(root, "Rules.make")
    if not os.path.isfile(rules):
        return None, "no Rules.make"
    if shutil.which("make"):
        body = "include %s\n.PHONY: __p\n__p:\n" % rules
        body += "".join("\t@printf '%s=%%s\\n' '$(%s)'\n" % (v, v) for v in RULE_VARS)
        r = run(["make", "-s", "--no-print-directory", "-f", "-", "TI_SDK_PATH=" + root, "__p"],
                input=body)
        if r.returncode == 0 and r.stdout.strip():
            out = {}
            for line in r.stdout.splitlines():
                k, _, v = line.partition("=")
                out[k] = v
            return out, "make-evaluated"
    out = {}
    txt = open(rules, errors="replace").read()
    for v in RULE_VARS:
        m = re.search(r"^(?:export\s+)?%s\s*\??=\s*(.*)$" % v, txt, re.M)
        if m:
            out[v] = m.group(1).strip()
    return out, "text-parsed (make unavailable; variables not expanded)"

def grep_line(path, pattern, flags=0):
    """first 'relpath:line' of regex in file, else None"""
    try:
        for i, l in enumerate(open(path, errors="replace"), 1):
            if re.search(pattern, l, flags):
                return i
    except OSError:
        pass
    return None

# --------------------------------------------------------------- manifest

KEY_COMPONENT = re.compile(
    r"^(kernel|u-boot[a-z0-9-]*|atf|trusted-firmware-a[a-z0-9-]*|optee-[a-z-]+|"
    r"k3conf|ti-[a-z0-9-]+|linux-firmware[a-z0-9-]*|[a-z0-9-]*firmware[a-z0-9-]*|"
    r"[a-z0-9-]*remoteproc[a-z0-9-]*|[a-z0-9-]*rpmsg[a-z0-9-]*|[a-z0-9-]*pru[a-z0-9-]*|"
    r"u-boot-tools|dtc|device-tree-compiler)$")

def parse_manifest(root):
    p = os.path.join(root, "manifest", "software_manifest.txt")
    if not os.path.isfile(p):
        return None, p
    rows, seen = [], set()
    for i, l in enumerate(open(p, errors="replace"), 1):
        if not l.startswith("|"):
            continue
        cols = [c.strip() for c in l.split("|")]
        if len(cols) < 4 or not cols[1] or " " in cols[1] or cols[1].lower() == "name":
            continue
        name, ver = cols[1], cols[2]
        if name.startswith(("kernel-module-", "kernel-image", "kernel-vmlinux", "nativesdk-")):
            continue
        if KEY_COMPONENT.match(name) and not re.search(r"(-license|-dev|-dbg|-src)$|^ti-test|^linux-firmware-", name) \
                and (name, ver) not in seen:
            seen.add((name, ver))
            rows.append({"name": name, "version": ver, "line": i})
    return rows, p

# ---------------------------------------------------------- boot-file info

def sec_mode(name):
    m = re.search(r"(?:^|[-_])(hs-fs|hs-se|hs|gp)(?:[-_.]|$)", name)
    return m.group(1) if m else None

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def boot_files(root, platform):
    dirs = [os.path.join(root, "board-support", "built-images")]
    if platform:
        dirs.append(os.path.join(root, "board-support", "prebuilt-images", platform))
    out, ev = [], []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        ev.append(rel(d, root) + "/")
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.isfile(p) and re.match(
                    r"(tiboot3|tispl|u-boot|sysfw|ti-fs|bl31|bl32|MLO|fitImage|Image|uEnv|boot)", n) \
                    and "--" not in n:
                out.append({"dir": rel(d, root), "file": n, "size": os.path.getsize(p),
                            "security_mode_in_name": sec_mode(n), "_p": p})
        sf = os.path.join(d, "ti-sysfw")
        if os.path.isdir(sf):
            for n in sorted(os.listdir(sf)):
                out.append({"dir": rel(sf, root), "file": n, "size": os.path.getsize(os.path.join(sf, n)),
                            "security_mode_in_name": sec_mode(n), "_p": os.path.join(sf, n)})
    # identify unlabeled tiboot3.bin by content hash against labeled variants
    for f in out:
        if f["file"] in ("tiboot3.bin",):
            h = sha(f["_p"])
            same = [g["file"] for g in out if g is not f and g["dir"] == f["dir"]
                    and g["file"].startswith("tiboot3") and sha(g["_p"]) == h]
            if same:
                f["identical_to"] = same
    for f in out:
        f.pop("_p", None)
    return out, ev

# ------------------------------------------------------------ DT tooling

def find_tool(name, root, kernel):
    cands = []
    if root:
        cands += glob.glob(os.path.join(root, "*devkit", "sysroots", "x86_64-*", "usr", "bin", name))
        cands += glob.glob(os.path.join(root, "*devkit", "sysroots", "x86_64-*", "usr", "bin", "*", name))
    if kernel and name == "dtc":
        cands.append(os.path.join(kernel, "scripts", "dtc", "dtc"))
    # Host as last resort (only if SDK has no dtc)
    p = shutil.which(name)
    if p:
        cands.append(p)
    for c in cands:
        if os.access(c, os.X_OK):
            return c
    return None

def find_kernel(root):
    return first_dir(os.path.join(root, "board-support", "ti-linux-kernel*")) if root else None

def kernel_from_dts(dts):
    d = os.path.dirname(os.path.abspath(dts))
    while d != "/":
        if os.path.isdir(os.path.join(d, "include", "dt-bindings")) and \
           os.path.isdir(os.path.join(d, "arch")):
            return d
        d = os.path.dirname(d)
    return None

def dts_search_roots(kernel, arch):
    amap = {"aarch64": "arm64", "arm64": "arm64", "arm": "arm"}
    pref = amap.get(arch or "", None)
    roots = sorted(glob.glob(os.path.join(kernel, "arch", "*", "boot", "dts")))
    roots.sort(key=lambda r: 0 if pref and ("/arch/%s/" % pref) in r else 1)
    return roots

def candidate_stems(root, platform, prefixes):
    """DTB stems the SDK ships (built-images/dtb, prebuilt-images/<platform>), filtered by prefix."""
    names = set()
    dirs = glob.glob(os.path.join(root, "board-support", "built-images", "dtb", "**"), recursive=True)
    dirs = [d for d in dirs if os.path.isdir(d)] + [os.path.join(root, "board-support", "built-images", "dtb")]
    if platform:
        dirs.append(os.path.join(root, "board-support", "prebuilt-images", platform))
    for d in dirs:
        for f in glob.glob(os.path.join(d, "*.dtb")):
            n = os.path.basename(f)[:-4]
            if "--" in n:
                continue
            if platform and n.endswith("-" + platform):
                n = n[:-len(platform) - 1]
            names.add(n)
    out = []
    for n in sorted(names):
        for i, p in enumerate(prefixes):
            if n.startswith(os.path.basename(p)):
                out.append((i, n))
                break
    return out

def select_dts(root, kernel, rules, args):
    """Returns (dts_path, rule_text, evidence)"""
    if args.dts:
        return os.path.abspath(args.dts), "--dts override", []
    if not (root and kernel):
        return None, "no SDK/kernel to select from", []
    platform = rules.get("PLATFORM", "")
    prefixes = [p for p in rules.get("KERNEL_DEVICETREE_PREFIX", "").split("|") if p]
    cands = candidate_stems(root, platform, prefixes)
    ev = ["Rules.make: KERNEL_DEVICETREE_PREFIX=%s" % rules.get("KERNEL_DEVICETREE_PREFIX", "")]

    def locate(stem):
        for r in dts_search_roots(kernel, rules.get("ARCH")):
            hits = sorted(glob.glob(os.path.join(r, "**", stem + ".dts"), recursive=True))
            if hits:
                return hits[0]
        return None

    mk = os.path.basename(rules.get("MKIMAGE_DTB_FILE", ""))
    order = []
    if mk.endswith(".dtb"):
        order.append(("Rules.make MKIMAGE_DTB_FILE (%s)" % mk, mk[:-4]))
    if platform:
        order.append(("stem equals PLATFORM", platform))
    for i, p in enumerate(prefixes):
        order.append(("stem equals KERNEL_DEVICETREE_PREFIX alternative '%s'" % p, os.path.basename(p)))
    for why, stem in order:
        d = locate(stem)
        if d:
            return d, "first match of: MKIMAGE_DTB_FILE, PLATFORM, prefix alternatives; used: " + why, ev
    # fallback: shortest shipped DTB stem under first matching prefix
    for i, n in sorted(cands, key=lambda t: (t[0], len(t[1]), t[1])):
        d = locate(n)
        if d:
            return d, "shortest shipped DTB name under the first KERNEL_DEVICETREE_PREFIX alternative with a .dts", ev
    return None, "no DTS found for prefixes %r" % prefixes, ev

def preprocess(cpp, dts, kernel):
    d = os.path.dirname(dts)
    incs = []
    cur = d
    while True:
        incs.append(cur)
        if re.search(r"/boot/dts$", cur) or cur in ("/", ""):
            break
        cur = os.path.dirname(cur)
    if kernel:
        incs += [os.path.join(kernel, "include"), os.path.join(kernel, "scripts", "dtc", "include-prefixes")]
    cmd = [cpp, "-nostdinc", "-undef", "-D__DTS__", "-x", "assembler-with-cpp"]
    for i in incs:
        cmd += ["-I", i]
    cmd.append(dts)
    r = run(cmd, cwd=d)
    if r.returncode != 0:
        return None, "cpp failed: " + r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "cpp failed", []
    # include closure from linemarkers
    closure, seen = [], set()
    for m in re.finditer(r'^# \d+ "([^"]+)"', r.stdout, re.M):
        p = m.group(1)
        if p.startswith("<") or not p.endswith((".dts", ".dtsi", ".dtso")):
            continue
        a = p if os.path.isabs(p) else os.path.normpath(os.path.join(d, p))
        if a not in seen and os.path.isfile(a):
            seen.add(a)
            closure.append(a)
    if dts not in seen:
        closure.insert(0, dts)
    return r.stdout, None, closure

def compile_dts(dtc, pp):
    r = run([dtc, "-q", "-I", "dts", "-O", "dts"], input=pp)
    if r.returncode != 0 or not r.stdout.strip():
        err = r.stderr.strip().splitlines()
        return None, "dtc failed: " + (err[-1] if err else "no output")
    return r.stdout, None

# ---------------------------------------------------------- DTS parsing

class Node:
    def __init__(self, name, labels, parent):
        self.name, self.labels, self.parent = name, labels, parent
        self.props, self.children = {}, []
    @property
    def path(self):
        if self.parent is None:
            return "/"
        pp = self.parent.path
        return (pp if pp != "/" else "") + "/" + self.name
    @property
    def unit(self):
        return self.name.split("@", 1)[1] if "@" in self.name else None
    def strings(self, p):
        v = self.props.get(p)
        return [x[1] for x in v if x[0] == "s"] if v else []
    def cells(self, p):
        v = self.props.get(p)
        if not v:
            return []
        out = []
        for x in v:
            if x[0] == "c":
                out.extend(x[2])
        return out
    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

def _parse_value(s):
    items = []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"|(?:/bits/\s*(\d+)\s*)?<([^>]*)>|\[([^\]]*)\]', s):
        if m.group(1) is not None:
            items.append(("s", m.group(1)))
        elif m.group(3) is not None:
            vals = []
            for t in m.group(3).split():
                try:
                    vals.append(int(t, 0))
                except ValueError:
                    vals.append(t)
            items.append(("c", int(m.group(2) or 32), vals))
        else:
            items.append(("b", m.group(4)))
    return items

def parse_dts(text):
    root = Node("", [], None)
    cur, i, n = root, 0, len(text)
    first_open = True
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if text.startswith("/*", i):
            i = text.find("*/", i) + 2
            continue
        if text.startswith("//", i):
            i = text.find("\n", i)
            i = n if i < 0 else i
            continue
        if c == "}":
            cur = cur.parent or cur
            i = text.find(";", i) + 1
            continue
        j, q, depth = i, False, 0
        while j < n:
            ch = text[j]
            if q:
                if ch == "\\":
                    j += 1
                elif ch == '"':
                    q = False
            elif ch == '"':
                q = True
            elif ch in "<[":
                depth += 1
            elif ch in ">]":
                depth -= 1
            elif depth <= 0 and ch in ";{":
                break
            j += 1
        stmt = text[i:j].strip()
        term = text[j] if j < n else ";"
        i = j + 1
        if term == "{":
            if stmt == "/":
                if first_open:
                    cur, first_open = root, False
                    continue
                cur = root
                continue
            parts = stmt.replace(":", ": ").split()
            labels = [p[:-1] for p in parts if p.endswith(":")]
            name = [p for p in parts if not p.endswith(":")][-1]
            nd = Node(name, labels, cur)
            cur.children.append(nd)
            cur = nd
        else:
            if stmt.startswith("/") and stmt.endswith("/"):
                continue
            if stmt.startswith("/dts-v1/") or stmt.startswith("/plugin/"):
                continue
            k, _, v = stmt.partition("=")
            cur.props[k.strip()] = _parse_value(v) if v.strip() else [("e",)]
    return root

# ------------------------------------------------------ DT fact extraction

CORE_COMPAT = re.compile(
    r"(r5f|m4f|m4fss|hsm-m4fss|pruss|icssg(?!-prueth)|icssm(?!-prueth)|[,-]pru$|[,-]rtu$|[,-]txpru$|"
    r"c7x|c71|c66|c66x|dsp|rproc|remoteproc)")
# nodes WITHOUT firmware-name are listed only if they look like a core/subsystem, not a PRU sub-block
CORE_NOFW = re.compile(r"(r5f|m4f|m4fss|c7x|c71|c66x?|dsp|rproc|remoteproc|pruss|icssg|icssm)$")
CORE_KIND = [("r5f", "R5F"), ("hsm", "HSM M4F"), ("m4f", "M4F"), ("c7x", "C7x DSP"), ("c71", "C7x DSP"),
             ("c66", "C66x DSP"), ("dsp", "DSP"), ("rtu", "PRU/RTU"), ("pru", "PRU/ICSS")]

def kind_of(compats, name):
    if any("prueth" in c for c in compats):
        return "PRU Ethernet firmware user (not a core)"
    s = " ".join(compats) + " " + name
    for k, v in CORE_KIND:
        if k in s:
            return v
    return "remote processor"

def fmt_hz(v):
    return "%d" % v

def reg_decode(node, vals):
    par = node.parent
    ac = (par.cells("#address-cells") or [2])[0] if par else 2
    sc = (par.cells("#size-cells") or [1])[0] if par else 1
    out, step = [], ac + sc
    for k in range(0, len(vals) - step + 1, step):
        a = 0
        for x in vals[k:k + ac]:
            a = (a << 32) | x
        s = 0
        for x in vals[k + ac:k + step]:
            s = (s << 32) | x
        out.append({"addr": "0x%x" % a, "size": "0x%x" % s})
    return out

def extract_dt(root, src_find):
    """root: parsed tree. src_find(regex)->'relpath:line' or None. Returns dict of sections."""
    nodes = list(root.walk())
    ph = {}
    for n in nodes:
        v = n.cells("phandle")
        if v:
            ph[v[0]] = n
    res = {}
    # --- identity
    res["model"] = (root.strings("model") or [None])[0]
    res["compatible"] = root.strings("compatible")
    # --- cpus
    cpus = [n for n in nodes if n.parent and n.parent.name == "cpus" and n.name.startswith("cpu@")]
    res["cpus"] = [{"node": n.name, "compatible": n.strings("compatible"),
                    "opp_table": (ph[n.cells("operating-points-v2")[0]].path
                                  if n.cells("operating-points-v2") and n.cells("operating-points-v2")[0] in ph else None)}
                   for n in cpus]
    # --- remote processors
    rprocs = []
    for n in nodes:
        comp = n.strings("compatible")
        has_fw = "firmware-name" in n.props
        if not (has_fw or any(CORE_NOFW.search(c) for c in comp)):
            continue
        if n.parent is None:
            continue
        if not has_fw and any("firmware-name" in d.props for d in n.walk() if d is not n):
            continue  # cluster container; its core children are listed instead
        status = (n.strings("status") or ["okay"])[0]
        regions = []
        for h in n.cells("memory-region"):
            r = ph.get(h)
            if r is not None:
                rr = reg_decode(r, r.cells("reg"))
                regions.append({"node": (r.labels or [r.name])[0], "reg": rr[0] if rr else None})
        bootph = sorted(k for k in n.props if k.startswith("bootph"))
        fw = (n.strings("firmware-name") or [None])[0]
        e = []
        if fw:
            s = src_find(r'firmware-name\s*=\s*"%s"' % re.escape(fw))
            e = [s] if s else []
        rprocs.append({"kind": kind_of(comp, n.name), "node": n.path, "label": (n.labels or [None])[0],
                       "compatible": comp, "status": status, "firmware_name": fw,
                       "memory_regions": regions, "bootph": bootph,
                       "reserved": status == "reserved",
                       "evidence": e})
    res["remoteprocs"] = rprocs
    # --- reserved memory
    rm = [n for n in nodes if n.name == "reserved-memory"]
    regs = []
    for r in rm:
        for c in r.children:
            rr = reg_decode(c, c.cells("reg"))  # cells come from c.parent (= r)
            if not rr and c.cells("size"):
                rr = [{"addr": "dynamic (alloc-ranges)", "size": "0x%x" % c.cells("size")[-1]}]
            s = None
            if c.labels:
                s = src_find(r'\b%s\s*:' % re.escape(c.labels[0]))
            regs.append({"label": (c.labels or [None])[0], "node": c.name,
                         "compatible": c.strings("compatible"), "reg": rr,
                         "no_map": "no-map" in c.props, "evidence": [s] if s else []})
    res["reserved_memory"] = regs
    # --- OPP tables
    cons = {}
    for n in nodes:
        for h in n.cells("operating-points-v2"):
            if h in ph:
                cons.setdefault(ph[h].path, []).append(n.path)
    opps = []
    for n in nodes:
        comp = n.strings("compatible")
        if not any(c.startswith("operating-points-v2") for c in comp):
            continue
        ent = []
        for c in n.children:
            hz = c.cells("opp-hz")
            v = None
            if hz:
                v = hz[0] if len(hz) == 1 else (hz[0] << 32) | hz[1]
            ent.append({"node": c.name, "opp_hz": v,
                        "supported_hw": ["0x%x" % x for x in c.cells("opp-supported-hw")] or None,
                        "turbo": "turbo-mode" in c.props,
                        "microvolt": c.cells("opp-microvolt") or None})
        s = src_find(r'\b%s\s*:' % re.escape(n.labels[0])) if n.labels else \
            src_find(r'compatible\s*=\s*"%s"' % re.escape(comp[0]))
        users = cons.get(n.path, [])
        opps.append({"node": n.path, "label": (n.labels or [None])[0], "compatible": comp,
                     "count": len(ent), "opps": ent, "consumers": users,
                     "cpu_table": any("/cpus/" in u for u in users),
                     "evidence": [s] if s else []})
    res["opp_tables"] = opps
    # --- pinctrl
    pins = []
    for n in nodes:
        if any("pinctrl-single" in c or "padconf" in c for c in n.strings("compatible")) or \
           (n.strings("compatible") and any(c.endswith("pinctrl") for c in n.strings("compatible"))):
            if n.unit:
                regv = reg_decode(n, n.cells("reg"))
                pins.append({"node": n.path, "label": (n.labels or [None])[0],
                             "compatible": n.strings("compatible"), "reg": regv})
    res["pinctrl_nodes"] = pins
    # --- gpio
    gp = []
    for n in nodes:
        comp = n.strings("compatible")
        if comp and any(re.search(r"gpio", c) and (c.startswith("ti,") or "davinci" in c) for c in comp) \
                and "gpio-controller" in n.props:
            regv = reg_decode(n, n.cells("reg"))
            gp.append({"node": n.path, "label": (n.labels or [None])[0], "compatible": comp,
                       "unit_address": n.unit, "reg": regv,
                       "status": (n.strings("status") or ["okay"])[0],
                       "ngpios": (n.cells("ti,ngpio") or [None])[0]})
    res["gpio"] = gp
    return res

# ----------------------------------------------------------- pinctrl headers

def iopad_macros(kernel):
    out = []
    pats = [os.path.join(kernel, "include", "dt-bindings", "pinctrl", "k3*.h"),
            os.path.join(kernel, "arch", "*", "boot", "dts", "ti", "k3-pinctrl.h"),
            os.path.join(kernel, "arch", "*", "boot", "dts", "ti", "*", "k3-pinctrl.h")]
    for pat in pats:
        for f in sorted(glob.glob(pat)):
            for i, l in enumerate(open(f, errors="replace"), 1):
                m = re.match(r"#define\s+([A-Z0-9_]+_IOPAD)\s*\(", l)
                if m:
                    out.append({"macro": m.group(1), "file": rel(f, kernel), "line": i})
    return out

def iopad_usage(closure, kernel):
    use = {}
    for f in closure:
        if not f.endswith((".dts", ".dtsi")):
            continue
        for i, l in enumerate(open(f, errors="replace"), 1):
            for m in re.finditer(r"\b([A-Z0-9_]+_IOPAD)\s*\(", l):
                u = use.setdefault(m.group(1), {"macro": m.group(1), "uses": 0, "first": "%s:%d" % (rel(f, kernel), i)})
                u["uses"] += 1
    return sorted(use.values(), key=lambda x: -x["uses"])

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sdk-root", help="SDK root (default: TI_SDK_ROOT, else found by ./ti-sdk-env.sh)")
    ap.add_argument("--kernel-dir")
    ap.add_argument("--dts", help="override board DTS (testing against a kernel tree)")
    ap.add_argument("--out-dir")
    ap.add_argument("--format", default="md,json")
    ap.add_argument("--name", help="output file stem (default: PLATFORM)")
    args = ap.parse_args()
    env = sdk_env("TI_SDK_ROOT", "TI_FACTS_DIR") if not (args.sdk_root and args.out_dir) else {}
    args.sdk_root = args.sdk_root or env.get("TI_SDK_ROOT") or None

    root = os.path.abspath(args.sdk_root) if args.sdk_root else None
    if root and not os.path.isfile(os.path.join(root, "Rules.make")):
        print("gen-sdk-facts: %s has no Rules.make; not an SDK root" % root, file=sys.stderr)
        if not (args.kernel_dir or args.dts):
            return 1
        root = None
    rep = Report()
    rules, rules_how = ({}, "no SDK root")
    if root:
        rules, rules_how = eval_rules(root)
        rules = rules or {}
    kernel = os.path.abspath(args.kernel_dir) if args.kernel_dir else \
        (find_kernel(root) or (kernel_from_dts(args.dts) if args.dts else None))
    platform = rules.get("PLATFORM") or ""
    name = args.name or platform
    if not name and args.dts:
        name = os.path.basename(args.dts).rsplit(".", 1)[0]
    name = name or "unknown-platform"

    # output dir
    out_dir = args.out_dir or env.get("TI_FACTS_DIR")
    if not out_dir:
        ws = os.getcwd()
        out_dir = os.path.join(ws, ".claude", "target-platform") \
            if os.path.isdir(os.path.join(ws, ".claude")) else os.path.join(ws, "target-platform")

    # ---- SDK / Rules.make
    sdk_ver = None
    if root:
        m = re.search(r"-(\d+(?:[._]\d+){2,4})$", os.path.basename(root))
        sdk_ver = m.group(1).replace("_", ".") if m else None
    rv = {k: rules.get(k) for k in RULE_VARS if rules.get(k)}
    rep.add("rules", "Build configuration (Rules.make)", rv or None,
            ["%s/Rules.make (%s)" % (root, rules_how)] if root else [],
            None if rv else "not found: no SDK root / Rules.make")

    # ---- component versions
    if root:
        rows, mp = parse_manifest(root)
        bs = []
        for d in sorted(glob.glob(os.path.join(root, "board-support", "*"))):
            b = os.path.basename(d)
            m = re.match(r"(.*?)-(\d.*)$", b)
            if os.path.isdir(d):
                bs.append({"component": m.group(1) if m else b, "version": m.group(2) if m else None,
                           "dir": "board-support/" + b})
        rep.add("components", "Component versions",
                {"board_support_dirs": bs, "manifest": rows} if (bs or rows) else None,
                ["board-support/ directory names"] + ([rel(mp, root)] if rows is not None else []),
                None if rows is not None else "manifest/software_manifest.txt not found; versions from directory names only")
        bf, ev = boot_files(root, platform)
        rep.add("boot_files", "Boot files (built-images, prebuilt-images)", bf or None, ev,
                None if bf else "not found: no built-images/ or prebuilt-images/<PLATFORM>/ boot files")
    else:
        rep.add("components", "Component versions", None, [], "not found: no SDK root")
        rep.add("boot_files", "Boot files", None, [], "not found: no SDK root")

    # ---- device tree
    dts_path, rule_txt, sel_ev = select_dts(root, kernel, rules, args)
    dtinfo, closure = None, []
    src_cache = {}
    def src_find(pat):
        for f in closure:
            if f not in src_cache:
                src_cache[f] = open(f, errors="replace").read().splitlines()
            for i, l in enumerate(src_cache[f], 1):
                if re.search(pat, l):
                    return "%s:%d" % (rel(f, kernel or os.getcwd()), i)
        return None

    dt_keys = [("dt_identity", "Board device tree"), ("remoteprocs", "Remote processors"),
               ("reserved_memory", "Reserved memory"), ("opp", "CPU/device OPP tables"),
               ("pinmux", "Pinmux"), ("gpio", "GPIO controllers")]
    why = None
    if not dts_path:
        why = "board DTS not found (%s)" % rule_txt
    elif not os.path.isfile(dts_path):
        why = "DTS file %s does not exist" % dts_path
    else:
        cpp = find_tool("cpp", root, kernel)
        dtc = find_tool("dtc", root, kernel)
        if not cpp:
            why = "host cpp not found (install gcc/cpp)"
        elif not dtc:
            why = "dtc not found on host, in SDK devkit sysroot, or kernel scripts/dtc"
        else:
            pp, err, closure = preprocess(cpp, dts_path, kernel)
            if err:
                why = err
            else:
                txt, err = compile_dts(dtc, pp)
                if err:
                    why = err
                else:
                    try:
                        dtinfo = extract_dt(parse_dts(txt), src_find)
                    except Exception as e:  # never crash on odd trees
                        why = "DTS parse error: %r" % e
    base = rel(kernel, root) if (kernel and root) else (kernel or "")
    dts_rel = rel(dts_path, kernel) if (dts_path and kernel) else dts_path
    if dtinfo is None:
        for k, t in dt_keys:
            rep.skip(k, t, why)
    else:
        rep.add("dt_identity", "Board device tree",
                {"dts": dts_rel, "selection_rule": rule_txt, "model": dtinfo["model"],
                 "compatible": dtinfo["compatible"], "cpus": dtinfo["cpus"],
                 "include_closure": [rel(f, kernel or os.path.dirname(dts_path)) for f in closure
                                     if not (kernel and f.startswith(kernel + "/include/"))]},
                sel_ev + [dts_rel], None)
        rp = dtinfo["remoteprocs"]
        rep.add("remoteprocs", "Remote processors (nodes with firmware-name or core-like compatible)",
                rp or None, sorted({e for r in rp for e in r["evidence"]}) or [dts_rel],
                None if rp else "not found: no remoteproc-like nodes in the DTS")
        rm = dtinfo["reserved_memory"]
        rep.add("reserved_memory", "Reserved memory", rm or None,
                sorted({e for r in rm for e in r["evidence"]}) or [dts_rel],
                None if rm else "not found: no /reserved-memory children")
        op = dtinfo["opp_tables"]
        rep.add("opp", "Operating points (compatible operating-points-v2*)", op or None,
                sorted({e for r in op for e in r["evidence"]}) or [dts_rel],
                None if op else "not found: no operating-points-v2 tables")
        # pinmux
        pm = {}
        if kernel:
            defs = iopad_macros(kernel)
            used = iopad_usage(closure, kernel)
            pm = {"iopad_macros_used": used, "iopad_macros_defined_in_headers": defs,
                  "pinctrl_nodes": dtinfo["pinctrl_nodes"]}
            ev = sorted({"%s:%d" % (d["file"], d["line"]) for d in defs if d["macro"] in {u["macro"] for u in used}})
            ev += [u["first"] for u in used]
        else:
            ev = [dts_rel]
        rep.add("pinmux", "Pinmux (IOPAD macros used by this board DTS, pinctrl nodes)",
                pm if (pm.get("iopad_macros_used") or pm.get("pinctrl_nodes")) else None, ev,
                None if pm.get("iopad_macros_used") or pm.get("pinctrl_nodes") else "not found: no *_IOPAD macros or pinctrl-single nodes")
        gp = dtinfo["gpio"]
        rep.add("gpio", "GPIO controllers", gp or None, [dts_rel],
                None if gp else "not found: no ti,*gpio / davinci-gpio controllers")

    # ---- overlays
    ovl = None
    if dts_path and os.path.isfile(dts_path):
        stem = os.path.basename(dts_path)[:-4]
        d = os.path.dirname(dts_path)
        ovl = sorted(os.path.basename(f) for f in glob.glob(os.path.join(d, stem + "-*.dtso")))
    rep.add("overlays", "Overlay sources (*.dtso whose name starts with the board DTS stem)",
            ovl or None, [rel(os.path.dirname(dts_path), kernel or "/") + "/"] if ovl else [],
            None if ovl else "not found: no %s-*.dtso" % (os.path.basename(dts_path)[:-4] if dts_path else "<board>"))

    # ---- respart out, bin, Makefile targets
    if root:
        ro = sorted(os.listdir(os.path.join(root, "board-support", "k3-respart-tool", "out"))) \
            if os.path.isdir(os.path.join(root, "board-support", "k3-respart-tool", "out")) else None
        rep.add("respart", "k3-respart-tool out/ files", ro, ["board-support/k3-respart-tool/out/"] if ro else [],
                None if ro else "not found: board-support/k3-respart-tool/out/")
        bn = sorted(os.listdir(os.path.join(root, "bin"))) if os.path.isdir(os.path.join(root, "bin")) else None
        rep.add("bin", "SDK bin/ helper scripts", bn, ["bin/"] if bn else [], None if bn else "not found: bin/")
        tg = {}
        mk_files = [os.path.join(root, "Makefile")] + sorted(glob.glob(os.path.join(root, "makerules", "Makefile_*")))
        for f in mk_files:
            if not os.path.isfile(f):
                continue
            for i, l in enumerate(open(f, errors="replace"), 1):
                m = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", l)
                if m and not m.group(1).startswith("."):
                    t = re.sub(r"_(stage|install|clean|dtbs)$", "", m.group(1))
                    tg.setdefault(t, "%s:%d" % (rel(f, root), i))
        rep.add("make_targets", "Top-level make targets (base names; _stage/_install/_clean variants exist where defined)",
                [{"target": k, "evidence": v} for k, v in sorted(tg.items())] or None,
                ["Makefile", "makerules/Makefile_*"] if tg else [], None if tg else "not found: no Makefile targets")
    else:
        for k, t in (("respart", "k3-respart-tool out/ files"), ("bin", "SDK bin/ helper scripts"),
                     ("make_targets", "Top-level make targets")):
            rep.add(k, t, None, [], "not found: no SDK root")

    # ---------------------------------------------------------- output
    meta = {"generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "generator": "gen-sdk-facts.py " + GENERATOR_VERSION,
            "sdk_root": root, "sdk_version": sdk_ver, "platform": platform or None, "soc": rules.get("SOC"),
            "kernel_dir": kernel, "dts": dts_path, "dtc": (find_tool("dtc", root, kernel) if dts_path else None),
            "skipped_sections": rep.skipped}
    doc = {"meta": meta, "sections": {k: rep.sections[k] for k in rep.order}}
    os.makedirs(out_dir, exist_ok=True)
    fmts = [f.strip() for f in args.format.split(",") if f.strip()]
    written = []
    if "json" in fmts:
        p = os.path.join(out_dir, name + ".json")
        with open(p, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
        written.append(p)
    if "md" in fmts:
        p = os.path.join(out_dir, name + ".md")
        with open(p, "w") as f:
            f.write(render_md(doc, name))
        written.append(p)
    for p in written:
        print("gen-sdk-facts: wrote " + p)
    if rep.skipped:
        print("gen-sdk-facts: skipped sections: " + ", ".join(
            "%s (%s)" % (s["section"], s["reason"]) for s in rep.skipped[:1]) +
            (" (+%d more, same reason)" % (len(rep.skipped) - 1) if len(rep.skipped) > 1 else ""),
            file=sys.stderr)
    return 0

# ------------------------------------------------------------ rendering

def hx(v):
    return "0x%x" % v if isinstance(v, int) else str(v)

def render_md(doc, name):
    m, S = doc["meta"], doc["sections"]
    L = []
    w = L.append
    w("# Target platform facts: %s" % name)
    w("")
    w("> GENERATED FILE - do not edit; regenerate with `python3 lib/gen-sdk-facts.py` (skill `ti-generate-kb`).")
    w("")
    w("- Generated: %s" % m["generated"])
    w("- Generator: %s" % m["generator"])
    w("- SDK: %s (version %s)" % (m["sdk_root"] or "not found", m["sdk_version"] or "not found"))
    w("- Kernel tree: %s" % (m["kernel_dir"] or "not found"))
    if m["skipped_sections"]:
        w("- Skipped sections: %s" % ", ".join(s["section"] for s in m["skipped_sections"]))
    w("")
    w("Every section lists its evidence. Missing facts are marked 'not found'; nothing is guessed.")

    def head(k):
        s = S[k]
        w("")
        w("## " + s["title"])
        if s["note"]:
            w("")
            w("Note: " + s["note"])
        return s

    def evid(s):
        if s["evidence"]:
            w("")
            w("Evidence: " + "; ".join("`%s`" % e for e in s["evidence"][:12]) +
              (" ..." if len(s["evidence"]) > 12 else ""))

    s = head("rules")
    if s["data"]:
        w("")
        w("| Variable | Value |")
        w("|---|---|")
        for k, v in s["data"].items():
            w("| %s | `%s` |" % (k, v))
    evid(s)

    s = head("components")
    if s["data"]:
        w("")
        w("| Component | Version | Source |")
        w("|---|---|---|")
        for b in s["data"]["board_support_dirs"]:
            w("| %s | %s | `%s` |" % (b["component"], b["version"] or "-", b["dir"]))
        for r in s["data"]["manifest"] or []:
            w("| %s | %s | manifest line %d |" % (r["name"], r["version"], r["line"]))
    evid(s)

    s = head("boot_files")
    if s["data"]:
        w("")
        w("| Dir | File | Size | Security mode in name | Notes |")
        w("|---|---|---|---|---|")
        for f in s["data"]:
            w("| `%s` | `%s` | %d | %s | %s |" % (f["dir"], f["file"], f["size"],
              f["security_mode_in_name"] or "-", ("byte-identical to " + ", ".join(f["identical_to"])) if f.get("identical_to") else ""))
    evid(s)

    s = head("dt_identity")
    if s["data"]:
        d = s["data"]
        w("")
        w("- Board DTS: `%s`" % d["dts"])
        w("- Selection rule: %s" % d["selection_rule"])
        w("- model: %s" % (d["model"] or "not found"))
        w("- compatible: %s" % (", ".join(d["compatible"]) or "not found"))
        cp = d["cpus"]
        if cp:
            w("- CPUs: %d x %s" % (len(cp), ", ".join(sorted({c for x in cp for c in x["compatible"][:1]}))))
        else:
            w("- CPUs: not found")
    evid(s)

    s = head("remoteprocs")
    if s["data"]:
        w("")
        w("| Kind | Node | Compatible | Status | firmware-name | Memory regions | bootph | Reserved |")
        w("|---|---|---|---|---|---|---|---|")
        for r in s["data"]:
            mr = "; ".join("%s@%s" % (x["node"], x["reg"]["addr"] if x["reg"] else "?") for x in r["memory_regions"]) or "-"
            w("| %s | `%s` | %s | %s | %s | %s | %s | %s |" % (
                r["kind"], r["node"], ", ".join(r["compatible"]) or "-", r["status"],
                "`%s`" % r["firmware_name"] if r["firmware_name"] else "-", mr,
                ", ".join(r["bootph"]) or "-", "yes" if r["reserved"] else "no"))
        w("")
        w("Whether a core is boot-loaded (for example the device-manager core) is not encoded in the DTS: "
          "check the boot files above and the docs.")
    evid(s)

    s = head("reserved_memory")
    if s["data"]:
        w("")
        w("| Label | Node | Address | Size | no-map |")
        w("|---|---|---|---|---|")
        for r in s["data"]:
            rg = r["reg"][0] if r["reg"] else {"addr": "?", "size": "?"}
            w("| %s | `%s` | %s | %s | %s |" % (r["label"] or "-", r["node"], rg["addr"], rg["size"], "yes" if r["no_map"] else "no"))
    evid(s)

    s = head("opp")
    if s["data"]:
        for t in s["data"]:
            w("")
            w("### `%s` (%s) - %d OPPs%s" % (t["node"], ", ".join(t["compatible"]), t["count"],
                                           ", used by CPUs" if t["cpu_table"] else
                                           (", consumers: " + ", ".join(t["consumers"][:3])) if t["consumers"] else ""))
            w("")
            w("| Node | opp-hz | opp-supported-hw | turbo |")
            w("|---|---|---|---|")
            for o in t["opps"]:
                w("| %s | %s | %s | %s |" % (o["node"], o["opp_hz"] if o["opp_hz"] is not None else "-",
                                             " ".join(o["supported_hw"]) if o["supported_hw"] else "-", "yes" if o["turbo"] else "no"))
    evid(s)

    s = head("pinmux")
    if s["data"]:
        d = s["data"]
        used = d["iopad_macros_used"]
        w("")
        w("IOPAD macros used by this board DTS: " + (", ".join("`%s` (%d uses, first `%s`)" % (u["macro"], u["uses"], u["first"]) for u in used) or "not found"))
        defd = {x["macro"]: x for x in d["iopad_macros_defined_in_headers"]}
        for u in used:
            if u["macro"] in defd:
                w("- `%s` defined at `%s:%d`" % (u["macro"], defd[u["macro"]]["file"], defd[u["macro"]]["line"]))
        w("")
        w("Pinctrl nodes: " + ("" if d["pinctrl_nodes"] else "not found"))
        for p in d["pinctrl_nodes"]:
            w("- `%s` reg %s" % (p["node"], ", ".join("%s (+%s)" % (x["addr"], x["size"]) for x in p["reg"]) or "-"))
    evid(s)

    s = head("gpio")
    if s["data"]:
        w("")
        w("| Node | Label | Compatible | Status | Address |")
        w("|---|---|---|---|---|")
        for g in s["data"]:
            w("| `%s` | %s | %s | %s | %s |" % (g["node"], g["label"] or "-", ", ".join(g["compatible"]), g["status"], g["unit_address"] or "-"))
    evid(s)

    s = head("overlays")
    if s["data"]:
        w("")
        for o in s["data"]:
            w("- `%s`" % o)
    evid(s)

    for k in ("respart", "bin"):
        s = head(k)
        if s["data"]:
            w("")
            w(", ".join("`%s`" % x for x in s["data"]))
        evid(s)

    s = head("make_targets")
    if s["data"]:
        w("")
        w(", ".join("`%s`" % t["target"] for t in s["data"]))
    evid(s)
    w("")
    return "\n".join(L)

if __name__ == "__main__":
    sys.exit(main())
