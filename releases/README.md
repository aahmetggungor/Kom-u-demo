# Android development build

**Current hosted demo: [Download 0.1.1 APK](https://github.com/aahmetggungor/Kom-u-demo/releases/download/demo-v0.1.1/komsu-demo-v0.1.1.apk)** — [Release notes](demo-v0.1.1.md) — [Usage guide](../docs/DEMO_GUIDE.md).

The file below is an older local-API development build; use GitHub Releases for the hosted demo. Development is paused at demo-v0.1.1 (2026-09-18).

`komsu-0.1-debug.apk` was assembled on 2026-09-15. Debug signing; synthetic development use only. SHA-256: `C544D01C292711ABC49BB014298B9A4D3567E48529C5A7C6A3EF919077313855`.

Validated: 6 app unit tests, 7 relay/crypto unit tests, 6 Room instrumentation tests on Pixel 7 / Android 14 emulator, and Android lint without errors. Tests cover WAV bounds/silence, HTTP status policy, report/audio queue reopen/claim recovery/fencing/tenant separation, cache replacement, authenticated encryption/signature tampering, durable relay custody and lossless Room v1→v2→v3 migration.

Requires a configured Komşu API and initial login. Debug emulator URL: `http://10.0.2.2:8000`. Offline text/audio queue, explicit microphone permission, bounded recording controls and three-language phrase text are available after provisioning. Physical-device microphone/airplane-mode evidence, Wi-Fi Direct/Bluetooth radio sessions, organization key distribution, recorded phrase audio, autonomous dispatch and field certification are not included.
