# Frozen desktop regression inputs

The suite contains synthetic inputs from the dated-series and email-thread development experiments. Every file, request and expected value is checked in. The mailbox uses example.test addresses and contains no real correspondence.

Run commands from the repository root. Verify a source and print its frozen request without starting inference:

```sh
python3 scripts/workspace_regression_case.py --case email-thread
python3 scripts/workspace_regression_case.py --case dated-series
```

Upload the case file with the upload_name from suite.json, then use the exact request in that manifest. Record the new job and MLflow run IDs, model/runtime hashes, sampling configuration and harness commit. Preserve the first attempt before applying any correction. Confirming a development proposal must use an explicit development actor and must not create a human training label.

Check a saved compiled.json artifact:

```sh
python3 scripts/workspace_regression_case.py --case email-thread \
  --compiled /absolute/path/to/compiled.json --output /absolute/path/to/check.json
```

The command exits with status 1 when a checked contract fails. It requires the compiled source hash to match the frozen input, compares record values without depending on row order, retains duplicate counts, checks the expected field mapping and rejects excluded records. Numerically equal integers and floats compare equally. Booleans remain distinct. Expected field names are exact; a semantically equivalent renamed field needs review.

The original email proposal fails the view mapping check because it groups by review status. Its corrected proposal groups by project and passes. Both retain the same record values. The dated-series proposal passes these checks even though its original renderer joined the teams into one line. Rendering therefore still needs its separate series-count and browser checks.

The suite is a regression set developed after observing failures. It is not held-out evaluation, a measure of semantic accuracy, or a human-reviewed training dataset. A new configuration must also be tested on independent files with reviewed expectations. No inference is launched by the checker.
