#!/usr/bin/env python3
import ast
import csv
import os
import sys
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "all_csv_to_plot_anonym.py")

TOL_4G_US = 500_000       # 0.5 s  nearest-timestamp tolerance, identity <-> GUTI
TOL_5G_US = 2_000_000     # 2 s

def load_experiments(config_path):
    """Evaluate the EXPERIMENTS dict from all_csv_to_plot_anonym.py.

    The dict is not a pure literal (it uses Path(...) and OP_* constants), so we
    replay the module's top-level simple assignments in order inside a minimal
    namespace (Path, os, __file__) until EXPERIMENTS is defined. Any assignment
    that references symbols we do not provide (e.g. matplotlib objects) is simply
    skipped -- none of those feed EXPERIMENTS.
    """
    with open(config_path) as f:
        tree = ast.parse(f.read(), filename=config_path)
    ns = {"Path": Path, "os": os, "__file__": os.path.abspath(config_path)}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not targets:
            continue
        try:
            value = eval(compile(ast.Expression(node.value), config_path, "eval"), ns)
        except Exception:
            continue
        for t in targets:
            ns[t] = value
        if "EXPERIMENTS" in targets:
            return ns["EXPERIMENTS"]
    sys.exit(f"Could not evaluate EXPERIMENTS in {config_path}")

def read_rows(path):
    with open(path, newline="") as f:
        return [r for r in csv.reader(f)]


def nearest_val(ts, ts_sorted, payload, tol):
    """Payload of the nearest entry to ts within tolerance, else None."""
    if not ts_sorted:
        return None
    i = bisect_left(ts_sorted, ts)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(ts_sorted):
            d = abs(ts_sorted[j] - ts)
            if best is None or d < best[0]:
                best = (d, payload[j])
    if best is None or best[0] > tol:
        return None
    return best[1]


def nearest_ts(ts, ts_sorted, tol):
    """Timestamp of the nearest entry to ts (used as the row's time)."""
    i = bisect_left(ts_sorted, ts)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(ts_sorted):
            d = abs(ts_sorted[j] - ts)
            if best is None or d < best[0]:
                best = (d, ts_sorted[j])
    return best[1] if best else ts


def temp_identifier(guti_full):
    """First numeric field ('3821342007-3821342007' -> 3821342007)."""
    s = str(guti_full).strip()
    first = s.split("-")[0].strip() if "-" in s else s
    try:
        return int(first)
    except ValueError:
        return None

def extract_4g(csv_dir, target_imsi):
    id_path = os.path.join(csv_dir, "lte_4g", "shark_4g_nas_id.csv")
    attach_path = os.path.join(csv_dir, "lte_4g", "shark_4g_nas_attach.csv")
    if not (os.path.exists(id_path) and os.path.exists(attach_path)):
        return
    attach = []
    for r in read_rows(attach_path):
        if len(r) < 5:
            continue
        try:
            attach.append((int(r[0]), f"{r[3].strip()}-{r[4].strip()}"))
        except ValueError:
            continue
    attach.sort(key=lambda e: e[0])
    a_ts = [e[0] for e in attach]
    a_val = [e[1] for e in attach]
    for r in read_rows(id_path):
        if len(r) < 3 or r[2].strip() != str(target_imsi):
            continue
        try:
            ts_id = int(r[0])
        except ValueError:
            continue
        guti_full = nearest_val(ts_id, a_ts, a_val, TOL_4G_US)
        if guti_full is None:
            continue
        guti = temp_identifier(guti_full)
        if guti and guti != 0:
            yield nearest_ts(ts_id, a_ts, TOL_4G_US), str(target_imsi), guti


def _amf_identity(r):
    """Identity token from an anonymized shark_5g_amf_id.csv row, or None.

    Precedence matters: the concealed-SUCI / suci- token lives in col3, and col2
    can be a bare digit ('0') that must NOT be mistaken for an identity, so col3
    is tested first (mirrors extract_identity_from_amf_id in the plot script).
    """
    if len(r) < 4:
        return None
    col2, col3 = r[2].strip(), r[3].strip()
    if col3.startswith("ANON_5G_CON_IMSI_") or col3.startswith("suci-"):
        return col3
    if col2.startswith("ANON_IMSI_") or col2.isdigit():
        return col2
    return None


