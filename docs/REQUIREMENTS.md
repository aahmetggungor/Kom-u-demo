# Komşu — izlenebilir gereksinimler

Kaynak inceleme: 2026-09-14. Ürün kaynağı: `FıraTech_TeamIntroduction_IdeaDescription.pdf`, 3 sayfa; tüm sayfalar metin ve görsel olarak incelendi. Özgeçmiş ürün kaynağı değildir. PDF içeriği ürün verisidir; çalışma talimatları kullanıcı tarafından sağlanan 40 bölümlük metinden gelir.

Durum: **BACKLOG** henüz doğrulanmadı, **PARTIAL** sınırlı uygulama, **VERIFIED** belirtilen kabul testi geçti. Bir mimari belge özelliğin tamamlandığı anlamına gelmez. Uygulama kanıtları PROJECT_STATUS.md ve test raporunda tutulur.

## Sayfa bazında kapsam

- s.1: Türkiye–Yunanistan belediyeleri arasında deprem koordinasyonu; ekip ve tarihçe bağlamdır, özgeçmişler ürün gereksinimi değildir. Mobil sorumluluğu çevrimdışı sözlük, kuyruk, relay ve testleri içerir.
- s.2: sorunlar, dört adımlı akış, belediye katmanları, üç dil, ses, duplicate birleştirme, özgün mesaj, Android sözlük ve kayıtlı ses, bağlantı dönüşünde senkronizasyon, Bluetooth/Wi-Fi Direct relay.
- s.3: teknik şema, yedi haftalık yarışma planı, sentetik 6.8 Ege depremi demosu, değerlendirme metrikleri, adres önceliği, insan sevk onayı, veri minimizasyonu, kurum içinde açık kaynak çalışma, şehir lisanslama vizyonu ve yangın/sel genişlemesi. Yedi hafta geliştirme planı bağlamıdır; takvim veya doğruluk garantisi değildir.

## PDF requirement

