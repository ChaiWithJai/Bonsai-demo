# Bond math workstream

Status: proposed implementation, September 23, 2026. This document describes required behavior, not completed functionality.

## User and outcome

Jai wants to learn bond math by working through a problem on a whiteboard, turning his reasoning into explicit inputs and equations, and checking it against current Treasury data. The product lives as a feature available from New chat in Bonsai-demo. The first result someone can share is a view that connects his original working, a confirmed cash-flow schedule, and a verified price calculation.

## Visual interaction

1. Open New chat and choose the bond-math feature and attach a whiteboard photo, or enter the same working as text. Keep the original image visible beside the conversation.
2. Local Bonsai proposes the face value, coupon rate, coupon frequency, maturity, settlement assumption, yield convention, and equation. Each extracted field points back to its source. Highlight unreadable symbols and unresolved units. Ask Jai to correct and confirm the inputs before calculating.
3. Fetch the latest available Treasury observations on demand. Show the observation date separately from the fetch time, preserve the response and its hash, and disclose stale or unavailable data. Daily published observations are not real-time tradable quotes.
4. Draw the payment schedule and the price-versus-yield curve. Clicking a payment highlights its discount factor, contribution to price, and matching equation term. Let Jai predict the direction and size of a price change before revealing the computed result.
5. Allow a yield change in basis points. Show the exact repriced value, a duration approximation, and the approximation error. Explain a discrepancy by highlighting the affected inputs or equation terms, then offer another problem.
6. Save the original attempt, corrections, source snapshot, calculation version, and reviewed result in the workstream. Human learning feedback and model-training labels are separate records.

## Calculation contract

Begin with a fixed-rate, option-free bond valued on a coupon date with regular semiannual payments. For face value F, annual coupon rate c, annual nominal yield y, m payments per year, and N remaining payments, calculate C = F*c/m and P = sum(C/(1+y/m)^k, k=1..N) + F/(1+y/m)^N. Rates are decimals internally. One basis point is 0.0001. Display currency and precision explicitly.

Use deterministic calculation code as the numerical authority. Verify par pricing when coupon equals yield, zero-yield pricing, principal repayment, and the inverse price/yield relationship. Compare analytic duration with a finite-difference check. Irregular coupons, accrued interest, clean versus dirty price, day-count conventions, bills, TIPS, and callable bonds require separate explicit conventions before support is claimed.

Treasury par yields provide market context and a clearly labeled teaching scenario. Do not use par yields as spot discount factors or imply that a par-curve observation is the executable yield of a specific security. A future term-structure exercise must document interpolation and bootstrapping separately.

## Existing harness and integration

Keep the Svelte workstreams, Python job records, source store, confirmation step, generated-view checks, and MLflow traces. Local Bonsai handles whiteboard interpretation and explanation. Add a server-side Jev adapter through Vercel AI Gateway, pinned to `typesafe-ai/jev`, for bounded classifications such as unresolved assumptions and next exercise category. A Jev decision is not a mathematical proof. No other cloud reasoning model is a fallback.

The Treasury adapter acquires data and records provenance. The renderer shows the confirmed data and deterministic results. Neither Jev nor a generated UI may silently change the confirmed inputs. The first release formalizes working into a typed calculation specification; it must not claim theorem-prover verification.

## Acceptance and proof shot

From a fresh workstream, complete image/text intake, correction, dated Treasury fetch, checked calculation, interactive repricing, and saved review. Refreshing the browser must preserve progress without repeating inference. The closing shot shows original working, confirmed assumptions, payment contributions, total price, and source date together. Include one deliberately incorrect student step, clearly labeled as an exercise, and demonstrate the correction without inventing a model failure.

## References

- Treasury feed contract: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed
- Treasury interest-rate files: https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/interest-rate-xml-files
- Jev integration: https://vercel.com/i/jev-integrations
