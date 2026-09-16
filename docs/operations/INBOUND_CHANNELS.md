# External inbound channels — development contract

SMS, messaging, social and phone gateways POST to /api/v1/inbound/{connector_id}.
This is a vendor-neutral development contract. No live provider account is connected.
Provider-specific signing/normalization must run in a trusted gateway; vendor webhooks
must not be pointed directly at this endpoint assuming compatible signatures.

Configure KOMSU_CHANNEL_CONNECTORS as a JSON array in a secret store. Each connector
has connector_id, tenant_id, actor_id, source, secret (32–256 characters) and
requests_per_minute. Actor membership must belong to that tenant and permit ingress.
Neither tenant nor actor identity is accepted from the message body. Do not put
connector secrets in GitHub, logs, URL parameters or browser code.

Body: delivery_id, external_id, text, received_at (timezone required), language
(tr/el/en/und), optional address_raw, location and original_report_id. The last field
preserves a known original report UUID across relay channels; otherwise the gateway
namespace and external message ID determine it. Phone alone may carry audio_wav_base64:
mono 16-bit PCM WAV at 16 kHz, 0.2–30 seconds, within configured upload limits.
Audio is encrypted and quarantined; receipt acceptance does not approve transcription.

Sign the exact request bytes using HMAC-SHA256(secret, ASCII(timestamp) + '.' + body).
Send lowercase hex in X-Komsu-Signature and Unix seconds in X-Komsu-Timestamp.
Timestamp tolerance is five minutes; retries re-sign the unchanged body with fresh time.
Initial acceptance is 202; identical delivery replay is 200. A reused delivery ID
with different bytes is 409. New delivery IDs with unchanged source message identity
reuse the report. Rejected signed payloads return 422 and retain only hashed IDs,
body checksum and bounded error code as a dead letter; raw payloads are not retained.
Invalid signatures return 401. Quota returns 429; queue/config outage returns 503
with Retry-After, without permanently rejecting a recoverable delivery.

PostgreSQL transaction locks serialize inbound requests per tenant. Report, job,
encrypted audio and accepted receipt commit together. The quota is durable across
replicas and includes rejected signed deliveries. Identical retries do not spend quota.
Retention removes matching receipts; receipts do not extend the original report lifetime.

Local simulator: set KOMSU_CONTRACT_CONNECTOR and KOMSU_CONTRACT_SECRET privately,
then run python -m uvicorn scripts.inbound_contract_server:create_app --factory
--host 127.0.0.1 --port 8011 --no-access-log. POST /deliver/tr, /deliver/el or /deliver/en.
The target defaults to local port 8000 and rejects external destinations. Fixtures in
data/inbound.synthetic.json contain only synthetic reports. No provider send API is used.

Before a live sandbox: supply chosen provider, test account, webhook signing reference,
registered sender/number, consent and retention rules, network restrictions, secret
rotation mechanism and sandbox fixtures. Real messages require separate explicit approval.
