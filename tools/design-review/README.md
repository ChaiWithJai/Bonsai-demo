# A+ design-review tooling

This is the local error-discovery rig adapted from the Ray of Light design-review tool. It turns the real A+ production build into an annotatable screenshot atlas.

The atlas covers the homepage hero, lead magnet, method, proof, team and inquiry form. It also covers the full service-menu buying path, each offer, comparison, proof story, process, FAQs, order form and confirmation screen at desktop and mobile widths.

## Run a review

From the repository root:

```sh
npm run review
```

That command:

1. Builds the production site.
2. Captures 20 review surfaces at desktop and mobile sizes.
3. Builds `samples.json`.
4. Starts the local review app at <http://localhost:8377>.

To run each part separately:

```sh
npm run review:capture
npm run review:build
npm run review:serve
```

## Annotate

1. Open <http://localhost:8377>.
2. Choose a screen and viewport.
3. Drag a rectangle around anything that needs attention.
4. Write a plain note and press Enter.

Margin notes stay aligned with their rectangles. The Journey tab shows the complete page path by lane. The Progress tab groups categorized failure modes and holds agent suggestions that can be accepted or dismissed.

Annotations are written to `annotations.json` immediately and backed up in local storage. The server listens on `127.0.0.1`, so the review UI is available only on this computer.

## Files

| File | Role |
|---|---|
| `capture/capture.spec.ts` | Captures the A+ homepage, offers and confirmation surfaces |
| `capture/playwright.config.ts` | Runs desktop and mobile capture projects against the production preview |
| `build_samples.py` | Turns screenshots into the ordered sample manifest |
| `app.py` | Local stdlib server and JSON API |
| `index.html` | Rectangle annotation, journey and progress interface |

Generated review state is ignored by Git: `shots/`, `samples.json`, `annotations.json`, `patterns.json`, and `suggestions.json`.

To start a completely fresh review round, stop the server, remove those generated files and clear the `aplus-review-annotations-r1` local-storage key in the review browser.
