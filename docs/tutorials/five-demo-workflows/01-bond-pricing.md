# A bond price starts with the payment schedule

The worksheet has a $1,000 bond, a 5% annual coupon, and ten years remaining. It also has the wrong payment count. Calculating a price from those inputs would preserve the mistake in a more convincing form.

In [Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo), the useful first response is a correction and a question. Semiannual payments mean 20 coupons of $25. The worksheet supplies no yield, so the user must confirm one before the calculator runs.

With a confirmed 5% yield, the price is $1,000. Raise the yield to 5.25% while keeping the payments fixed, and the price falls to $980.74. The interface lets the reader inspect how each payment contributes to that change.

![Edited bond-pricing cut at 00:51, showing a price of 980.74 after the yield increases to 5.25%.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/01-bond-pricing-cut.png)

Figure 1. Frame at 00:51 of the edited cut. The app result is a labeled held frame.

## Follow the calculation

| Check | Expected value |
| --- | ---: |
| Remaining payments | 20 |
| Coupon per payment | $25 |
| Final payment | $1,025 |
| Price at 5.00% annual yield | $1,000.00 |
| Price at 5.25% annual yield | $980.74 |
| Price change | -$19.26 |

The calculator discounts each payment at the annual nominal yield divided by two. For a payment in period `t`, use `cash_flow / (1 + yield / 2)^t`, then sum all 20 present values.

![Bonsai New chat displaying 20 payments, a 5.25% annual yield, a price of 980.74, and the final payment inspection.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/01-bond-pricing-app.png)

Figure 2. Recorded app state after repricing. The final payment is $1,025; its discounted value is $610.46 at the new yield.

## Try it in New chat

Use the branded recording UI with Bonsai 2 27B and the matching Prism runtime. Follow the [series setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/README.md#run-the-recording-ui). The stock chat page alone does not include every control shown here.

Use the synthetic [worksheet](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/evals/demos/bond/worksheet.svg). Open the SVG in a browser and save a screenshot as PNG for image attachment. The worksheet intentionally uses the wrong payment count and coupon amount. It is a teaching fixture, not a customer document.

1. Open **New chat**, then choose **Work through bond math**. Confirm that **Bonsai chat tools** is enabled in the composer tool selector.
2. Attach the worksheet image. Ask Bonsai to identify the variables, units, errors, and missing assumptions before calculating.
3. Check the proposed correction. A ten-year bond with two payments per year has 20 payments. A 5% annual coupon on a $1,000 face value pays $25 every six months.
4. Supply the missing yield and confirm the inputs with the message below.

```text
I confirm these inputs: face value 1000 USD, annual coupon rate 5%,
annual yield 5%, 20 remaining payments, 2 payments per year,
on a coupon date. Use calculate_bond once. Explain how the
payment schedule produces the present value.
```

5. In **Bond cash flows**, inspect the first payment and payment 20. The final payment contains the $25 coupon and $1,000 principal.
6. Expand **What if yield changes?** and move the yield change to +25 basis points. Keep the coupon schedule unchanged.

## Confirm the extraction before trusting the price

If the image is misread, enter the fields as text and confirm them before calling the calculator. Large images on Metal, Vulkan, and CPU are normally reduced to about 1,024 vision tokens, which can hide small writing. Review the original image rather than treating extraction as verified.

If the cash-flow card is missing, check that the branded UI is running and the model called `calculate_bond`. A prose price alone does not show that the calculator ran.

The [calculator](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/scripts/workspace_bond_math.py) handles regular fixed-rate bonds on coupon dates. It excludes accrued interest, irregular coupons, and embedded options. Treasury observations are a separate tool; the cut does not establish a Treasury-derived discount curve.

## What the recorded run proves

The [native image workflow record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/native-bond-image-evidence.json) preserves the correction, calculator response, and source hash. Confirmation in the recorded development run was automated, not a human approval label. Model wording may differ on a new run; the numeric checks should remain the same.

## Continue the review

- [Reconcile a leverage covenant](https://gist.github.com/ChaiWithJai/f66f84aab4141232083afab7254cfa38): check definitions before applying arithmetic.
- [Inspect a financial error](https://gist.github.com/ChaiWithJai/ae3046a50213aba9903838256cbec6a8): verify a numeric claim that follows a correct intermediate result.

<details>
<summary>Recording and source revision</summary>

Repository: [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo). Source revision: `bf425c5`. Companion cut: `01-bond-pricing-FINAL.mp4`, 70.6 seconds. Recorded September 23, 2026. The companion filename identifies the original edited cut; screenshots are pinned to the published repository assets.

</details>
