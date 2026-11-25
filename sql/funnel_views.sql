-- ============================================================================
-- Product Funnel & A/B Testing Analytics — Modular SQL Views (SQLite)
-- ============================================================================

-- 1. Clean Paired Daily View (Excludes 2019-08-05 from BOTH groups to avoid
--    broken Spend/Purchase denominator & day-of-week imbalance -> 29 matched days)
DROP VIEW IF EXISTS vw_clean_paired_daily;
CREATE VIEW vw_clean_paired_daily AS
WITH incomplete_dates AS (
    SELECT DISTINCT campaign_date
    FROM raw_campaign_daily
    WHERE impressions IS NULL
       OR website_clicks IS NULL
       OR purchases IS NULL
)
SELECT
    r.campaign_group,
    r.campaign_date,
    CASE CAST(strftime('%w', r.campaign_date) AS INTEGER)
        WHEN 0 THEN 'Sun'
        WHEN 1 THEN 'Mon'
        WHEN 2 THEN 'Tue'
        WHEN 3 THEN 'Wed'
        WHEN 4 THEN 'Thu'
        WHEN 5 THEN 'Fri'
        WHEN 6 THEN 'Sat'
    END AS day_of_week,
    CASE
        WHEN CAST(strftime('%w', r.campaign_date) AS INTEGER) IN (0, 6) THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type,
    r.spend_usd,
    r.impressions,
    r.reach,
    r.website_clicks,
    r.searches,
    r.view_content,
    r.add_to_cart,
    r.purchases,
    -- Transparency flag for cross-day attribution lag
    CASE WHEN r.purchases > r.add_to_cart THEN 1 ELSE 0 END AS attribution_lag_flag,
    -- Daily Unit Economics
    ROUND(CAST(r.spend_usd AS REAL) * 1000.0 / NULLIF(r.impressions, 0), 2) AS cpm_usd,
    ROUND(CAST(r.spend_usd AS REAL) / NULLIF(r.website_clicks, 0), 4) AS cpc_usd,
    ROUND(CAST(r.spend_usd AS REAL) / NULLIF(r.purchases, 0), 2) AS cpa_usd,
    -- Daily Stage Conversion Rates (%)
    ROUND(CAST(r.website_clicks AS REAL) * 100.0 / NULLIF(r.impressions, 0), 3) AS ctr_pct,
    ROUND(CAST(r.searches AS REAL) * 100.0 / NULLIF(r.website_clicks, 0), 2) AS click_to_search_pct,
    ROUND(CAST(r.view_content AS REAL) * 100.0 / NULLIF(r.website_clicks, 0), 2) AS click_to_view_pct,
    ROUND(CAST(r.add_to_cart AS REAL) * 100.0 / NULLIF(r.view_content, 0), 2) AS view_to_cart_pct,
    ROUND(CAST(r.purchases AS REAL) * 100.0 / NULLIF(r.add_to_cart, 0), 2) AS cart_to_purchase_pct,
    ROUND(CAST(r.purchases AS REAL) * 100.0 / NULLIF(r.website_clicks, 0), 2) AS click_to_purchase_pct,
    ROUND(CAST(r.purchases AS REAL) * 100.0 / NULLIF(r.impressions, 0), 4) AS imp_to_purchase_pct,
    ROUND(CAST(r.impressions AS REAL) / NULLIF(r.reach, 0), 3) AS ad_frequency
FROM raw_campaign_daily r
WHERE r.campaign_date NOT IN (SELECT campaign_date FROM incomplete_dates);


-- 2. Executive Campaign Summary (True Blended Funnel & Unit Economics across 29 Matched Days)
DROP VIEW IF EXISTS vw_campaign_summary;
CREATE VIEW vw_campaign_summary AS
SELECT
    campaign_group,
    COUNT(*) AS matched_days,
    SUM(spend_usd) AS total_spend_usd,
    SUM(impressions) AS total_impressions,
    SUM(reach) AS total_reach,
    SUM(website_clicks) AS total_clicks,
    SUM(searches) AS total_searches,
    SUM(view_content) AS total_views,
    SUM(add_to_cart) AS total_carts,
    SUM(purchases) AS total_purchases,
    -- Blended Economics
    ROUND(SUM(spend_usd) * 1000.0 / SUM(impressions), 2) AS blended_cpm_usd,
    ROUND(CAST(SUM(spend_usd) AS REAL) / SUM(website_clicks), 4) AS blended_cpc_usd,
    ROUND(CAST(SUM(spend_usd) AS REAL) / SUM(purchases), 2) AS blended_cpa_usd,
    ROUND(CAST(SUM(impressions) AS REAL) / SUM(reach), 3) AS avg_ad_frequency,
    -- Blended Funnel Rates (%)
    ROUND(CAST(SUM(website_clicks) AS REAL) * 100.0 / SUM(impressions), 3) AS ctr_pct,
    ROUND(CAST(SUM(searches) AS REAL) * 100.0 / SUM(website_clicks), 2) AS click_to_search_pct,
    ROUND(CAST(SUM(view_content) AS REAL) * 100.0 / SUM(searches), 2) AS search_to_view_pct,
    ROUND(CAST(SUM(add_to_cart) AS REAL) * 100.0 / SUM(view_content), 2) AS view_to_cart_pct,
    ROUND(CAST(SUM(purchases) AS REAL) * 100.0 / SUM(add_to_cart), 2) AS cart_to_purchase_pct,
    ROUND(CAST(SUM(purchases) AS REAL) * 100.0 / SUM(website_clicks), 2) AS click_to_purchase_pct,
    ROUND(CAST(SUM(purchases) AS REAL) * 100.0 / SUM(impressions), 4) AS overall_imp_to_purchase_pct
