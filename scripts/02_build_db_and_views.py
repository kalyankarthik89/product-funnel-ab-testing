import os
import sqlite3
import pandas as pd

DB_PATH = "data/processed/ab_testing.db"
SQL_PATH = "sql/funnel_views.sql"
EXPORT_DIR = "data/processed/bi_exports"

os.makedirs("data/processed", exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

COLUMN_MAP = {
    "Campaign Name": "campaign_group",
    "Date": "campaign_date",
    "Spend [USD]": "spend_usd",
    "# of Impressions": "impressions",
    "Reach": "reach",
    "# of Website Clicks": "website_clicks",
    "# of Searches": "searches",
    "# of View Content": "view_content",
    "# of Add to Cart": "add_to_cart",
    "# of Purchase": "purchases",
}


def load_and_standardize(path, label):
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df = df.rename(columns=COLUMN_MAP)
    df["campaign_group"] = label
    df["campaign_date"] = pd.to_datetime(df["campaign_date"], dayfirst=True).dt.strftime("%Y-%m-%d")
    return df


def main():
    ctrl = load_and_standardize("data/raw/control_group.csv", "Control")
    test = load_and_standardize("data/raw/test_group.csv", "Test")
    combined = pd.concat([ctrl, test], ignore_index=True)

    # Build SQLite DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    combined.to_sql("raw_campaign_daily", conn, index=False, if_exists="replace")

    # Execute SQL views
    with open(SQL_PATH, "r") as f:
        conn.executescript(f.read())

    # Automated data quality & reconciliation checks
    raw_cnt = pd.read_sql("SELECT COUNT(*) AS c FROM raw_campaign_daily", conn)["c"].iloc[0]
    clean_cnt = pd.read_sql("SELECT COUNT(*) AS c FROM vw_clean_paired_daily", conn)["c"].iloc[0]
    null_check = pd.read_sql(
        "SELECT COUNT(*) AS c FROM vw_clean_paired_daily WHERE impressions IS NULL OR purchases IS NULL",
        conn,
    )["c"].iloc[0]
    lag_days = pd.read_sql(
        "SELECT campaign_group, campaign_date, add_to_cart, purchases FROM vw_clean_paired_daily WHERE attribution_lag_flag = 1",
        conn,
    )

    print("=== Phase 2: ETL & SQL Validation Checks ===")
    print(f"1. Raw rows loaded: {raw_cnt} (30 Control + 30 Test)")
    print(f"2. Clean paired rows: {clean_cnt} (29 matched days x 2 groups -> excluded 2019-08-05 from BOTH)")
    print(f"3. Nulls in clean paired view: {null_check} (PASS)" if null_check == 0 else f"3. Nulls found: {null_check} (FAIL)")
    print(f"4. Attribution lag days flagged (Purchase > Add to Cart): {len(lag_days)}")
    if len(lag_days) > 0:
        print(lag_days.to_string(index=False))

    # Print Executive Summary Table
    summary = pd.read_sql("SELECT * FROM vw_campaign_summary", conn)
    print("\n=== Clean Paired 29-Day Campaign Summary ===")
    print(summary.T.to_string())

    # Print Funnel Stage Drop-off
    funnel = pd.read_sql("SELECT * FROM vw_funnel_stage_dropoff", conn)
    print("\n=== 6-Stage Funnel Conversion & Drop-Off ===")
    print(funnel.to_string(index=False))

    # Print Weekday vs Weekend
    dow = pd.read_sql("SELECT * FROM vw_weekday_vs_weekend", conn)
    print("\n=== Weekday vs Weekend Split ===")
    print(dow.to_string(index=False))

    # Export all views to CSV for Phase 3 & BI
    views = [
        "vw_clean_paired_daily",
        "vw_campaign_summary",
        "vw_funnel_stage_dropoff",
        "vw_weekday_vs_weekend",
        "vw_cumulative_trends",
    ]
    for v in views:
        df_v = pd.read_sql(f"SELECT * FROM {v}", conn)
        df_v.to_csv(os.path.join(EXPORT_DIR, f"{v}.csv"), index=False)

    conn.close()
    print(f"\nExported {len(views)} clean views -> {EXPORT_DIR}/")


if __name__ == "__main__":
    main()