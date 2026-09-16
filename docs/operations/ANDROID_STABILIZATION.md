# Prompt 10 — Android stabilization checkpoint

Completed in this checkpoint:
- Demo login stores the server-advertised expiration with the encrypted token.
- Expired/rejected credentials stop automatic uploads; tenant identity and local reports remain.
- A renewed eligible field session resumes auth-blocked report/audio queues.
- The connection form restores the saved API address and rejects observer sessions for field ingress.
- Queue labels explain pending, sending, receipt-confirmed and conflicting reports in Turkish.
- A manual retry schedules existing reports with their original UUIDs; it does not create new copies.

The server remains authoritative for expiration/revocation. Unknown-lifetime opaque sessions
wait for a server rejection; the client does not invent an expiration time. The development
demo uses the advertised eight-hour lifetime. Reports can still be recorded offline after expiry.

Manual rehearsal on a disposable test phone:
1. Log in to the synthetic demo, enable airplane mode and save two text reports.
2. Force-stop/reopen and reboot: verify the same report IDs/texts remain queued.
3. Reconnect and retry: verify each report appears once in the web dashboard.
4. Let the session expire offline: verify records remain and a renewal notice appears.
5. Renew the same institution session: verify existing records resume without fresh IDs.
6. Switch institutions: verify only that institution's queue and cached cases are visible.
7. Create a deliberate UUID/content conflict in a local fixture API: verify no silent overwrite.
8. Test 200% font size, TalkBack, portrait/landscape and low-light contrast on physical devices.

Prompt 10 remains in progress. Next: versioned/checksummed TR/EL/EN phrase package,
safe professional audio-package validation/import and accessibility/layout checks.
No professional voice recordings or native-speaker acceptance have been supplied.
Do not label synthesized or unreviewed recordings as approved rescue instructions.
The free hosted demo uses text reports; durable audio storage/transcription is a separate pilot gate.
