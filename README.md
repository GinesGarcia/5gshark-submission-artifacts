# 5G-Shark: Artifacts and Evaluation Repository

Anonymized datasets and scripts to reproduce the temporary-identifier (GUTI)
traceability analysis and the NAS registration-reject study from the 5G-Shark
paper.

## Repository structure

| Path | Description |
|------|-------------|
| `experiments_anonym/` | Raw anonymized capture CSVs, one directory per day (`lte_4g/` and `nr_5g/`). |
| `registration_reject/` | NAS reject-cause traces (`OP_A_Reject.txt`) with a dedicated `README.md`. |
| `plots/` | Generated GUTI figures (`.png` / `.pdf`). |
| `01_extract_guti_dataset.py` | Builds `guti_dataset.csv` from the raw captures. |
| `02_compute_table.py` | Computes the per-operator traceability table from `guti_dataset.csv`. |
| `all_csv_to_plot_anonym.py` | Renders the comparative GUTI figures into `plots/`. |
| `requirements.txt` | Dependencies for the plotting script only. |

## Requirements

- `01_extract_guti_dataset.py` and `02_compute_table.py` use the **Python 3 standard library only** — no installation needed.
- `all_csv_to_plot_anonym.py` needs `pandas` + `matplotlib`. Install them (ideally in a virtual environment):

  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```

## Reproducing the paper artifacts

### 1. Temporary-identifier traceability table

Two stdlib-only steps. Step 1 flattens the raw captures into one row per
registration (`timestamp, operator, ue, tech, imsi, guti`); step 2 computes the
per-operator / per-RAT step-size and linkability table and prints it to the
terminal.

```bash
python3 01_extract_guti_dataset.py   # -> writes guti_dataset.csv
python3 02_compute_table.py          # -> prints the traceability table
```

Reproduces the step-size table (Table 4 in the paper):

### 2. GUTI comparison figures

```bash
python3 all_csv_to_plot_anonym.py    # -> writes plots/guti_anonymous_80000s.{png,pdf}
```

### 3. Registration-reject traces

Open `registration_reject/` and read its `README.md` first: it maps specific NAS
reject causes (e.g. Cause 6, Cause 73) to forced RAT downgrades, denial-of-service
loops, and IMSI null-scheme exposure, and explains how to parse `OP_A_Reject.txt`.
