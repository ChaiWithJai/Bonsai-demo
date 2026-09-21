# Multiple files for one question

Workspace accepts up to 20 original files per question. Each file is extracted separately. The collection retains original record identifiers and filenames, and the proposal job archives every original byte stream with its checksum. Collections are immutable snapshots. Applying human corrections creates a different snapshot and does not rewrite originals.

Email exports in EML and MBOX format expose message headers, bodies, dates, and thread identifiers. HTML is converted to text without fetching resources. Attachments are listed but their contents are not extracted. Generic text and JSON remain supported; no dedicated phone-message export adapter is claimed.

The conversation still stops at a proposal. The user can request a change or confirm the exact proposal version before rendering. The real 79-page PDF proposal remains awaiting confirmation. No model inference or human confirmation was performed for this implementation check.

Validation: 158 Python tests passed, Svelte reported zero errors and warnings, the production build passed, and four desktop/mobile browser checks passed. The browser checks attached existing original files and removed them without creating model jobs. Unit tests cover mixed email/table collections, original integrity, corrections, email parsing, and archiving originals into proposal jobs. These checks do not establish multi-file model quality or held-out reliability.

Remaining: fetch intake, dedicated message formats, richer document/media extraction, durable team identity and collaboration, and a validated training loop. Existing review events are evidence, not completed model training.

The previous full backup attempt failed with disk exhaustion. Three disposable restore-check directories were removed only after checking that their verified MongoDB archives still existed. Original archives and the most recent verified restore were retained. A new checkpoint and backup attempt follow this change.