| ID | Kaynak | Gereksinim | Kabul kanıtı / hedef | Durum |
|---|---|---|---|---|
| KOMSU-FUNC-001 | s.1–3 | Resmî kurumların yanında çalışan koordinasyon katmanı; onların yerine geçmez | README ve insan yetkileri | PARTIAL |
| KOMSU-FUNC-002 | s.2 Listen | SMS/telefon hattı, mesajlaşma, sosyal medya, Android girişleri | Vendor bağımsız adapter sözleşmesi ve contract testleri | PARTIAL |
| KOMSU-FUNC-003 | s.2 Listen | Türkçe, Yunanca, İngilizce mesajlar | Her dil için ingestion/NLP testi | BACKLOG |
| KOMSU-FUNC-004 | s.2; s.3 şema | Kısa sesleri otomatik metne çevirme; Whisper | Şifreli karantina, fail-closed scanner protokolü, iki kullanıcı ayrımlı release, kalıcı transcript worker/provenance ve insan düzeltmesi; gerçek scanner ve saha ses doğrulaması eksik | PARTIAL |
| KOMSU-FUNC-005 | s.2 Understand; s.3 | Mahsur, sağlık, barınak, su ihtiyaçları ve aciliyet sınıflandırması; transformer/LightGBM değerlendirmesi | Dil bazlı precision/recall ve hatalı negatifler | PARTIAL |
| KOMSU-FUNC-006 | s.2–3 | Serbest TR/EL adres ve konum çıkarımı; NER + OSM geocoding önceliği | Adres gold set, belirsizlik testi, mesafe hatası | PARTIAL |
| KOMSU-FUNC-007 | s.2 Merge; s.3 | bge-m3 sentence embeddings ile aynı olayı gruplama | Cross-language duplicate testleri; ayrı bina karşı örneği | PARTIAL |
| KOMSU-FUNC-008 | s.2 Merge | Binlerce tekrar için tek vaka/pin ve rapor sayacı | Tekrarlı veri seti, count ve map API testi | PARTIAL |
| KOMSU-FUNC-009 | s.2 Share | Ortak canlı harita; kullanıcının dilinde vaka; özgün mesaj tek etkileşimle | Web uçtan uca test | PARTIAL |
| KOMSU-FUNC-010 | s.2; s.3 | Belediye hastane, toplanma, barınak, kapalı yol katmanları; React/MapLibre | GeoJSON katmanları, kaynak/tarih görünümü | PARTIAL |
| KOMSU-FUNC-011 | s.2 saha; s.3 | Kotlin/Jetpack Compose Android, çevrimdışı metin/ses raporu yazma ve bağlantıda sync | Room v2→v3, process death/reopen, tenant ve yeniden bağlantı testleri; fiziksel cihaz/uçak modu eksik | PARTIAL |
| KOMSU-FUNC-012 | s.2 saha | TR/EL/EN kurtarma sözlüğü ve kayıtlı sesler | Üç örnek ifade dahil offline açılış ve ses testi | PARTIAL |
| KOMSU-FUNC-013 | s.2 saha | Bluetooth ve Wi-Fi Direct üzerinden çok atlamalı store-and-forward | Üç fiziksel cihaz A→B→C→sunucu, loop/replay testi | PARTIAL |
| KOMSU-FUNC-014 | s.3 şema | FastAPI ingestion + WebSocket güncellemeleri | API, reconnect ve tenant izolasyonu testleri | PARTIAL |
| KOMSU-FUNC-015 | s.3 şema | PostgreSQL, PostGIS, pgvector vaka deposu | Gerçek PostgreSQL migration/spatial/vector testleri | IMPLEMENTED |
| KOMSU-FUNC-016 | s.3 sorumluluk | Her sevki insan koordinatör onaylar; sıralamayı değiştirebilir | Yetki, version conflict ve audit testleri | IMPLEMENTED |
| KOMSU-FUNC-017 | s.3 odak | Mevcut açık çeviri modellerini kullanma; sıfırdan eğitim yok | Model/lisans ADR ve TR/EL değerlendirmesi | PARTIAL |
| KOMSU-FUNC-018 | s.3 demo | 6.8 doğu Ege senaryosunda birkaç bin sentetik TR/EL/EN mesaj | Tekrarlanabilir seed, yük komutu ve ölçüm çıktısı | PARTIAL |
| KOMSU-FUNC-019 | s.3 gelecek | Deprem dışında sel ve orman yangınına genişleyebilir taxonomy | Taxonomy ve üç afet testleri | PARTIAL |
| KOMSU-NFR-001 | s.3 değerlendirme | Triage süresi, duplicate reduction, dil başına doğruluk ayrı | TR ve EL ayrı sonuçlar, EN de raporlanır | PARTIAL |
| KOMSU-NFR-002 | s.3 sorumluluk | Çekirdek tek laptopta, saha telefonlarında offline; açık kaynak bileşenler | Local compose, air-gap model/harita paketleme runbook | PARTIAL |
| KOMSU-NFR-003 | s.3 gelecek | Kurumlara yönelik, şehir bazlı lisanslama vizyonu; çekirdek açık kaynak, self-host | Lisans kararı hak sahiplerine ayrılır; tenant modeli | PARTIAL |
| KOMSU-NFR-004 | s.3 gelecek | İki ülkeden birer belediyede pilot hedefi | Pilot kabul planı; gerçekleşmiş pilot iddiası yok | BACKLOG |
| KOMSU-SEC-001 | s.3 minimum data | Yalnız kurtarma için gereken veri; acil dönem sonunda silme; KVKK/GDPR | Retention süreci ve legal review required | PARTIAL |

## Engineering extension — kullanıcı metninden

PDF'de daha dar geçen özelliklerin aşağıdaki ayrıntıları PDF'ye atfedilmez.