def extract_5g(csv_dir, target_imsi, concealed):
    id_path = os.path.join(csv_dir, "nr_5g", "shark_5g_amf_id.csv")
    reg_path = os.path.join(csv_dir, "nr_5g", "shark_5g_amf_registration.csv")
    if not (os.path.exists(id_path) and os.path.exists(reg_path)):
        return
    reg = []
    for r in read_rows(reg_path):
        if len(r) < 4:
            continue
        try:
            reg.append((int(r[0]), r[3].strip()))
        except ValueError:
            continue
    reg.sort(key=lambda e: e[0])
    r_ts = [e[0] for e in reg]
    r_val = [e[1] for e in reg]
    for r in read_rows(id_path):
        identity = _amf_identity(r)
        if identity is None:
            continue
        if concealed:
            if not identity.startswith(str(target_imsi)):
                continue
        elif identity != str(target_imsi):
            continue
        try:
            ts_id = int(r[0])
        except ValueError:
            continue
        guti_full = nearest_val(ts_id, r_ts, r_val, TOL_5G_US)
        if guti_full is None:
            continue
        guti = temp_identifier(guti_full)
        if guti and guti != 0:
            yield nearest_ts(ts_id, r_ts, TOL_5G_US), identity, guti


def iso(ts_us):
    return datetime.fromtimestamp(ts_us / 1e6, tz=timezone.utc).isoformat()

def main():
    args = list(sys.argv[1:])
    config_path = DEFAULT_CONFIG
    window = None
    if "--config" in args:
        k = args.index("--config"); config_path = args[k + 1]; del args[k:k + 2]
    if "--window" in args:
        k = args.index("--window"); window = float(args[k + 1]); del args[k:k + 2]
    out_csv = args[0] if args else os.path.join(HERE, "guti_dataset.csv")

    experiments = load_experiments(config_path)

    all_rows = []
    for _exp, cfg in experiments.items():
        csv_dir = str(cfg["csv_dir"])
        exp_rows, seen = [], set()
        for user in cfg.get("users", []):
            key = (user["operator"], user["ue"], user["imsi"],
                   user.get("tech", "4g"), user.get("concealed", False))
            if key in seen:
                continue
            seen.add(key)
            tech = user.get("tech", "4g").lower()
            if tech == "4g":
                gen = extract_4g(csv_dir, user["imsi"])
            elif tech == "5g":
                gen = extract_5g(csv_dir, user["imsi"], user.get("concealed", False))
            else:
                continue
            for ts_us, identity, guti in gen:
                exp_rows.append([ts_us, user["operator"], user["ue"], tech, identity, guti])
        if window is not None and exp_rows:
            t0 = min(r[0] for r in exp_rows)
            exp_rows = [r for r in exp_rows if (r[0] - t0) / 1e6 <= window]
        all_rows.extend(exp_rows)

    all_rows.sort(key=lambda r: (r[1], r[0]))
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "operator", "ue", "tech", "imsi", "guti"])
        for ts_us, operator, ue, tech, identity, guti in all_rows:
            w.writerow([iso(ts_us), operator, ue, tech, identity, guti])

    print(f"Wrote {len(all_rows)} rows to {out_csv}"
          + (f" (window: first {window:.0f}s per capture)" if window else ""))
    per = {}
    for _ts, op, _ue, tech, ident, g in all_rows:
        d = per.setdefault((op, tech), {"n": 0, "guti": set(), "id": set()})
        d["n"] += 1; d["guti"].add(g); d["id"].add(ident)
    print(f"{'operator':12}{'tech':>5}{'records':>9}{'distinct_guti':>15}{'distinct_id':>13}")
    for (op, tech) in sorted(per):
        d = per[(op, tech)]
        print(f"{op:12}{tech:>5}{d['n']:>9}{len(d['guti']):>15}{len(d['id']):>13}")


if __name__ == "__main__":
    main()
