#!/usr/bin/env python3
import csv
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

SPACE = 2 ** 32
GATE = 0.01 * SPACE                 # "linkable" threshold: 1% of 2^32
UNIFORM_MEDIAN_FRAC = 0.2929        # median |X-Y| for two iid uniforms = 0.293*range

HERE = os.path.dirname(os.path.abspath(__file__))

ROW_ORDER = [('Operator A', '5g'), ('Operator A', '4g'), ('Operator B', '5g'),
             ('Operator B', '4g'), ('Operator C', '4g')]
TECHLABEL = {'5g': 'SA (5G)', '4g': 'NSA (4G)'}


def alias(operator):
    """'Operator A' -> 'A'  (falls back to the raw label if it has no space)."""
    return operator.split()[-1] if " " in operator else operator


def ts(s):
    return datetime.fromisoformat(s).timestamp()

def streams_4g(records):
    """4G: one stream per (anonymized) IMSI, time-ordered guti list."""
    by_imsi = defaultdict(list)
    for r in records:
        by_imsi[r['imsi']].append((ts(r['timestamp']), int(r['guti'])))
    return [[g for _t, g in sorted(v)] for v in by_imsi.values()]


def _bursts(evs):
    """Collapse consecutive identical GUTIs; evs sorted [(t, guti)] -> [guti]."""
    out, i = [], 0
    while i < len(evs):
        j = i
        while j + 1 < len(evs) and evs[j + 1][1] == evs[i][1]:
            j += 1
        out.append(evs[i][1])
        i = j + 1
    return out


def streams_5g(records):
    """5G: reconstruct <=2 subscriber tracks by value linkage (concealed identity)."""
    evs = sorted((ts(r['timestamp']), int(r['guti'])) for r in records)
    burst_vals = _bursts(evs)
    tracks, assign = [], []
    for v in burst_vals:
        if not tracks:
            tracks.append(v); assign.append(0); continue
        k = min(range(len(tracks)), key=lambda t: abs(v - tracks[t]))
        if abs(v - tracks[k]) > GATE and len(tracks) < 2:
            tracks.append(v); k = len(tracks) - 1
        tracks[k] = v; assign.append(k)
    out = defaultdict(list)
    for v, k in zip(burst_vals, assign):
        out[k].append(v)
    return list(out.values())


def pooled_steps(streams):
    """All non-zero consecutive |dGUTI| across the streams, pooled."""
    steps = []
    for seq in streams:
        for a, b in zip(seq, seq[1:]):
            d = abs(b - a)
            if d > 0:
                steps.append(d)
    return steps

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "guti_dataset.csv")
    rows = list(csv.DictReader(open(path)))
    groups = defaultdict(list)
    for r in rows:
        groups[(r['operator'], r['tech'])].append(r)

    table = []
    for op, tech in ROW_ORDER:
        recs = groups.get((op, tech), [])
        if not recs:
            print(f"[WARN] no records for {op} / {tech}; skipping row.")
            continue
        gutis = [int(r['guti']) for r in recs]
        span = max(gutis) - min(gutis)
        streams = streams_4g(recs) if tech == '4g' else streams_5g(recs)
        steps = pooled_steps(streams)
        if not steps:
            print(f"[WARN] no reallocation steps for {op} / {tech}; skipping row.")
            continue
        step = statistics.median(steps)
        linkable = 100 * sum(1 for d in steps if d < GATE) / len(steps)
        step_p2 = 100 * step / SPACE
        step_pr = 100 * step / span if span else float('nan')
        # reading label from step-as-%-of-effective-range vs the uniform ideal
        if step_pr < 1:
            reading = "quasi-sequential"
        elif step_pr >= 0.85 * UNIFORM_MEDIAN_FRAC * 100 and linkable < 15:
            reading = "fully re-randomised"
        else:
            reading = "partially re-randomised"
        table.append({
            'op': alias(op), 'tech': TECHLABEL[tech], 'records': len(recs),
            'eff_range_pct': 100 * span / SPACE, 'step_p2': step_p2,
            'step_pr': step_pr, 'linkable': linkable, 'reading': reading,
            'span_abs': span, 'n_streams': len(streams), 'n_steps': len(steps),
            '_op_raw': op, '_tech_raw': tech,
        })

    hdr = f"{'Op/Tech':<14}{'Rec.':>6}{'EffRange%2^32':>14}{'Step%2^32':>11}{'Step%range':>12}{'Linkable%':>11}  Reading"
    print(hdr); print('-' * len(hdr))
    for t in table:
        print(f"{t['op']+' / '+t['tech']:<14}{t['records']:>6}{t['eff_range_pct']:>13.1f}%"
              f"{t['step_p2']:>10.3f}%{t['step_pr']:>11.2f}%{t['linkable']:>10.0f}%  {t['reading']}")
    print(f"\n(uniform re-randomiser ideal: median step ~ {UNIFORM_MEDIAN_FRAC*100:.1f}% of the effective range; "
          f"'linkable' gate = 1% of 2^32)")

if __name__ == "__main__":
    main()
