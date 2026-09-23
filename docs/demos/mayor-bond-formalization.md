# Camera notes to a checked bond exercise

Use **New chat → Work through bond math**. This enables Bonsai chat tools,
Treasury Insights, and GB10 Vision in the native MCP selector. No separate task
screen is required. Camera capture happens only through an explicit tool call.

Try: “Capture my GB10 whiteboard once. Tell me what you can read, then ask me to
confirm the variables. Make a report comparing the five mayor-era exercise
contexts, and quiz me one exercise at a time.”

## What formalization means here

Bonsai proposes a question, variables with units, source passages or image
locations, assumptions, unresolved readings, formulas, and checks. The user
confirms the interpretation in chat before calculation. Numerical tools compute
the results; the model explains them. The answer checker records the submitted
number, units, expected value, tolerance, and result. A numerical pass does not
verify the reasoning or the accuracy of handwritten transcription.

This is executable numerical checking, not a proof-assistant implementation.
[Vinod Khosla’s May 25 post](https://x.com/vkhosla/status/2058976857345954154)
endorses work on verification and autoformalization by quoting a verification
summit announcement. The workflow above is our implementation choice, not a
method specified by that post.

## Tools and deployment

- `/api/gb10-vision`: three MCP tools, `list_cameras`, `get_camera_status`, and
  `capture_frame`. The app backend connects through the existing `gb10` SSH alias
  and executes `~/.local/share/bonsai-vision/gb10_vision_mcp.py`. Credentials remain
  in server SSH configuration. The script captures one JPEG using GStreamer,
  releases the device, and preserves the image hash and UTC capture time on GB10.
- `/api/treasury-insights`: `get_curve(date)` and
  `get_rate_history(start, end, tenor)`. This wraps the repository’s official
  Treasury adapter. It does not claim to be a separately installed external MCP.
  Exact dates stay exact, unavailable dates stay missing, and each retrieval
  preserves the raw source, hash, retrieval time, and MLflow evidence link.
- `/api/bonsai-tools`: existing bond calculations plus `prepare_mayor_report()` to gather all five contexts, `mayor_exercise(era)`, and
  `grade_mayor_exercise(era, answer, unit)`. Exercise and grading actions use the
  existing harness persistence and MLflow integration.

Deploy the camera script to GB10 with `scp`; no camera HTTP port is opened there.
The app server needs the configured SSH alias and GStreamer must have access to
the selected video device. Hosted deployments need a private route to GB10; a
public browser cannot directly use the development machine’s SSH configuration.
The current local path is tested independently of any cloud deployment.

## Exercise pack

[NYC’s official mayor list](https://www.nyc.gov/site/dcas/about/green-book-mayors-of-the-city-of-new-york.page),
checked September 23, 2026, supplies administration periods. Each exercise uses a
synthetic USD 1,000 face bond with 20 remaining semiannual payments on a coupon
date. Coupons and yields are deliberately explicit teaching inputs. They are
**not historical NYC bond terms**. Selected dates provide Treasury context only.

| Mayor | Period | Selected context date | Exercise | Coupon / yield assumptions |
|---|---|---|---|---|
| Giuliani | 1994–2001 | 1994-01-03 | Price | 6% / 6.5% |
| Bloomberg | 2002–2013 | 2008-09-15 | Price | 5% / 4% |
| de Blasio | 2014–2021 | 2020-03-16 | Modified duration | 4% / 2% |
| Adams | 2022–2025 | 2022-06-15 | DV01 | 4% / 5% |
| Mamdani | 2026 onward | 2026-09-22 | Convexity | 5% / 5.5% |

Treasury par yields are neither municipal yields nor discount spot curves.
These dates do not summarize whole administrations or show mayoral causation.
Actual city debt service or refunding analysis requires offering documents,
call terms, dated cash flows, transaction costs, and city fiscal records. Those
are not silently invented by this starter pack.

## Review loop

1. Capture or attach evidence. Preserve the original.
2. Show a structured interpretation and unresolved values.
3. Confirm assumptions and the chosen question in chat.
4. Retrieve Treasury context with provenance and calculate separately.
5. Produce a report with historical observations separated from assumptions.
6. Ask one exercise, wait for an answer, then grade the number and units.
7. Preserve corrections and review status. Do not convert an automated test
   into a human-reviewed training example.

The bond starter uses Low reasoning (512 tokens) when the current preference is
Default. An explicit Off, Low, Medium, High, or Max choice is preserved. This
sets the pending chat preference without writing a persistent global default.
The first report test exhausted its 180-second wait in reasoning; its original
trace is retained in `mayor-report-reasoning-evidence.json` for comparison.
