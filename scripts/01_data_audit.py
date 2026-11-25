import os
import warnings
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

CONTROL_PATH = "data/raw/control_group.csv"
TEST_PATH = "data/raw/test_group.csv"
os.makedirs("outputs", exist_ok=True)


def detect_delimiter(filepath):
    with open(filepath, "r", encoding="utf-8-sig") as f:
        header = f.readline()
    return ";" if header.count(";") > header.count(",") else ","


def load_raw(filepath):
    sep = detect_delimiter(filepath)
    df = pd.read_csv(filepath, sep=sep, encoding="utf-8-sig")
    return df, sep


def find_col(df, keyword):
    for c in df.columns:
        if keyword.lower() in c.lower():
            return c
    return None


def audit_dataset(name, df, sep):
    lines = []
    lines.append(f"### {name}")
    lines.append(f"- **Detected Delimiter:** `{sep}`")
    lines.append(f"- **Shape:** {df.shape[0]} rows × {df.shape[1]} columns")
    lines.append(f"- **Columns:** {list(df.columns)}")
    lines.append(f"- **Exact Duplicate Rows:** {int(df.duplicated().sum())}")

    # Missing values check
    nulls = df.isnull().sum()
    null_cols = nulls[nulls > 0]
    if len(null_cols) == 0:
        lines.append("- **Missing Values:** None (0 nulls)")
    else:
        lines.append("- **Missing Values Found:**")
        for col, cnt in null_cols.items():
            lines.append(f"  - `{col}`: {int(cnt)} missing ({cnt/len(df)*100:.1f}%)")
        bad_rows = df[df.isnull().any(axis=1)]
        date_col = find_col(df, "date")
        if date_col:
            lines.append(f"  - **Affected Dates:** {bad_rows[date_col].tolist()}")

    # Date range check
    date_col = find_col(df, "date")
    if date_col:
        parsed_dates = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
        lines.append(f"- **Date Range:** {parsed_dates.min().date()} to {parsed_dates.max().date()} ({parsed_dates.nunique()} unique days)")
        date_dups = int(parsed_dates.duplicated().sum())
        lines.append(f"- **Duplicate Dates:** {date_dups}")

    # Funnel logic / monotonicity checks
    c_imp = find_col(df, "impression")
    c_reach = find_col(df, "reach")
    c_click = find_col(df, "click")
    c_search = find_col(df, "search")
    c_view = find_col(df, "view")
    c_cart = find_col(df, "cart")
    c_purch = find_col(df, "purchase")
    c_spend = find_col(df, "spend")

    anomalies = []
    checks = [
        ("Reach > Impressions", c_reach, c_imp),
        ("Website Clicks > Impressions", c_click, c_imp),
        ("Website Clicks > Reach", c_click, c_reach),
        ("Purchase > Add to Cart", c_purch, c_cart),
        ("Purchase > Website Clicks", c_purch, c_click),
        ("Add to Cart > Website Clicks", c_cart, c_click),
    ]
    for label, left, right in checks:
        if left and right:
            valid = df[[left, right]].dropna()
            cnt = int((valid[left] > valid[right]).sum())
            if cnt > 0:
                anomalies.append(f"{label}: {cnt} day(s)")

    if c_spend:
        neg_spend = int((df[c_spend].dropna() <= 0).sum())
        if neg_spend > 0:
            anomalies.append(f"Zero/Negative Spend: {neg_spend} day(s)")

    lines.append(f"- **Funnel Logic Anomalies:** {', '.join(anomalies) if anomalies else 'None detected'}")

    # Outlier check (IQR method) on Spend & Purchases
    outlier_notes = []
    for label, col in [("Spend", c_spend), ("Impressions", c_imp), ("Clicks", c_click), ("Purchases", c_purch)]:
        if col:
            s = df[col].dropna()
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            out_cnt = int(((s < lo) | (s > hi)).sum())
            if out_cnt > 0:
                outlier_notes.append(f"{label}: {out_cnt} outlier day(s) [range {s.min():,.0f}–{s.max():,.0f}]")
    lines.append(f"- **Statistical Outliers (1.5×IQR):** {', '.join(outlier_notes) if outlier_notes else 'None'}")

    return "\n".join(lines)


def main():
    ctrl, ctrl_sep = load_raw(CONTROL_PATH)
    test, test_sep = load_raw(TEST_PATH)

    report = ["# Phase 1: Raw Data & Experiment Health Audit\n"]
    report.append(audit_dataset("Control Group (`control_group.csv`)", ctrl, ctrl_sep))
    report.append("")
    report.append(audit_dataset("Test Group (`test_group.csv`)", test, test_sep))

    # Cross-group alignment check
    c_date = find_col(ctrl, "date")
    t_date = find_col(test, "date")
    c_dates = set(pd.to_datetime(ctrl[c_date], dayfirst=True).dt.date)
    t_dates = set(pd.to_datetime(test[t_date], dayfirst=True).dt.date)

    report.append("\n### Cross-Group Experiment Alignment")
    report.append(f"- **Matching Dates:** {len(c_dates & t_dates)} days")
    report.append(f"- **Only in Control:** {sorted(list(c_dates - t_dates))}")
    report.append(f"- **Only in Test:** {sorted(list(t_dates - c_dates))}")

    # Quick raw totals snapshot
    report.append("\n### Raw Metric Totals (Before Cleaning)")
    metrics = ["Spend", "Impression", "Reach", "Click", "Search", "View", "Cart", "Purchase"]
    rows = []
    for m in metrics:
        cc = find_col(ctrl, m)
        tc = find_col(test, m)
        if cc and tc:
            cv = ctrl[cc].sum()
            tv = test[tc].sum()
            diff_pct = ((tv - cv) / cv * 100) if cv != 0 else 0
            rows.append(f"| {m} | {cv:,.0f} | {tv:,.0f} | {diff_pct:+.1f}% |")

    report.append("| Metric | Control Total | Test Total | Raw Diff |")
    report.append("| :--- | ---: | ---: | ---: |")
    report.extend(rows)

    full_report = "\n".join(report)
    with open("outputs/01_audit_report.md", "w") as f:
        f.write(full_report)

    print(full_report)
    print("\nSaved full report -> outputs/01_audit_report.md")


if __name__ == "__main__":
    main()