FROM vw_clean_paired_daily
GROUP BY campaign_group;


-- 3. 6-Stage Funnel Long Format (For BI Funnel Visuals & Stage Drop-Off Analysis)
DROP VIEW IF EXISTS vw_funnel_stage_dropoff;
CREATE VIEW vw_funnel_stage_dropoff AS
WITH totals AS (
    SELECT * FROM vw_campaign_summary
),
stages AS (
    SELECT campaign_group, 1 AS stage_order, 'Impressions' AS stage_name, total_impressions AS stage_volume, total_impressions AS prev_volume FROM totals
    UNION ALL
    SELECT campaign_group, 2, 'Website Clicks', total_clicks, total_impressions FROM totals
    UNION ALL
    SELECT campaign_group, 3, 'Searches', total_searches, total_clicks FROM totals
    UNION ALL
    SELECT campaign_group, 4, 'View Content', total_views, total_searches FROM totals
    UNION ALL
    SELECT campaign_group, 5, 'Add to Cart', total_carts, total_views FROM totals
    UNION ALL
    SELECT campaign_group, 6, 'Purchase', total_purchases, total_carts FROM totals
)
SELECT
    campaign_group,
    stage_order,
    stage_name,
    stage_volume,
    ROUND(CAST(stage_volume AS REAL) * 100.0 / NULLIF(prev_volume, 0), 2) AS step_conversion_pct,
    ROUND((1.0 - CAST(stage_volume AS REAL) / NULLIF(prev_volume, 0)) * 100.0, 2) AS step_dropoff_pct
FROM stages
ORDER BY campaign_group, stage_order;


-- 4. Weekday vs Weekend Segmentation (Simpson's Paradox / Temporal Bias Check)
DROP VIEW IF EXISTS vw_weekday_vs_weekend;
CREATE VIEW vw_weekday_vs_weekend AS
SELECT
    day_type,
    campaign_group,
    COUNT(*) AS days,
    SUM(spend_usd) AS spend_usd,
    SUM(impressions) AS impressions,
    SUM(website_clicks) AS clicks,
    SUM(add_to_cart) AS carts,
    SUM(purchases) AS purchases,
    ROUND(CAST(SUM(website_clicks) AS REAL) * 100.0 / SUM(impressions), 3) AS ctr_pct,
    ROUND(CAST(SUM(purchases) AS REAL) * 100.0 / SUM(website_clicks), 2) AS click_to_purchase_pct,
    ROUND(CAST(SUM(spend_usd) AS REAL) / SUM(purchases), 2) AS cpa_usd
FROM vw_clean_paired_daily
GROUP BY day_type, campaign_group
ORDER BY day_type, campaign_group;


-- 5. Cumulative Performance & Rolling 7-Day Trend (SQL Window Functions)
DROP VIEW IF EXISTS vw_cumulative_trends;
CREATE VIEW vw_cumulative_trends AS
SELECT
    campaign_group,
    campaign_date,
    spend_usd,
    purchases,
    cpa_usd AS daily_cpa_usd,
    ctr_pct AS daily_ctr_pct,
    SUM(spend_usd) OVER (
        PARTITION BY campaign_group ORDER BY campaign_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_spend_usd,
    SUM(purchases) OVER (
        PARTITION BY campaign_group ORDER BY campaign_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_purchases,
    ROUND(
        CAST(SUM(spend_usd) OVER (
            PARTITION BY campaign_group ORDER BY campaign_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS REAL) /
        NULLIF(SUM(purchases) OVER (
            PARTITION BY campaign_group ORDER BY campaign_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ), 0), 2
    ) AS cumulative_cpa_usd,
    ROUND(
        CAST(SUM(spend_usd) OVER (
            PARTITION BY campaign_group ORDER BY campaign_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS REAL) /
        NULLIF(SUM(purchases) OVER (
            PARTITION BY campaign_group ORDER BY campaign_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 0), 2
    ) AS rolling_7d_cpa_usd
FROM vw_clean_paired_daily
ORDER BY campaign_group, campaign_date;