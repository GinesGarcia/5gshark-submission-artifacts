import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Patch
from matplotlib.ticker import ScalarFormatter

# ============================================================
# CONFIG & ANONYMIZATION
# ============================================================
MAX_EXP_TIME = 80000
LEGEND_ORDER = ["S23", "Pixel8", "Quectel", "Concealed_5g"]

# Mapping for internal consistency
OP_A = "Operator A"
OP_B = "Operator B"
OP_C = "Operator C"

DEVICE_COLORS = {
    "S23": ["#039BE5", "#039BE5", "#039BE5", "#039BE5"],
    "Quectel": ["#D10000", "#DF0404", "#D10404", "#D40202"],
    "Pixel8": ["#F57C00", "#DF5D21", "#F57C00", "#F57C00"],
    "Concealed_5g": ["#56AA59", "#56AA59", "#56AA59", "#56AA59"],
}
FALLBACK_COLORS = ["#E0E0E0", "#9E9E9E", "#616161", "#212121"]

# Base directory anchored to this script
BASE_DIR = Path(__file__).resolve().parent

EXPERIMENTS = {
    "18_03_2026": {
        "csv_dir": BASE_DIR / "experiments_anonym" / "18_03_2026",
        "users": [],
    },
    "23_03_2026": {
        "csv_dir": BASE_DIR / "experiments_anonym" / "23_03_2026",
        "users": [
            {"operator": OP_A, "ue": "S23", "imsi": "ANON_IMSI_A2", "tech": "4g"},
            {"operator": OP_C, "ue": "Pixel8", "imsi": "ANON_IMSI_C1", "tech": "4g"},
            {"operator": OP_A, "ue": "Concealed_5g", "imsi": "ANON_5G_CON_IMSI_A0_", "tech": "5g", "concealed": True},
        ],
    },
    "10_04_2026": {
        "csv_dir": BASE_DIR / "experiments_anonym" / "10_04_2026",
        "users": [
            {"operator": OP_C, "ue": "S23", "imsi": "ANON_IMSI_C1", "tech": "4g"},
        ],
    },
    "15_04_2026": {
        "csv_dir": BASE_DIR / "experiments_anonym" / "15_04_2026",
        "users": [
            {"operator": OP_A, "ue": "Quectel", "imsi": "ANON_IMSI_A2", "tech": "4g"},
            {"operator": OP_B, "ue": "S23", "imsi": "ANON_IMSI_B1", "tech": "4g"},
            {"operator": OP_B, "ue": "Pixel8", "imsi": "ANON_IMSI_B2", "tech": "4g"},
            {"operator": OP_A, "ue": "Concealed_5g", "imsi": "ANON_5G_CON_IMSI_A0_", "tech": "5g", "concealed": True},
            {"operator": OP_B, "ue": "Concealed_5g", "imsi": "ANON_5G_CON_IMSI_B0_", "tech": "5g", "concealed": True},
        ],
    },
}

OUTPUT_DIR = BASE_DIR / "plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# HELPERS
# ============================================================

def parse_temp_identifier(guti_value: str):
    if pd.isna(guti_value):
        return float("nan")
    guti_value = str(guti_value).strip()
    first_part = guti_value.split("-")[0].strip() if "-" in guti_value else guti_value
    try:
        return int(first_part)
    except Exception:
        return float("nan")


# ============================================================
# 4G EXTRACTION
# ============================================================

def extract_4g_imsi_guti_mapping(csv_dir: str, target_imsi: str) -> pd.DataFrame:
    path_id = os.path.join(csv_dir, "lte_4g", "shark_4g_nas_id.csv")
    path_attach = os.path.join(csv_dir, "lte_4g", "shark_4g_nas_attach.csv")

    if not os.path.exists(path_id) or not os.path.exists(path_attach):
        return pd.DataFrame(columns=["datetime", "imsi", "guti_full", "ts_guti_raw"])

    df_ids = pd.read_csv(path_id, names=["ts_id", "s1ap_id", "imsi"], dtype=str)
    df_ids = df_ids[df_ids["imsi"] == target_imsi].copy()

    if df_ids.empty:
        return pd.DataFrame(columns=["datetime", "imsi", "guti_full", "ts_guti_raw"])

    df_ids["ts_id_num"] = pd.to_numeric(df_ids["ts_id"], errors="coerce")

    df_attach_raw = pd.read_csv(path_attach, header=None, dtype=str)
    df_attach = df_attach_raw.iloc[:, [0, 3, 4]].copy()
    df_attach.columns = ["ts_guti_raw", "guti", "guti_chk"]
    df_attach["ts_guti_num"] = pd.to_numeric(df_attach["ts_guti_raw"], errors="coerce")
    df_attach["guti_full"] = df_attach["guti"].astype(str) + "-" + df_attach["guti_chk"].astype(str)

    df_out = pd.merge_asof(
        df_ids.sort_values("ts_id_num"),
        df_attach.sort_values("ts_guti_num"),
        left_on="ts_id_num",
        right_on="ts_guti_num",
        direction="nearest",
        tolerance=500_000
    )

    df_out["datetime"] = pd.to_datetime(df_out["ts_guti_num"], unit="us")
    return df_out[["datetime", "imsi", "guti_full", "ts_guti_raw"]]