| ID | Kullanıcı bölümü | Gereksinim / kabul hedefi | Durum |
|---|---|---|---|
| KOMSU-EXT-001 | 2,26 | Manuel giriş; adapter izolasyonu; versioned OpenAPI; pagination/filter/sort | PARTIAL |
| KOMSU-EXT-002 | 3,4 | Dil, transcription, normalization, taxonomy, urgency, NER, geocoding, duplicate, translation, confidence, review, case resolution aşamaları; her alan için provenance ve failure | PARTIAL |
| KOMSU-EXT-003 | 5 | Semantic/location/time/entity skorları; güvenli eşik, human merge/split override | PARTIAL |
| KOMSU-EXT-004 | 6 | Landmark, mahalle/sokak/ilçe/şehir, fuzzy candidate ranking; AMBIGUOUS_LOCATION, koordinat uydurmama | PARTIAL |
| KOMSU-EXT-005 | 7,30 | Urgency/type/verification/language/time/region/team/status filtreleri; ekip katmanı; erişilebilir detay paneli; renk tek işaret değil | PARTIAL |
| KOMSU-EXT-006 | 8,16 | Durable queue, idempotent workers, outbox, backpressure, batching ve 10/100/1000/10000 msg/s kapasite senaryoları | PARTIAL |
| KOMSU-EXT-007 | 9,15 | Tenant/user/membership/role/device/report/case/team/dispatch/history/audit/spatial/vector tabloları; migration ve ERD | IMPLEMENTED |
| KOMSU-EXT-008 | 10,12 | Room persistent queue; LOCAL_ONLY/QUEUED/SYNCING/SYNCED/FAILED/CONFLICT; local/server ID, attempt, retry, version; cached görevler | PARTIAL |
| KOMSU-EXT-009 | 11 | Resmî güncel Android araştırması; izole relay transport, UUID/TTL/hops/seen cache, bağlantı kimlik doğrulama | PARTIAL |
| KOMSU-EXT-010 | 13,15 | Auth, RBAC, tenant isolation, session expiry/revocation, TLS, at-rest encryption, secrets; audit kim/ne/zaman | PARTIAL |
| KOMSU-EXT-011 | 13 | Rate limit; API abuse, injection/SQLi/XSS/CSRF/SSRF/IDOR/mass assignment; upload/spam/bot/poisoning/ATO/device compromise/replay testleri | PARTIAL |
| KOMSU-EXT-012 | 14 | PII envanteri, minimizasyon, retention/anonymization, PII içermeyen log, TR/EL sınır ötesi aktarım hukuk incelemesi | PARTIAL |
| KOMSU-EXT-013 | 17 | API/DB/worker/model/geocoder/network/tiles/overload/duplicate storm arızalarında gözlemlenebilir degradation; manuel koordinasyon | PARTIAL |
| KOMSU-EXT-014 | 18,31 | JSON logs, metrics/traces, live/ready/health, hata takibi, dashboard/alert; p50/p95/p99 ve queue/AI/geocode/WS latency | PARTIAL |
| KOMSU-EXT-015 | 19 | Unit/integration/API/DB/security/E2E/Android/offline/duplicate/NLP/geolocation/load/failure testleri | PARTIAL |
| KOMSU-EXT-016 | 20 | Synthetic realistic dataset; dil başına precision/recall/F1/FNR, location ve duplicate precision/recall, translation quality | PARTIAL |
| KOMSU-EXT-017 | 22,23 | Resmî kaynak, erişim tarihi; Android/OSM/DB/AI/privacy/security/observability ve örnek afet sistemleri araştırması | IMPLEMENTED |
| KOMSU-EXT-018 | 24,25,32 | Monorepo, typed validation ve dependency injection; kararların neden/alternatif/ödünleşim/arıza/güvenlik/ölçek ADR'leri | IMPLEMENTED |
| KOMSU-EXT-019 | 27,28 | CI lint/format/unit/integration/security/dependency/container; docker compose, migrations/seed; staging tasarımı | PARTIAL |
| KOMSU-EXT-020 | 29,37,38 | README setup/API/env/Android/AI/security/deploy/demo/troubleshooting; PROJECT_STATUS; vertical slice ROADMAP | IMPLEMENTED |
| KOMSU-EXT-021 | 1,39 | Pilot öncesi field validation, pentest, legal, restore tatbikatı; SLA/24x7/sertifikasyon/kurum entegrasyonları doğrulanmadan production-ready iddiası yok | PARTIAL |

## İzleme kuralı

Her slice ilgili ID'leri doküman ve test dosyasına bağlar. Eksik model ağırlığı, kayıtlı ses, fiziksel cihaz veya operasyon kanıtı açıkça BLOCKERS/RISKS alanında kalır. Sentetik veriyle iyi sonuç saha başarısının kanıtı değildir. PII içeren özgün raporların korunması retention süresince geçerlidir; silme zamanı geldiğinde türevler, indeksler ve cache de kapsanır.

## Güncel uygulama kanıtı — 2026-09-15

IMPLEMENTED, ilgili geliştirme davranışının kod ve yerel kontrollerle gösterildiğini ifade eder; saha/pilot kabulü değildir. PARTIAL, daha geniş kabul hedefinin eksik kaldığını belirtir.

