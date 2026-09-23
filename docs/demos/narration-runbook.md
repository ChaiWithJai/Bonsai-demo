# Produce Dolly narration

The six-language drafts are in `scripts/localizations.json`, paired with the
English masters. They are not native-speaker approvals. The scripts retain the
recorded numerical results, synthetic-case labels, and the limits of the
teacher-forced activation diagnostics.

Run `python3 scripts/produce_demo_narration.py` from the repository to regenerate
the 30-job queue and the local review page at
`.cache/demos/narration/review.html`. Planning makes no speech API calls.

Authentication belongs in the server environment or the ignored repository
`.env`: `AI_GATEWAY_API_KEY`, or supported Vercel OIDC authentication. The public
voice identifier must remain `BONSAI_DOLLY_VOICE_ID=ce3b16c14af54adebba5ebe50a3d4417`.
The adapter pins `fish-audio/s2.1-pro`. No alternate voice is substituted.

Begin with a single audio check:

```sh
python3 scripts/produce_demo_narration.py --execute --language zh --demo 01-bond-learning
```

After checking the actual voice, pronunciation, numbers, and timing, run the
remaining jobs with `--execute`. A valid completed job is reused only when its
request and audio hashes match. A provider or decoding failure stops the batch.
Do not treat a failed or timed-out request as proof that a provider did no work.
Inspect the saved queue before manually retrying.

Each successful job retains its request, model, voice, language, audio hash,
measured duration, and provider metadata. `human_reviewed` remains false. Duration
within 60–90 seconds is only a timing flag, not editorial approval. The program
does not stretch speech to fit the silent draft.

Next, review each recording, create captions aligned to the actual audio, check
Farsi right-to-left layout, and adjust the visual edit to match the narration.
The main cuts, short excerpts, and walkthroughs all still require their final
sound and synchronization pass. Neither placeholder audio nor an unrelated
voice can satisfy the requested delivery.

The retired `fish-audio/s2.1-pro-free` endpoint returned HTTP 404 during the
first authenticated pilot. The adapter now uses the paid `fish-audio/s2.1-pro`
endpoint. Fish infers language from input text and voice; its provider ignores
the SDK language option. Check each resulting language by listening.

The user approved longer cuts on September 23, 2026. Treat 60–90 seconds as
an initial editorial target, not a delivery gate. Preserve natural speech
speed and extend evidence holds or scene timing as needed for each language.