# ============================================================
# 5G EXTRACTION
# ============================================================

def extract_identity_from_amf_id(df_raw: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in df_raw.iterrows():
        vals = [str(v).strip() if pd.notna(v) else "" for v in row.tolist()]
        if len(vals) < 4:
            continue

        ts = vals[0]
        col2 = vals[2]
        col3 = vals[3]

        user_id = None
        if col3.startswith("ANON_5G_CON_IMSI_") or col3.startswith("suci-"):
            user_id = col3
        elif col2.startswith("ANON_IMSI_") or col2.isdigit():
            user_id = col2

        if ts and user_id:
            rows.append({"ts_id_raw": ts, "imsi": user_id})

    return pd.DataFrame(rows)

def extract_5g_imsi_guti_mapping(csv_dir: str, target_imsi: str, concealed: bool = False) -> pd.DataFrame:
    path_id = os.path.join(csv_dir, "nr_5g", "shark_5g_amf_id.csv")
    path_reg = os.path.join(csv_dir, "nr_5g", "shark_5g_amf_registration.csv")

    if not os.path.exists(path_id) or not os.path.exists(path_reg):
        return pd.DataFrame(columns=["datetime", "imsi", "guti_full", "ts_guti_raw"])

    df_ids = extract_identity_from_amf_id(pd.read_csv(path_id, header=None, dtype=str))
    if df_ids.empty:
        return pd.DataFrame(columns=["datetime", "imsi", "guti_full", "ts_guti_raw"])

    if concealed:
        df_ids = df_ids[df_ids["imsi"].astype(str).str.startswith(target_imsi)].copy()
    else:
        df_ids = df_ids[df_ids["imsi"] == target_imsi].copy()

    if df_ids.empty:
        return pd.DataFrame(columns=["datetime", "imsi", "guti_full", "ts_guti_raw"])

    df_ids["ts_id_num"] = pd.to_numeric(df_ids["ts_id_raw"], errors="coerce")

    df_reg = pd.read_csv(path_reg, header=None, dtype=str).iloc[:, [0, 3]].copy()
    df_reg.columns = ["ts_guti_raw", "guti_full"]
    df_reg["ts_guti_num"] = pd.to_numeric(df_reg["ts_guti_raw"], errors="coerce")

    df_out = pd.merge_asof(
        df_ids.sort_values("ts_id_num"),
        df_reg.sort_values("ts_guti_num"),
        left_on="ts_id_num",
        right_on="ts_guti_num",
        direction="nearest",
        tolerance=2_000_000
    )

    df_out["datetime"] = pd.to_datetime(df_out["ts_guti_num"], unit="us")
    return df_out[["datetime", "imsi", "guti_full", "ts_guti_raw"]]

def extract_user_df(csv_dir: str, imsi: str, tech: str, concealed: bool = False) -> pd.DataFrame:
    if tech.lower() == "4g":
        return extract_4g_imsi_guti_mapping(csv_dir, imsi)
    if tech.lower() == "5g":
        return extract_5g_imsi_guti_mapping(csv_dir, imsi, concealed)
    return pd.DataFrame()

# ============================================================
# DATASET BUILDING
# ============================================================

def build_operator_dataset(experiment_cfg: dict) -> dict:
    operator_data = {}
    temp_user_data = []
    global_t0 = None
    processed_keys = set()

    for user in experiment_cfg["users"]:
        op = user["operator"]
        ue = user["ue"]
        imsi = user["imsi"]
        tech = user.get("tech", "4g")
        concealed = user.get("concealed", False)

        user_key = (op, ue, imsi, tech, concealed)
        if user_key in processed_keys:
            continue
        processed_keys.add(user_key)

        df = extract_user_df(experiment_cfg["csv_dir"], imsi, tech, concealed)
        if df.empty:
            continue

        df["temp_id_value"] = df["guti_full"].apply(parse_temp_identifier)
        df = df.dropna(subset=["datetime", "temp_id_value"])

        if df.empty:
            continue

        if global_t0 is None or df["datetime"].min() < global_t0:
            global_t0 = df["datetime"].min()

        temp_user_data.append({
            "op": op,
            "ue": ue,
            "tech": tech,
            "concealed": concealed,
            "df": df
        })

    if global_t0 is None:
        return {}

    for data in temp_user_data:
        df = data["df"].copy()
        df["time_s"] = (df["datetime"] - global_t0).dt.total_seconds()
        operator_data.setdefault(data["op"], []).append({
            "ue": data["ue"],
            "tech": data["tech"],
            "concealed": data["concealed"],
            "df": df
        })

    return operator_data

# ============================================================
# GLOBAL PLOT
# ============================================================

def plot_all_operators_first_window(experiments_dict: dict, output_dir: str, max_time: int):
    structured_data = {}
    exp_order_map = {name: i for i, name in enumerate(experiments_dict.keys(), start=1)}

    for exp_name, exp_cfg in experiments_dict.items():
        op_data = build_operator_dataset(exp_cfg)
        for operator, entries in op_data.items():
            structured_data.setdefault(operator, {})
            for entry in entries:
                ue_name = entry["ue"]
                structured_data[operator].setdefault(ue_name, [])
                entry["exp_num"] = exp_order_map[exp_name]
                structured_data[operator][ue_name].append(entry)

    desired_order = [OP_A, OP_B, OP_C]
    valid_operators = [op for op in desired_order if op in structured_data]

    if not valid_operators:
        print("[WARN] No valid operator data found.")
        return

    ncols = len(valid_operators)
    fig, axes = plt.subplots(2, ncols, figsize=(7 * ncols, 11), squeeze=False)
    hatches = {
        'S23': '///',
        'Pixel8': '\\\\\\',
        'Quectel': 'xxx',
        'Concealed_5g': '|||'
    }

    for col, operator in enumerate(valid_operators):
        ax_top, ax_mid = axes[0, col], axes[1, col]
        hist_patches = {}

        sorted_devices = sorted(
            structured_data[operator].items(),
            key=lambda x: LEGEND_ORDER.index(x[0]) if x[0] in LEGEND_ORDER else 99
        )

        for ue_name, experiments in sorted_devices:
            for exp_entry in experiments:
                df = exp_entry["df"].copy()

                df = df[(df["time_s"] <= max_time) & (df["temp_id_value"] > 0)]
                if df.empty:
                    continue

                color_list = DEVICE_COLORS.get(ue_name, FALLBACK_COLORS)
                base_color = mpl.colors.to_rgba(color_list[0])

                is_5g = exp_entry["tech"].lower() == "5g"
                marker_style = "x" if is_5g else "o"
                line_style = "none" if (is_5g and exp_entry["concealed"]) else ("--" if is_5g else "-")

                ax_top.plot(
                    df["time_s"],
                    df["temp_id_value"],
                    marker=marker_style,
                    linestyle=line_style,
                    color=base_color,
                    markersize=4,
                    alpha=0.7,
                    label=ue_name
                )

                ax_mid.hist(
                    df["temp_id_value"],
                    bins=20,
                    histtype="bar",
                    facecolor=list(base_color[:3]) + [0.35],
                    edgecolor=base_color,
                    hatch=hatches.get(ue_name, '')
                )

                if ue_name not in hist_patches:
                    hist_patches[ue_name] = Patch(
                        facecolor=list(base_color[:3]) + [0.35],
                        edgecolor=base_color,
                        hatch=hatches.get(ue_name, ''),
                        label=ue_name
                    )

        # --- Top Graph Formatting ---
        ax_top.set_title(f"{operator}", fontweight='bold', pad=50)
        ax_top.set_xlabel("Time [s]")
        ax_top.set_ylabel("Temporary Identifier Value")
        ax_top.grid(True, alpha=0.3)

        xfmt = ScalarFormatter(useMathText=False)
        xfmt.set_powerlimits((4, 4))
        ax_top.xaxis.set_major_formatter(xfmt)

        handles, labels = ax_top.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ordered_labels = [l for l in LEGEND_ORDER if l in by_label]

        if ordered_labels:
            ax_top.legend(
                [by_label[l] for l in ordered_labels],
                ordered_labels,
                loc='lower center',
                bbox_to_anchor=(0.5, 1.05),
                ncol=len(ordered_labels),
                fontsize=9,
                frameon=True,
                edgecolor='black',
                fancybox=False
            )

        # --- Bottom Graph Formatting ---
        ax_mid.set_xlabel("Temporary Identifier Value")
        ax_mid.set_ylabel("Frequency")
        ax_mid.grid(True, alpha=0.3)

        ordered_patches = [hist_patches[l] for l in LEGEND_ORDER if l in hist_patches]
        if ordered_patches:
            ax_mid.legend(
                handles=ordered_patches,
                loc='lower center',
                bbox_to_anchor=(0.5, 1.05),
                ncol=len(ordered_patches),
                fontsize=9,
                frameon=True,
                edgecolor='black',
                fancybox=False
            )

    plt.tight_layout()
    plt.subplots_adjust(
        top=0.85,
        bottom=0.1,
        hspace=0.4,
        wspace=0.3
    )

    out_png = os.path.join(output_dir, f"guti_anonymous_{max_time}s.png")
    out_pdf = os.path.join(output_dir, f"guti_anonymous_{max_time}s.pdf")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_pdf, format="pdf", bbox_inches="tight")
    plt.close(fig)

    print(f"[OK] Saved figure: {out_png}")
    print(f"[OK] Saved figure: {out_pdf}")

def main():
    plot_all_operators_first_window(EXPERIMENTS, OUTPUT_DIR, MAX_EXP_TIME)

if __name__ == "__main__":
    main()