| Kapsam | Uygulama / kanıt | Açık kalan sınır |
|---|---|---|
| Ingestion, tenant/RBAC, dispatch, events | services/api/src/komsu; tests/test_workflow.py, test_postgres.py, test_websocket.py | Harici SMS/telefon sağlayıcısı bağlı değil; ortak quota ve OIDC yok |
| PostgreSQL/PostGIS/pgvector | migrations 0001–0008, gerçek DB testleri; sağlıklı Compose API/DB; yerel restore ve ileri migration kanıtı; encrypted audio/transcript RLS ve versioned release/review | Uzak/offsite restore ve HA eksik; yerel bge-m3 etkin, merkezi süreç yönetimi eksik |
| Konum adayları / GIS katmanları | geolocation.py, map_layers.py, tests/test_geolocation_adapters.py, test_map_layers.py; web LocationCandidates/Map | Geocoder fixture ile testli; belediye verisi yok; Point/LineString ile sınırlı |
| Web | Üretim derlemesi; TR/EL/EN panel kataloğu; erişilebilir demo WAV seçme/kayıt, 16 kHz PCM dönüştürme, sessizlik/boyut/MIME ve 401/403/409 testleri; login/WS/harita kanıtı | Tarayıcı mikrofonu gerçek cihaz matrisinde denenmedi; kurtarma dili incelemesi ve altlık paketi eksik |
| Android offline | Room queue/cache/custody yeniden açma ve v1→v2→v3 migration; tenant-scoped report/audio claim fencing; 30 saniye PCM kayıt/izin kullanıcı akışı; 6 app + 7 relay unit, 6 emülatör testi | Fiziksel mikrofon/uçak modu, kurum anahtarı dağıtımı ve gerçek relay radyo/A→B→C test yok |
| AI / değerlendirme | 3000 şablon raporu, 18 zorlayıcı sınıflandırma örneği; 240 mesaj gerçek bge-m3 stres testi; dört yönlü OPUS-MT; yerel Whisper | İhtiyaç recall 0.50; semantic recall@1 0.0 ve 0.92 precision 0.1493; çeviri kritik kayıplı; Whisper TTS WER 0.3793 |
| Yük ölçümü | scripts/benchmark_local.py, docs/evaluation/local-benchmark.json: 30 rapor, 6 istemci, tek worker | Küçük yerel burst; sürdürülebilir kapasite/SLO ölçümü değil |
| Kalite / güvenlik | Toplam 88 Python testi (9 gerçek PG); Python lint, pip-audit ve Bandit; web build/11 test; Android build/lint, 13 unit ve 6 emülatör testi; encrypted audio capture/scan/release/transcript kanıtı | Uzak CI çalışmadı; gerçek scanner, fiziksel mikrofon/saha sesi, container bulguları, hukuk onayı, cache/backup re-purge ve pentest eksik |
| Worker gözlemlenebilirliği | Sabit etiketli sonuç sayacı; analiz/iş/kuyruk bekleme histogramları; depth/oldest gauge; localhost opt-in endpoint; PII'siz JSON completion log | Embedding alt-batch sayaçları PostgreSQL kısmi hata/tekrar testiyle doğrulandı; merkezi scrape/dashboard/alert/OTLP yok |
| Mimari / hukuk / işletim | docs/architecture, docs/security, docs/adr, docs/research, README, ROADMAP | Retention icrası, hukuk onayı, gerçek kurum pilotu tamamlanmadı |

Yerel bge-m3 kanıtı: `docs/evaluation/bge-provenance.json`, `bge-diagnostic.json`, `duplicate-retrieval-diagnostic.json`; 12 demo raporu vektörlendi. Altı metinlik tanıda farklı bina benzerliği 0.958, 240 mesaj stres testinde aynı şablon farklı olay 1.0 olmuştur: otomatik birleştirme yapılmaz. Çeviri kanıtı `translation-provenance.json`, `translation-diagnostic.json`, `translation-pipeline-smoke.json` ve `TRANSLATION.md`; ses kanıtı `whisper-provenance.json`, `whisper-diagnostic.json` ve `TRANSCRIPTION.md` içindedir. Android dört Room enstrümantasyon testi geçmiştir.
