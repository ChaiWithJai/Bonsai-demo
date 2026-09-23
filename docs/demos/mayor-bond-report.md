<!-- Bonsai-generated report; selected observations checked against saved Treasury results. -->

# Five-Mayor Bond Learning Report

**Purpose:** Teaching exercises linking NYC mayoral eras to *contextual* Treasury yields, not bond pricing inputs.

## Important caveats
- **No claim** that any mayor caused yield changes.
- Treasury par yields are **context only** — not spot rates, municipal rates, or NYC borrowing rates.
- Coupon/yield values in each exercise are **synthetic teaching assumptions**.
- Each context date is selected, not representative of the whole administration.

## Historical context (official daily Treasury par yields)

| Mayor (era) | Observation date | 10-year Treasury | Source |
|---|---|---|---|
| Giuliani (1994–2001) | 1994-01-03 | 5.92% | [Treasury XML 1994](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=1994) |
| Bloomberg (2002–2013) | 2008-09-15 | 3.47% | [Treasury XML 2008](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2008) |
| de Blasio (2014–2021) | 2020-03-16 | 0.73% | [Treasury XML 2020](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2020) |
| Adams (2022–2025) | 2022-06-15 | 3.33% | [Treasury XML 2022](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2022) |
| Mamdani (2026–present) | 2026-09-22 | 4.96% | [Treasury XML 2026](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2026) |

## Synthetic exercise assumptions (not historical rates)

Each: USD 1,000 face, 20 semiannual periods (10 years), no accrued interest/calls/default/tax effects.

| Exercise | Synthetic coupon | Synthetic yield | Target metric |
|---|---|---|---|
| Giuliani-v1 | 6.0% | 6.5% | price (USD) |
| Bloomberg-v1 | 5.0% | 4.0% | price (USD) |
| de Blasio-v1 | 4.0% | 2.0% | modified duration (years) |
| Adams-v1 | 4.0% | 5.0% | DV01 (USD/bp) |
| Mamdani-v1 | 5.0% | 5.5% | convexity (years²) |

Evidence links (MLflow/harness): each exercise's Treasury retrieval is saved; Giuliani: [sha256 a12b…53](http://127.0.0.1:5210/#/experiments/35/runs/abcc160ce218417198cfd54b031ae1dc).

---

## Now the Giuliani exercise — your turn

**Question:** Calculate the price and show your formula and units.

**Inputs (confirm before solving):**
- Face: **1,000 USD**
- Coupon rate: **6.0% p.a.** → coupon per period = 1,000 × 0.06 ÷ 2 = 30 USD every 6 months
- Annual yield: **6.5% p.a.** → per-period yield = 0.065 ÷ 2 = 3.25%
- Periods: **20** (semiannual, `frequency = 2`)
- No accrued interest

**Formula:** Price = Σ [C ÷ (1 + y/m)^t], t = 1…20, plus F ÷ (1 + y/m)^20.

Reply with your numeric answer, units, and working.