# Phase 3: Statistical Hypothesis Testing & Executive Decision Memo

## Executive Verdict: DO NOT SHIP Test Campaign As-Is (Adopt Hybrid Strategy)

Across **29 strictly matched calendar days** (excluding `2019-08-05` from both groups to fix Control's missing funnel log), the Test campaign spent **+11.6% more** (`$74,595` vs `$66,818`) while generating **-1.9% fewer purchases** (`14,869` vs `15,161`). True Blended CPA deteriorated by **+$0.61 (+13.8%)** from `$4.41` to `$5.02`.

## 1. Block Bootstrap Analysis on Blended Ratio Metrics (10,000 Paired-Day Resamples)

| Blended Metric | Control | Test | Diff (Test - Ctrl) | 95% Bootstrap CI | Bootstrap p-value | Business Takeaway |
| :--- | ---: | ---: | ---: | :---: | ---: | :--- |
| **Blended CPA ($/Order)** | $4.41 | $5.02 | **+$0.61 (+13.8%)** | `[$-0.35, $+1.70]` | 0.2274 | Test has a **88.6% probability** of higher CPA |
| **Blended CPM ($/1k Imp)** | $21.03 | $35.13 | **+$14.10 (+67.1%)** | `[$+9.48, $+20.15]` | 0.0000 | Test inventory is significantly more expensive |
| **Click-to-Purchase (%)** | 9.83% | 8.49% | **-1.33 pp** | `[-3.84, +0.86]` | 0.2406 | Lower on-site conversion per click in Test |

## 2. Paired Daily Hypothesis Tests (Unit of Analysis = Matched Day, n=29)

| Daily Metric (n=29 paired days)   |   Control Mean |   Test Mean |   Mean Diff (T-C) | 95% Boot CI            | Paired t p-val   | Wilcoxon p-val   | Sig (95%)   |
|:----------------------------------|---------------:|------------:|------------------:|:-----------------------|:-----------------|:-----------------|:------------|
| Daily Spend (USD)                 |        2304.07 |     2572.24 |            268.17 | [+78.44, +455.48]      | 0.0108           | 0.0243           | Yes         |
| Daily Impressions                 |      109560    |    73215.5  |         -36344.3  | [-49949.51, -22121.55] | <0.0001          | <0.0001          | Yes         |
| Daily Website Clicks              |        5320.79 |     6038.17 |            717.38 | [-188.70, +1609.35]    | 0.1321           | 0.1260           | No          |
| Daily Add to Cart                 |        1300    |      878.97 |           -421.03 | [-608.72, -221.79]     | 0.0003           | 0.0006           | Yes         |
| Daily Purchases                   |         522.79 |      512.72 |            -10.07 | [-105.11, +82.01]      | 0.8380           | 0.9637           | No          |
| Daily CPA (USD)                   |           5.05 |        6    |              0.95 | [-0.24, +2.23]         | 0.1521           | 0.4047           | No          |
| Daily CTR (%)                     |           5.1  |       10.42 |              5.32 | [+2.97, +8.11]         | 0.0004           | <0.0001          | Yes         |
| Daily View-to-Cart (%)            |          77.79 |       49.44 |            -28.34 | [-44.15, -13.35]       | 0.0013           | 0.0009           | Yes         |
| Daily Cart-to-Purchase (%)        |          45.72 |       61.16 |             15.44 | [+3.39, +25.41]        | 0.0124           | 0.0022           | Yes         |
| Daily Click-to-Purchase (%)       |          11.48 |        9.1  |             -2.38 | [-5.43, +0.41]         | 0.1316           | 0.3250           | No          |

## 3. Macro Funnel Two-Proportion Z-Tests (Aggregate Event Volume)

> *Note: Pooled Z-tests on millions of events treat clicks/impressions as independent and yield tiny p-values; we pair them with daily-level & block-bootstrap tests above to prevent pseudoreplication.*

| Metric                       |   Control (%) |   Test (%) |   Abs Diff (pp) |   Rel Lift (%) |   Z-Stat | p-value   | Significant (95%)   |
|:-----------------------------|--------------:|-----------:|----------------:|---------------:|---------:|:----------|:--------------------|
| CTR (Clicks / Impressions)   |         4.857 |      8.247 |           3.391 |          69.82 |   158.44 | <0.0001   | Yes                 |
| Click -> Search              |        41.748 |     40.24  |          -1.508 |          -3.61 |    -8.78 | <0.0001   | Yes                 |
| Search -> View Content       |        87.507 |     77.888 |          -9.619 |         -10.99 |   -46.42 | <0.0001   | Yes                 |
| View Content -> Add to Cart  |        66.88  |     46.445 |         -20.434 |         -30.55 |   -68.79 | <0.0001   | Yes                 |
| Add to Cart -> Purchase      |        40.215 |     58.333 |          18.118 |          45.05 |    44.74 | <0.0001   | Yes                 |
| Click -> Purchase (Site CVR) |         9.825 |      8.491 |          -1.334 |         -13.58 |   -13.27 | <0.0001   | Yes                 |
| Impressions -> Purchase      |         0.477 |      0.7   |           0.223 |          46.76 |    33.54 | <0.0001   | Yes                 |

## 4. Financial Opportunity & Budget Reallocation Sizing

- **Direct Budget Waste Avoided:** Running Test's `14,869` orders at Control's `$4.41` CPA saves **$9,064 per 29 days (~$114,080/year annualized)**.
- **Volume Upside at Constant Budget:** Reallocating Test's `$74,595` spend to Control's efficiency yields **~16,926 orders** (**+2,057 incremental orders/month**, or **+25,885 orders/year**).
- **Next-Iteration Hypothesis (Hybrid Win):** Test's ad creative achieved **+69.8% CTR** and its checkout converted **58.3% of carts** (vs 40.2% in Control), but suffered a **-20.4 pp View-to-Cart drop** and **+67% CPM**. Run a follow-up A/B test combining **Control's lower-CPM bidding strategy** with **Test's high-CTR creative + streamlined checkout**, while auditing product-page-to-cart friction.