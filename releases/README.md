# Android development build

`komsu-0.1-debug.apk` was assembled on 2026-09-15. Debug signing; synthetic development use only. SHA-256: `479DAD47869757D876EE0650B2D6E76B57600BB6A7D4E0EFCAB6394609E0ED5A`.

Validated: 4 app unit tests, 7 relay/crypto unit tests, 4 Room instrumentation tests on Pixel 7 / Android 14 emulator, and Android lint without errors. Tests cover queue reopen/claim recovery/fencing/tenant separation, cache replacement after case regrouping, authenticated encryption/signature tampering, durable relay custody across database reopen, and lossless Room v1→v2 migration.

Requires a configured Komşu API and initial login. Debug emulator URL: `http://10.0.2.2:8000`. Offline queue and three-language phrase text are available after provisioning. Relay storage and cryptographic primitives exist, but no Wi-Fi Direct/Bluetooth radio session, organization key distribution, recorded rescue audio, autonomous dispatch or field certification is included.
