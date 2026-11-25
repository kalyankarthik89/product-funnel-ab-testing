import os
import math
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

warnings.filterwarnings("ignore")

os.makedirs("outputs", exist_ok=True)
os.makedirs("deck/charts", exist_ok=True)

# Optional scipy for exact t/wilcoxon p-values; pure-math fallback prevents NumPy 2.x crashes
try:
    from scipy import stats as sp_stats
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def two_prop_z_test(x1, n1, x2, n2):
    """Two-sided two-proportion Z-test (Test=2 vs Control=1)."""
    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))
    z = (p2 - p1) / se_pool if se_pool > 0 else 0.0
    p_val = 2.0 * (1.0 - norm_cdf(abs(z)))
    se_unpooled = math.sqrt(p1 * (1.0 - p1) / n1 + p2 * (1.0 - p2) / n2)
    ci_lo = (p2 - p1) - 1.96 * se_unpooled
    ci_hi = (p2 - p1) + 1.96 * se_unpooled
    return p1, p2, p2 - p1, z, p_val, ci_lo, ci_hi


def paired_daily_test(ctrl_arr, test_arr):
    """Paired daily t-test + Wilcoxon (if scipy available) + 10k bootstrap CI."""
    diff = test_arr - ctrl_arr
    n = len(diff)
    mean_diff = float(np.mean(diff))
    sd_diff = float(np.std(diff, ddof=1))
    se_diff = sd_diff / math.sqrt(n)
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0

    if HAS_SCIPY:
        _, p_t = sp_stats.ttest_rel(test_arr, ctrl_arr)
        try:
            _, p_w = sp_stats.wilcoxon(test_arr, ctrl_arr)
        except Exception:
            p_w = np.nan
    else:
        p_t = 2.0 * (1.0 - norm_cdf(abs(t_stat)))
        p_w = np.nan

    rng = np.random.default_rng(42)
    idx = rng.integers(0, n, size=(10000, n))
    boot_means = diff[idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])
    return mean_diff, t_stat, float(p_t), float(p_w) if not np.isnan(p_w) else np.nan, float(ci_lo), float(ci_hi)


def block_bootstrap_ratio_diff(num_c, den_c, num_t, den_t, n_boot=10000, seed=42):
    """Paired-day block bootstrap for ratio metrics (e.g., Blended CPA = SUM(Spend)/SUM(Purchases))."""
    rng = np.random.default_rng(seed)
    n = len(num_c)
    idx = rng.integers(0, n, size=(n_boot, n))
    ratio_c = num_c[idx].sum(axis=1) / den_c[idx].sum(axis=1)
    ratio_t = num_t[idx].sum(axis=1) / den_t[idx].sum(axis=1)
    diffs = ratio_t - ratio_c
    obs_c = num_c.sum() / den_c.sum()
    obs_t = num_t.sum() / den_t.sum()
    obs_diff = obs_t - obs_c
    ci_lo, ci_hi = np.percentile(diffs, [2.5, 97.5])
    # Two-sided bootstrap p-value
    p_pos = np.mean(diffs >= 0)
    p_neg = np.mean(diffs <= 0)
    p_val = float(2.0 * min(p_pos, p_neg))
    prob_test_higher = float(np.mean(diffs > 0) * 100.0)
    return obs_c, obs_t, obs_diff, float(ci_lo), float(ci_hi), p_val, prob_test_higher, diffs


