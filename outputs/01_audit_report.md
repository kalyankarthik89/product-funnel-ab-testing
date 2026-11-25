# Phase 1: Raw Data & Experiment Health Audit

### Control Group (`control_group.csv`)
- **Detected Delimiter:** `;`
- **Shape:** 30 rows × 10 columns
- **Columns:** ['Campaign Name', 'Date', 'Spend [USD]', '# of Impressions', 'Reach', '# of Website Clicks', '# of Searches', '# of View Content', '# of Add to Cart', '# of Purchase']
- **Exact Duplicate Rows:** 0
- **Missing Values Found:**
  - `# of Impressions`: 1 missing (3.3%)
  - `Reach`: 1 missing (3.3%)
  - `# of Website Clicks`: 1 missing (3.3%)
  - `# of Searches`: 1 missing (3.3%)
  - `# of View Content`: 1 missing (3.3%)
  - `# of Add to Cart`: 1 missing (3.3%)
  - `# of Purchase`: 1 missing (3.3%)
  - **Affected Dates:** ['5.08.2019']
- **Date Range:** 2019-08-01 to 2019-08-30 (30 unique days)
- **Duplicate Dates:** 0
- **Funnel Logic Anomalies:** Purchase > Add to Cart: 1 day(s)
- **Statistical Outliers (1.5×IQR):** None

### Test Group (`test_group.csv`)
- **Detected Delimiter:** `;`
- **Shape:** 30 rows × 10 columns
- **Columns:** ['Campaign Name', 'Date', 'Spend [USD]', '# of Impressions', 'Reach', '# of Website Clicks', '# of Searches', '# of View Content', '# of Add to Cart', '# of Purchase']
- **Exact Duplicate Rows:** 0
- **Missing Values:** None (0 nulls)
- **Date Range:** 2019-08-01 to 2019-08-30 (30 unique days)
- **Duplicate Dates:** 0
- **Funnel Logic Anomalies:** None detected
- **Statistical Outliers (1.5×IQR):** None

### Cross-Group Experiment Alignment
- **Matching Dates:** 30 days
- **Only in Control:** []
- **Only in Test:** []

### Raw Metric Totals (Before Cleaning)
| Metric | Control Total | Test Total | Raw Diff |
| :--- | ---: | ---: | ---: |
| Spend | 68,653 | 76,892 | +12.0% |
| Impression | 3,177,233 | 2,237,544 | -29.6% |
| Reach | 2,576,503 | 1,604,747 | -37.7% |
| Click | 154,303 | 180,970 | +17.3% |
| Search | 64,418 | 72,569 | +12.7% |
| View | 56,370 | 55,740 | -1.1% |
| Cart | 37,700 | 26,446 | -29.9% |
| Purchase | 15,161 | 15,637 | +3.1% |