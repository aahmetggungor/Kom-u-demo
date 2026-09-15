# ADR-006: Isolated, explicit store-and-forward relay sessions

Context: FUNC-013 requires Bluetooth/Wi-Fi Direct multi-hop; neither is automatically a disaster mesh.

Decision: transport-neutral signed/encrypted immutable envelope, durable custody, UUID/expiry/hops/seen-cache. Native Bluetooth and Wi-Fi Direct adapters evaluated on physical devices; optional Nearby adapter only behind same port. See research/ANDROID_RELAY.md for current official constraints.

Alternatives: Nearby simplifies links but adds Play services; Wi-Fi-only excludes devices; background perpetual discovery conflicts with battery/platform constraints.

Consequences: more protocol work and explicit user session. No silent permission requests or claims of working hardware relay from unit tests. Revocation when offline and malicious hops remain risk; ciphertext quotas, bounded TTL and final server receipts reduce abuse. Scale via small manifests and bounded custody, no broadcast of raw PII.