def main():
    daily = pd.read_csv("data/processed/bi_exports/vw_clean_paired_daily.csv")
    summary = pd.read_csv("data/processed/bi_exports/vw_campaign_summary.csv").set_index("campaign_group")
    funnel = pd.read_csv("data/processed/bi_exports/vw_funnel_stage_dropoff.csv")
    trends = pd.read_csv("data/processed/bi_exports/vw_cumulative_trends.csv")
    dow = pd.read_csv("data/processed/bi_exports/vw_weekday_vs_weekend.csv")

    ctrl = daily[daily["campaign_group"] == "Control"].sort_values("campaign_date").reset_index(drop=True)
    test = daily[daily["campaign_group"] == "Test"].sort_values("campaign_date").reset_index(drop=True)
    assert (ctrl["campaign_date"].values == test["campaign_date"].values).all(), "Date alignment mismatch!"

    # 1. Pooled Proportion Z-Tests across Funnel Stages
    prop_specs = [
        ("CTR (Clicks / Impressions)", "total_clicks", "total_impressions"),
        ("Click -> Search", "total_searches", "total_clicks"),
        ("Search -> View Content", "total_views", "total_searches"),
        ("View Content -> Add to Cart", "total_carts", "total_views"),
        ("Add to Cart -> Purchase", "total_purchases", "total_carts"),
        ("Click -> Purchase (Site CVR)", "total_purchases", "total_clicks"),
        ("Impressions -> Purchase", "total_purchases", "total_impressions"),
    ]
    z_rows = []
    for name, num_col, den_col in prop_specs:
        x1, n1 = summary.loc["Control", num_col], summary.loc["Control", den_col]
        x2, n2 = summary.loc["Test", num_col], summary.loc["Test", den_col]
        p1, p2, diff, z, pval, lo, hi = two_prop_z_test(x1, n1, x2, n2)
        z_rows.append({
            "Metric": name,
            "Control (%)": round(p1 * 100, 3),
            "Test (%)": round(p2 * 100, 3),
            "Abs Diff (pp)": round(diff * 100, 3),
            "Rel Lift (%)": round((p2 - p1) / p1 * 100, 2),
            "Z-Stat": round(z, 2),
            "p-value": "<0.0001" if pval < 0.0001 else f"{pval:.4f}",
            "Significant (95%)": "Yes" if pval < 0.05 else "No",
        })
    z_df = pd.DataFrame(z_rows)

    # 2. Paired Daily Level Tests (True Unit of Observation: 29 Matched Days)
    daily_specs = [
        ("Daily Spend (USD)", "spend_usd"),
        ("Daily Impressions", "impressions"),
        ("Daily Website Clicks", "website_clicks"),
        ("Daily Add to Cart", "add_to_cart"),
        ("Daily Purchases", "purchases"),
        ("Daily CPA (USD)", "cpa_usd"),
        ("Daily CTR (%)", "ctr_pct"),
        ("Daily View-to-Cart (%)", "view_to_cart_pct"),
        ("Daily Cart-to-Purchase (%)", "cart_to_purchase_pct"),
        ("Daily Click-to-Purchase (%)", "click_to_purchase_pct"),
    ]
    daily_rows = []
    for label, col in daily_specs:
        c_arr = ctrl[col].values.astype(float)
        t_arr = test[col].values.astype(float)
        mdiff, tstat, pt, pw, lo, hi = paired_daily_test(c_arr, t_arr)
        daily_rows.append({
            "Daily Metric (n=29 paired days)": label,
            "Control Mean": round(c_arr.mean(), 2),
            "Test Mean": round(t_arr.mean(), 2),
            "Mean Diff (T-C)": round(mdiff, 2),
            "95% Boot CI": f"[{lo:+.2f}, {hi:+.2f}]",
            "Paired t p-val": "<0.0001" if pt < 0.0001 else f"{pt:.4f}",
            "Wilcoxon p-val": ("N/A" if np.isnan(pw) else ("<0.0001" if pw < 0.0001 else f"{pw:.4f}")),
            "Sig (95%)": "Yes" if pt < 0.05 else "No",
        })
    daily_df = pd.DataFrame(daily_rows)

    # 3. Block Bootstrap on True Blended Ratio Metrics (10,000 iterations)
    cpa_c, cpa_t, cpa_diff, cpa_lo, cpa_hi, cpa_p, cpa_prob, cpa_boot_diffs = block_bootstrap_ratio_diff(
        ctrl["spend_usd"].values, ctrl["purchases"].values,
        test["spend_usd"].values, test["purchases"].values
    )
    cvr_c, cvr_t, cvr_diff, cvr_lo, cvr_hi, cvr_p, _, _ = block_bootstrap_ratio_diff(
        ctrl["purchases"].values * 100.0, ctrl["website_clicks"].values,
        test["purchases"].values * 100.0, test["website_clicks"].values
    )
    cpm_c, cpm_t, cpm_diff, cpm_lo, cpm_hi, cpm_p, _, _ = block_bootstrap_ratio_diff(
        ctrl["spend_usd"].values * 1000.0, ctrl["impressions"].values,
        test["spend_usd"].values * 1000.0, test["impressions"].values
    )

    # 4. Financial Impact / Opportunity Sizing
    test_spend = float(summary.loc["Test", "total_spend_usd"])
    test_purch = float(summary.loc["Test", "total_purchases"])
    ctrl_spend = float(summary.loc["Control", "total_spend_usd"])
    ctrl_purch = float(summary.loc["Control", "total_purchases"])

    # If Test's budget ran at Control's CPA:
    expected_purch_at_ctrl_cpa = test_spend / cpa_c
    incremental_orders_29d = expected_purch_at_ctrl_cpa - test_purch
    annualized_orders_gained = incremental_orders_29d * (365.0 / 29.0)

    # Cost saved to achieve Test's exact 14,869 orders at Control CPA:
    cost_saving_29d = test_spend - (test_purch * cpa_c)
    annualized_cost_saving = cost_saving_29d * (365.0 / 29.0)

    # Save Statistical Report Markdown
    md = []
    md.append("# Phase 3: Statistical Hypothesis Testing & Executive Decision Memo\n")
    md.append("## Executive Verdict: DO NOT SHIP Test Campaign As-Is (Adopt Hybrid Strategy)\n")
    md.append(
        f"Across **29 strictly matched calendar days** (excluding `2019-08-05` from both groups to fix Control's missing funnel log), "
        f"the Test campaign spent **+11.6% more** (`${test_spend:,.0f}` vs `${ctrl_spend:,.0f}`) while generating **-1.9% fewer purchases** "
        f"(`{test_purch:,.0f}` vs `{ctrl_purch:,.0f}`). True Blended CPA deteriorated by **+${cpa_diff:.2f} (+{cpa_diff/cpa_c*100:.1f}%)** "
        f"from `${cpa_c:.2f}` to `${cpa_t:.2f}`.\n"
    )
    md.append("## 1. Block Bootstrap Analysis on Blended Ratio Metrics (10,000 Paired-Day Resamples)\n")
    md.append("| Blended Metric | Control | Test | Diff (Test - Ctrl) | 95% Bootstrap CI | Bootstrap p-value | Business Takeaway |")
    md.append("| :--- | ---: | ---: | ---: | :---: | ---: | :--- |")
    md.append(f"| **Blended CPA ($/Order)** | ${cpa_c:.2f} | ${cpa_t:.2f} | **+${cpa_diff:.2f} (+{cpa_diff/cpa_c*100:.1f}%)** | `[${cpa_lo:+.2f}, ${cpa_hi:+.2f}]` | {cpa_p:.4f} | Test has a **{cpa_prob:.1f}% probability** of higher CPA |")
    md.append(f"| **Blended CPM ($/1k Imp)** | ${cpm_c:.2f} | ${cpm_t:.2f} | **+${cpm_diff:.2f} (+{cpm_diff/cpm_c*100:.1f}%)** | `[${cpm_lo:+.2f}, ${cpm_hi:+.2f}]` | {cpm_p:.4f} | Test inventory is significantly more expensive |")
    md.append(f"| **Click-to-Purchase (%)** | {cvr_c:.2f}% | {cvr_t:.2f}% | **{cvr_diff:+.2f} pp** | `[{cvr_lo:+.2f}, {cvr_hi:+.2f}]` | {cvr_p:.4f} | Lower on-site conversion per click in Test |")

    md.append("\n## 2. Paired Daily Hypothesis Tests (Unit of Analysis = Matched Day, n=29)\n")
    md.append(daily_df.to_markdown(index=False))

    md.append("\n## 3. Macro Funnel Two-Proportion Z-Tests (Aggregate Event Volume)\n")
    md.append("> *Note: Pooled Z-tests on millions of events treat clicks/impressions as independent and yield tiny p-values; we pair them with daily-level & block-bootstrap tests above to prevent pseudoreplication.*\n")
    md.append(z_df.to_markdown(index=False))

    md.append("\n## 4. Financial Opportunity & Budget Reallocation Sizing\n")
    md.append(f"- **Direct Budget Waste Avoided:** Running Test's `{test_purch:,.0f}` orders at Control's `${cpa_c:.2f}` CPA saves **${cost_saving_29d:,.0f} per 29 days (~${annualized_cost_saving:,.0f}/year annualized)**.")
    md.append(f"- **Volume Upside at Constant Budget:** Reallocating Test's `${test_spend:,.0f}` spend to Control's efficiency yields **~{expected_purch_at_ctrl_cpa:,.0f} orders** (**+{incremental_orders_29d:,.0f} incremental orders/month**, or **+{annualized_orders_gained:,.0f} orders/year**).")
    md.append("- **Next-Iteration Hypothesis (Hybrid Win):** Test's ad creative achieved **+69.8% CTR** and its checkout converted **58.3% of carts** (vs 40.2% in Control), but suffered a **-20.4 pp View-to-Cart drop** and **+67% CPM**. Run a follow-up A/B test combining **Control's lower-CPM bidding strategy** with **Test's high-CTR creative + streamlined checkout**, while auditing product-page-to-cart friction.")

    report_text = "\n".join(md)
    with open("outputs/02_statistical_report.md", "w") as f:
        f.write(report_text)

    z_df.to_csv("data/processed/bi_exports/ab_funnel_ztests.csv", index=False)
    daily_df.to_csv("data/processed/bi_exports/ab_daily_paired_tests.csv", index=False)

    # =========================================================================
    # GENERATE 4 EXECUTIVE CHARTS
    # =========================================================================
    plt.rcParams.update({
        "font.family": "sans-serif",
        "axes.edgecolor": "#CCCCCC",
        "axes.linewidth": 0.8,
    })
    C_CTRL = "#1B4F72"   # Navy Blue
    C_TEST = "#D35400"   # Burnt Orange
    C_RED = "#C0392B"
    C_GREEN = "#1E8449"

    # Chart 1: Stage-by-Stage Funnel Conversion Comparison
    stages_plot = ["Impressions ->\nClicks (CTR)", "Clicks ->\nSearches", "Searches ->\nView Content", "View Content ->\nAdd to Cart", "Add to Cart ->\nPurchase"]
    ctrl_vals = [summary.loc["Control", "ctr_pct"], summary.loc["Control", "click_to_search_pct"],
                 summary.loc["Control", "search_to_view_pct"], summary.loc["Control", "view_to_cart_pct"],
                 summary.loc["Control", "cart_to_purchase_pct"]]
    test_vals = [summary.loc["Test", "ctr_pct"], summary.loc["Test", "click_to_search_pct"],
                 summary.loc["Test", "search_to_view_pct"], summary.loc["Test", "view_to_cart_pct"],
                 summary.loc["Test", "cart_to_purchase_pct"]]

    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=200)
    x = np.arange(len(stages_plot))
    w = 0.36
    b1 = ax.bar(x - w/2, ctrl_vals, w, label="Control Campaign", color=C_CTRL)
    b2 = ax.bar(x + w/2, test_vals, w, label="Test Campaign", color=C_TEST)
    for bar in b1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.4, f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color=C_CTRL)
    for bar in b2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.4, f"{bar.get_height():.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color=C_TEST)

    ax.annotate("Major Leak:\n-20.4 pp Drop", xy=(3 + w/2, test_vals[3] + 5), xytext=(3.15, 78),
                arrowprops=dict(arrowstyle="->", color=C_RED, lw=1.8), fontsize=9.5, fontweight="bold", color=C_RED, ha="center")
    ax.annotate("Checkout Win:\n+18.1 pp Lift", xy=(4 + w/2, test_vals[4] + 5), xytext=(4.05, 76),
                arrowprops=dict(arrowstyle="->", color=C_GREEN, lw=1.8), fontsize=9.5, fontweight="bold", color=C_GREEN, ha="center")

    ax.set_xticks(x)
    ax.set_xticklabels(stages_plot, fontsize=9.5, fontweight="bold")
    ax.set_ylabel("Step Conversion Rate (%)", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 102)
    ax.set_title("6-Stage Funnel Conversion Audit: Test Wins CTR & Checkout, Bleeds at View-to-Cart", fontsize=12, fontweight="bold", pad=14)
    ax.legend(frameon=False, loc="upper left", fontsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig("deck/charts/01_funnel_dropoff_comparison.png")
    plt.close()

    # Chart 2: Block Bootstrap Distribution of Blended CPA Difference
    fig, ax = plt.subplots(figsize=(9.5, 4.8), dpi=200)
    ax.hist(cpa_boot_diffs, bins=45, color="#5DADE2", alpha=0.75, edgecolor="white")
    ax.axvline(0, color="#2C3E50", linestyle="--", lw=1.8, label="No Difference ($0.00)")
    ax.axvline(cpa_diff, color=C_RED, lw=2.4, label=f"Observed Diff: +${cpa_diff:.2f}/order")
    ax.axvspan(cpa_lo, cpa_hi, color=C_RED, alpha=0.12, label=f"95% CI: [${cpa_lo:+.2f}, ${cpa_hi:+.2f}]")
    ax.set_title(f"Block Bootstrap (10,000 Resamples): Blended CPA Diff (Test - Control)\n{cpa_prob:.1f}% Probability That Test Campaign Has Higher Acquisition Cost", fontsize=11.5, fontweight="bold", pad=12)
    ax.set_xlabel("Blended CPA Difference: Test Minus Control (USD per Purchase)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Bootstrap Frequency", fontsize=10, fontweight="bold")
    ax.legend(frameon=True, facecolor="white", fontsize=9.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig("deck/charts/02_cpa_bootstrap_distribution.png")
    plt.close()

    # Chart 3: Rolling 7-Day CPA Trend (SQL Window Function Output)
    t_ctrl = trends[trends["campaign_group"] == "Control"].sort_values("campaign_date")
    t_test = trends[trends["campaign_group"] == "Test"].sort_values("campaign_date")

    fig, ax = plt.subplots(figsize=(10.5, 4.8), dpi=200)
    dates_lbl = [d[5:] for d in t_ctrl["campaign_date"]]
    ax.plot(dates_lbl, t_ctrl["rolling_7d_cpa_usd"], marker="o", ms=4.5, lw=2.4, color=C_CTRL, label=f"Control Rolling 7D CPA (Blended: ${cpa_c:.2f})")
    ax.plot(dates_lbl, t_test["rolling_7d_cpa_usd"], marker="s", ms=4.5, lw=2.4, color=C_TEST, label=f"Test Rolling 7D CPA (Blended: ${cpa_t:.2f})")
    ax.fill_between(dates_lbl, t_ctrl["rolling_7d_cpa_usd"], t_test["rolling_7d_cpa_usd"],
                    where=(t_test["rolling_7d_cpa_usd"].values >= t_ctrl["rolling_7d_cpa_usd"].values),
                    color=C_RED, alpha=0.12, interpolate=True, label="Test Cost Penalty")
    ax.set_title("Rolling 7-Day CPA Trajectory Across 29 Matched Days (Aug 2019)", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Rolling 7-Day CPA (USD)", fontsize=10, fontweight="bold")
    ax.set_xlabel("Date (MM-DD, Excluding Missing Day 08-05)", fontsize=10, fontweight="bold")
    plt.xticks(rotation=45, fontsize=8.5)
    ax.legend(frameon=True, facecolor="white", fontsize=9.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig("deck/charts/03_rolling_7d_cpa_trend.png")
    plt.close()

    # Chart 4: Vanity Metrics vs Business Reality (% Relative Change: Test vs Control)
    metrics_vr = [
        "CTR (Vanity)",
        "Cart -> Purchase",
        "CPM Cost (Bad)",
        "CPA Cost (Bad)",
        "Total Spend",
        "Total Purchases",
        "Click -> Purchase",
        "View -> Cart Leak",
    ]
    rel_changes = [
        (summary.loc["Test", "ctr_pct"] / summary.loc["Control", "ctr_pct"] - 1) * 100,
        (summary.loc["Test", "cart_to_purchase_pct"] / summary.loc["Control", "cart_to_purchase_pct"] - 1) * 100,
        (summary.loc["Test", "blended_cpm_usd"] / summary.loc["Control", "blended_cpm_usd"] - 1) * 100,
        (summary.loc["Test", "blended_cpa_usd"] / summary.loc["Control", "blended_cpa_usd"] - 1) * 100,
        (summary.loc["Test", "total_spend_usd"] / summary.loc["Control", "total_spend_usd"] - 1) * 100,
        (summary.loc["Test", "total_purchases"] / summary.loc["Control", "total_purchases"] - 1) * 100,
        (summary.loc["Test", "click_to_purchase_pct"] / summary.loc["Control", "click_to_purchase_pct"] - 1) * 100,
        (summary.loc["Test", "view_to_cart_pct"] / summary.loc["Control", "view_to_cart_pct"] - 1) * 100,
    ]
    bar_colors = [C_GREEN, C_GREEN, C_RED, C_RED, "#7F8C8D", C_RED, C_RED, C_RED]

    fig, ax = plt.subplots(figsize=(10, 5.0), dpi=200)
    y_pos = np.arange(len(metrics_vr))
    bars = ax.barh(y_pos, rel_changes, color=bar_colors, height=0.62)
    ax.axvline(0, color="#2C3E50", lw=1.2)
    for bar, val in zip(bars, rel_changes):
        offset = 1.8 if val >= 0 else -1.8
        ha = "left" if val >= 0 else "right"
        ax.text(val + offset, bar.get_y() + bar.get_height()/2, f"{val:+.1f}%", va="center", ha=ha, fontsize=9.5, fontweight="bold")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(metrics_vr, fontsize=10, fontweight="bold")
    ax.invert_yaxis()
    ax.set_xlim(-45, 88)
    ax.set_xlabel("Relative Change: Test vs Control (%)", fontsize=10, fontweight="bold")
    ax.set_title("Vanity Wins vs Unit Economics Reality: Why CTR Alone Misleads Stakeholders", fontsize=12, fontweight="bold", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    plt.tight_layout()
    plt.savefig("deck/charts/04_vanity_vs_reality_economics.png")
    plt.close()

    # =========================================================================
    # BUILD 5-SLIDE EXECUTIVE DECISION DECK (.pptx)
    # =========================================================================
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    NAVY = RGBColor(20, 45, 76)
    ORANGE = RGBColor(211, 84, 0)
    DARK = RGBColor(33, 37, 41)
    GRAY = RGBColor(100, 110, 120)
    LIGHT_BG = RGBColor(245, 247, 250)
    WHITE = RGBColor(255, 255, 255)
    RED = RGBColor(192, 57, 43)

    def add_header(slide, title_text, subtitle_text):
        bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.15))
        bar.fill.solid()
        bar.fill.fore_color.rgb = NAVY
        bar.line.fill.background()

        tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.18), Inches(12.2), Inches(0.55))
        p = tb.text_frame.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = WHITE

        sb = slide.shapes.add_textbox(Inches(0.55), Inches(0.72), Inches(12.2), Inches(0.35))
        p2 = sb.text_frame.paragraphs[0]
        p2.text = subtitle_text
        p2.font.size = Pt(12.5)
        p2.font.color.rgb = RGBColor(200, 215, 230)

    def add_bullets(slide, left, top, width, height, items, font_size=14):
        tb = slide.shapes.add_textbox(left, top, width, height)
        tf = tb.text_frame
        tf.word_wrap = True
        for i, (head, body) in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(10)
            r1 = p.add_run()
            r1.text = f"• {head}: "
            r1.font.bold = True
            r1.font.size = Pt(font_size)
            r1.font.color.rgb = NAVY
            r2 = p.add_run()
            r2.text = body
            r2.font.size = Pt(font_size)
            r2.font.color.rgb = DARK

    # Slide 1: Cover & Verdict
    s1 = prs.slides.add_slide(blank_layout)
    bg = s1.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()

    t1 = s1.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.7), Inches(1.4))
    p = t1.text_frame.paragraphs[0]
    p.text = "E-Commerce Marketing Funnel &\nA/B Testing Executive Readout"
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = WHITE

    t2 = s1.shapes.add_textbox(Inches(0.8), Inches(3.25), Inches(11.5), Inches(0.7))
    p = t2.text_frame.paragraphs[0]
    p.text = "Experiment Integrity Audit  •  6-Stage Funnel Diagnosis  •  Block-Bootstrap Statistical Testing"
    p.font.size = Pt(16)
    p.font.color.rgb = RGBColor(185, 205, 225)

    verdict_box = s1.shapes.add_shape(1, Inches(0.8), Inches(4.35), Inches(11.7), Inches(1.75))
    verdict_box.fill.solid()
    verdict_box.fill.fore_color.rgb = RGBColor(32, 68, 108)
    verdict_box.line.color.rgb = ORANGE
    verdict_box.line.width = Pt(2)

    vb = s1.shapes.add_textbox(Inches(1.05), Inches(4.5), Inches(11.2), Inches(1.5))
    tf = vb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "EXECUTIVE DECISION: DO NOT SHIP TEST CAMPAIGN AS-IS"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 195, 113)
    p2 = tf.add_paragraph()
    p2.space_before = Pt(8)
    p2.text = (
        f"Despite a +69.8% CTR lift, Test increased Blended CPA by +13.8% (${cpa_c:.2f} -> ${cpa_t:.2f}) and produced "
        f"-1.9% fewer orders on +11.6% more spend. Reallocating spend to Control efficiency saves ~${annualized_cost_saving:,.0f}/yr "
        f"or unlocks +{annualized_orders_gained:,.0f} annualized incremental orders."
    )
    p2.font.size = Pt(14)
    p2.font.color.rgb = WHITE

    # Slide 2: Audit & Vanity vs Reality
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "1. Experiment Audit & Vanity-vs-Reality Diagnosis", "Fixing the Aug 5 missing-log bug reversed the apparent purchase lift from +3.1% to -1.9%")
    s2.shapes.add_picture("deck/charts/04_vanity_vs_reality_economics.png", Inches(0.45), Inches(1.4), width=Inches(7.7))
    add_bullets(s2, Inches(8.35), Inches(1.55), Inches(4.6), Inches(5.3), [
        ("Denominator Bug Fixed", "Control missed funnel logs on Aug 5 while recording Spend. Excluding Aug 5 from BOTH groups yields 29 matched calendar days."),
        ("Headline Reversal", "Raw totals showed Test +3.1% orders; matched 29-day totals prove Test delivered -1.9% fewer orders (14,869 vs 15,161)."),
        ("Attribution Lag Flagged", "Control Aug 30 had 670 purchases vs 442 carts (cross-day attribution lag) — explicitly flagged in SQL."),
        ("CPM Inflation", "Test paid $35.13 CPM (+67% vs Control's $21.03), wiping out its CTR advantage."),
    ], font_size=13)

    # Slide 3: Funnel Leak Diagnosis
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "2. 6-Stage Funnel Diagnosis: Where Test Wins vs. Bleeds", "Test attracts clicks and closes carts well, but suffers a -20.4 pp crash from Product View to Cart")
    s3.shapes.add_picture("deck/charts/01_funnel_dropoff_comparison.png", Inches(0.45), Inches(1.35), width=Inches(8.2))
    add_bullets(s3, Inches(8.8), Inches(1.55), Inches(4.2), Inches(5.3), [
        ("Top-Funnel Win (+69.8%)", "Test CTR hit 8.25% vs 4.86% in Control — strong creative hook and ad relevance."),
        ("Mid-Funnel Crash (-20.4 pp)", "View-to-Cart plunged from 66.9% to 46.5%, indicating expectation mismatch or price/landing friction."),
        ("Checkout Rebound (+18.1 pp)", "Cart-to-Purchase jumped to 58.3% vs 40.2% — high intent among users who survive the product page."),
        ("Net Site CVR (-1.34 pp)", "Overall Click-to-Purchase dropped from 9.83% to 8.49%."),
    ], font_size=13)

    # Slide 4: Statistical Rigor & CPA Stability
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "3. Statistical Validation: Block Bootstrap & Rolling 7D Trend", "Using paired-day resampling avoids click-level pseudoreplication for ratio metrics like CPA")
    s4.shapes.add_picture("deck/charts/02_cpa_bootstrap_distribution.png", Inches(0.4), Inches(1.45), width=Inches(6.2))
    s4.shapes.add_picture("deck/charts/03_rolling_7d_cpa_trend.png", Inches(6.75), Inches(1.45), width=Inches(6.2))

    foot = s4.shapes.add_textbox(Inches(0.55), Inches(6.25), Inches(12.2), Inches(0.95))
    tf = foot.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = (
        f"Key Statistical Takeaway: Block bootstrap (10,000 resamples) estimates Blended CPA penalty at +${cpa_diff:.2f}/order "
        f"(95% CI: [${cpa_lo:+.2f}, ${cpa_hi:+.2f}], p={cpa_p:.4f}; {cpa_prob:.1f}% probability Test is costlier). "
        f"Consistent across Weekdays ($4.23 vs $4.78) and Weekends ($5.01 vs $5.87) — no Simpson's Paradox."
    )
    p.font.size = Pt(12.5)
    p.font.bold = True
    p.font.color.rgb = NAVY

    # Slide 5: Recommendations & Action Plan
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "4. Actionable Roadmap & Quantified Business Impact", "Hold Test rollout, protect unit economics, and test a Hybrid Creative + Bidding Variant")
    add_bullets(s5, Inches(0.7), Inches(1.55), Inches(11.9), Inches(5.4), [
        ("1. Immediate Action — Hold Full Rollout & Reallocate Budget", f"Shifting Test's ${test_spend:,.0f} spend to Control's ${cpa_c:.2f} CPA saves ${cost_saving_29d:,.0f}/month (~${annualized_cost_saving:,.0f}/year) for equal volume, or delivers +{incremental_orders_29d:,.0f} extra orders/month (+{annualized_orders_gained:,.0f}/year) at flat budget."),
        ("2. Diagnose Product Page -> Add-to-Cart Friction (-20.4 pp)", "Audit Test landing pages for message-match gaps, shipping/price surprises, or mobile load latency driving 53.6% post-view abandonment."),
        ("3. Launch Follow-Up Hybrid A/B Test (2x2 Factorial)", "Pair Control's low-CPM bidding/audience targeting ($21.03 CPM) with Test's high-CTR creative (8.25%) and high-converting checkout flow (58.3% Cart->Purchase)."),
        ("4. Upgrade Experiment Guardrails", "Replace CTR-led campaign reviews with CPA + Click-to-Purchase primary guardrails, enforce automated missing-day alerts, and track user-level IDs to eliminate cross-day attribution lag."),
    ], font_size=15)

    prs.save("deck/AB_Test_Executive_Decision_Deck.pptx")

    print(report_text)
    print("\n--- Generated Artifacts ---")
    print("1. outputs/02_statistical_report.md")
    print("2. deck/charts/01_funnel_dropoff_comparison.png .. 04_vanity_vs_reality_economics.png")
    print("3. deck/AB_Test_Executive_Decision_Deck.pptx")


if __name__ == "__main__":
    main()