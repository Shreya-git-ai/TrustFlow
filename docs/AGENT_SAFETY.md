# Assessment and evidence safety

## What the assessment can establish

The reviewer evaluates the milestone's saved acceptance criteria using the text in the latest evidence revision. Every criterion receives a finding and exact quotes supporting any `met` status. The report distinguishes observed facts from model inferences and lists missing proof and a recommended next step.

The report is decision support. Only the authenticated client can approve or request a revision. The backend requires a current successful report with every criterion marked `met` before it will record approval. Capture repeats the checks against durable PostgreSQL state and the PayPal authorization.

## What it cannot inspect today

- Reference links are validated and stored, but TrustFlow does not fetch them.
- PDF, PNG, JPEG, TXT, and CSV uploads are stored privately and can be downloaded by project members. TrustFlow does not extract text, run OCR, inspect images, or scan attachments for malware. File-only evidence is therefore insufficient for a text-based assessment.
- The prompt and submitted content are untrusted. The model is instructed to ignore instructions inside evidence and has no browsing, tool execution, approval, or payment capability.

The report calls out unverified links and uninspected attachments. A reviewer should request accessible text evidence when a criterion depends on those materials.

## Upload controls

The API limits request and decoded file size, allows only the documented file types, checks file signatures or text encoding, generates opaque storage names, writes files with private permissions, and serves them only after project-membership authorization. It never executes uploaded content. These controls validate format and access; they do not replace malware scanning.

## Payment safety

PayPal Sandbox is the default. The API rejects client-supplied approval flags. Order, authorization and capture identifiers are persisted, provider requests use durable idempotency keys, and verified webhook event IDs are deduplicated. If capture outcome is uncertain, the payment remains pending until a verified webhook or provider reconciliation confirms the result; the backend does not blindly retry capture. Authorization expiry must be present, parseable, and in the future before capture.

TrustFlow is not a legal escrow provider. A capture is reported only after PayPal returns or later confirms a completed capture with the expected amount and currency.
