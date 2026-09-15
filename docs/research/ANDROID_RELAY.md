# Android offline and relay research

Accessed 2026-09-14. Findings below are sourced; design proposals are labelled decisions. Physical-device behaviour remains unverified.

| Option | Evidence | Decision / trade-off |
|---|---|---|
| Room + WorkManager | [Offline-first guide](https://developer.android.com/topic/architecture/data-layer/offline-first): local database is UI source; persistent work drains queues | Local-first writes, immutable UUID reports, unique constrained sync; no guarantee of instant execution |
| Bluetooth | [Permissions](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions): Android 12+ nearby runtime permissions; older discovery can need location | Direct Bluetooth adapter preserves open platform option; handle denied/revoked permission, never assume availability |
| Wi-Fi Direct | [P2P guide](https://developer.android.com/develop/connectivity/wifi/wifi-direct): socket communication needs INTERNET permission even offline; API 33+ NEARBY_WIFI_DEVICES | Higher-volume transport candidate; discovery/group lifecycle and OEM testing required; not a ready-made mesh |
| Nearby Connections | [Overview](https://developers.google.com/nearby/connections/overview), [setup](https://developers.google.com/nearby/connections/android/get-started): offline peer discovery/data; encrypted links; Google Play services dependency | Optional adapter, not core requirement or claim of open-source transport; easier connection handling but unavailable on some devices |
| Background relay | [Foreground-service restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start): API 31+ restricts background FGS starts; while-in-use permissions add restrictions | Relay is a visible, explicit field session. Do not promise invisible perpetual mesh. Service type/permissions need target-SDK verification |

## Protocol decision

Store-and-forward at application level: A creates immutable UUID payload; encrypt to organisation public key and sign origin envelope. B/C store opaque ciphertext before acknowledging custody. Final server receipt differs from neighbour custody ACK. Relay retention bounded by TTL, hop limit, byte quota and persistent seen-cache. Report identity independent of transport/source so repeated upload remains idempotent. Check immutable signed creation/expiry/max-hops and validate origin before acceptance; untrusted hop counters alone do not secure routing. Do not trust peer-supplied tenant ID to grant access.

First foundation: isolated pure protocol and Room queue. Hardware transports remain experimental until A→B→C with only C online is tested, including crash after receive, key revocation, expiry, repeated discovery and malicious payload. Native Bluetooth and Wi-Fi Direct remain required evaluation paths; Nearby cannot silently replace both. Test API 26/30/31/33/34/35/36 and current target on physical vendors, denied permission, screen-off, force-stop, battery restrictions, clock skew, no Play services. Re-check Android 17/local-network changes before raising target SDK.
