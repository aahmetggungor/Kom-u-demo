# Komşu / γείτονας

Türkiye–Yunanistan afet koordinasyonu için insan kararını merkeze alan, üç dilli mesaj ve çevrimdışı saha uygulaması temeli. Ürün kaynağı FıraTech Komşu proje PDF'sidir. PDF kapsamı ve ek mühendislik gereksinimleri [gereksinim matrisinde](docs/REQUIREMENTS.md) ayrılır.

**Durum:** çalışan geliştirme temeli; production-ready veya gerçek afette kullanıma onaylı değildir. Sentetik verilerle çalışın. Özelliklerin doğrulama durumu [PROJECT_STATUS.md](PROJECT_STATUS.md) içinde tutulur.

## Şu anda çalışan akış

Kimliği doğrulanmış rapor → atomik kalıcı kayıt ve iş kuyruğu → TR/EL/EN kural tabanlı öneri → canlı web vaka listesi/harita noktası → koordinatör konum ve vaka doğrulaması → yetkili insan sevki ve audit kaydı. AI çalışmasa da özgün rapor incelenebilir. UUID ile tekrar gönderim aynı kaydı döndürür; farklı içerik 409 verir. Kurumlar arasında veri paylaşımı varsayılan olarak kapalıdır.

AI baseline kalibre edilmemiştir. Sabitlenmiş yerel bge-m3 semantik önerileri ve dört yönlü OPUS-MT çeviri adaptörü vardır; ikisi de varsayılan olarak kapalı ve insan incelemesine tabidir. Çeviri tanısal seti ciddi sayı, özel ad ve olumsuzluk kayıpları göstermiştir. Whisper adaptörü ve şifreli karantina deposu vardır; otomatik transcription iş akışı, canlı geocoder, kayıtlı sözlük sesi ve fiziksel Bluetooth/Wi-Fi Direct aktarımı tamamlanmış değildir. Kullanıcı arayüzü bunları varmış gibi göstermez.

## Bileşenler

| Dizin | İşlev |
|---|---|
| services/api/src/komsu | FastAPI, domain, auth, persistence, AI portları ve worker |
| apps/web | React/TypeScript/MapLibre koordinasyon ekranı |
| apps/mobile | Kotlin/Compose, Room, WorkManager; izole relay modülü |
| migrations | Alembic relational + PostgreSQL spatial/vector/RLS şeması |
| infrastructure/docker | Yerel DB, API ve migration image'ları |
| tests | Unit, API, security, failure ve PostgreSQL testleri |
| data | Tekrarlanabilir sentetik demo corpus |
| docs | Gereksinimler, mimari/ERD, ADR, araştırma ve threat model |

Mimari: [SYSTEM_ARCHITECTURE](docs/architecture/SYSTEM_ARCHITECTURE.md), [ERD/veritabanı](docs/architecture/DATABASE.md), [kararlar](docs/adr/001-backend.md), [şifreli ses kararı](docs/adr/009-encrypted-audio-quarantine.md), [vertical-slice roadmap](ROADMAP.md).

## Yerel kurulum

Gerekenler: Python 3.12+, Docker Engine/Desktop, Node.js (Vite sürümünün desteklediği güncel Node), npm. Android için Android Studio/JDK ve SDK 36. Komutları bu repo kökünde çalıştırın.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python scripts/configure_local.py
docker compose up -d --build
```

Linux/macOS'ta Python yolunu `.venv/bin/python` kullanın. İlk build PostGIS paketlerini indirir. Compose, DB hazır olunca migration'ı, o bitince API'yi başlatır. `http://127.0.0.1:8000/health/ready` hazır olmalıdır. Tek host Compose yüksek erişilebilirlik sağlamaz.

Yerel geliştirici API'yi container yerine doğrudan çalıştırabilir:

```powershell
docker compose up -d db
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn komsu.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Aynı portta hem container hem yerel API çalıştırmayın. Windows ortamında `127.0.0.1` kullanın; `localhost` IPv6 çözümlemesi bağlantı beklemesine yol açabilir. Bağlantı zaman aşımı 5 saniyedir.

### Demo oturumu ve verileri

```powershell
.venv\Scripts\python -m komsu.cli provision
.venv\Scripts\python scripts/generate_demo.py
.venv\Scripts\python scripts/seed_demo.py
cd apps/web
npm ci
npm run dev
```

Web: `http://127.0.0.1:5173`. Kök dizindeki **gitignored** `.env.session.json` içindeki geçici token ile giriş yapın. Token sekme belleğinde tutulur; tarayıcı depolamasına yazılmaz. `provision` mevcut credential dosyasını ezmez. Sekiz saat sonra aynı yerel demo kimliğini yenilemek için `python scripts/refresh_demo_session.py`; yeni rol/kurum oluşturmaz. Gerçek kurumlar için OIDC/MFA ve yönetimli kayıt pilot önkoşuludur.

`generate_demo.py` 3000 mesaj / 1000 sentetik olay grubu üretir; `seed_demo.py` ilk 12 mesajı alır ve worker ile işler. Farklı dillerde aynı olaylar şu anda kendiliğinden birleşmez: güvenli semantic merge slice'ı henüz tamamlanmadı. Kimlik tekrarlarını bu özellik ile karıştırmayın.

Sürekli worker:

```powershell
.venv\Scripts\python -m komsu.cli worker --tenant <provision-ile-olusan-tenant-id>
```

Compose worker profili için `.env` içine `KOMSU_WORKER_TENANT` ekleyin ve `docker compose --profile worker up -d --build worker` çalıştırın. Worker kurum kimliği açıkça belirtilmedikçe başlamaz.

### Ortam değişkenleri

| Değişken | Amaç |
|---|---|
| KOMSU_DATABASE_URL | Scoped runtime bağlantısı; API/worker |
| KOMSU_ADMIN_DATABASE_URL | Yalnız migration/provision/test admin bağlantısı |
| KOMSU_DB_PASSWORD / KOMSU_APP_PASSWORD | Compose için yerel rastgele parolalar |
| KOMSU_ENVIRONMENT | development/test; pilot/production açılışı bilinçli olarak kapalı |
| KOMSU_ALLOWED_ORIGINS | JSON liste; CORS ve WebSocket Origin allowlist |
| KOMSU_MAX_BODY_BYTES | Varsayılan 32768; gerçek stream boyutu kontrolü |
| KOMSU_MAX_AUDIO_BYTES | Yalnız ses ekleme yolu için stream sınırı; varsayılan 2000000 |
| KOMSU_AUDIO_MASTER_KEY_B64 | 32 rastgele baytın base64 değeri; ses şifreleme kök anahtarı, commit edilmez |
| KOMSU_AUDIO_KEY_ID | Şifreli ses satırına yazılan yönetilen anahtar sürüm etiketi |
| KOMSU_REQUESTS_PER_MINUTE | Süreç başına kurum request limiti; varsayılan 120 |
| KOMSU_QUEUE_LIMIT | Kurum başına bekleyen/running iş sınırı; varsayılan 10000 |
| KOMSU_WORKER_TENANT | Worker'ın işleyeceği kurum |
| KOMSU_TRANSLATION_MODEL_DIR | İsteğe bağlı, doğrulanmış yerel OPUS-MT paket kökü; ör. `models/opus-mt` |
| KOMSU_WORKER_METRICS_PORT | İsteğe bağlı localhost Prometheus worker portu; ör. `9101` |

`.env`, `.env.session.json`, model ağırlıkları, veritabanı dosyaları ve build cache'leri commit edilmez. Compose parolalarını döndürmek yalnız `.env` değiştirmekle mevcut DB rolünü güncellemez; ayrı yönetici rotasyonu gerekir.

## API

OpenAPI: `/openapi.json`, geliştirici dokümanı `/docs`. Versioned domain `/api/v1`. Bütün vaka/rapor/ekip yollarında bearer token; health anonim, metrics admin.

- `POST /reports`: UUID idempotent, 202 durable kabul; 409 farklı payload; 503 kuyruk/DB kapasitesi. İstemci başarısızlıkta aynı UUID ve içeriği saklar.
- `GET /cases`: urgency/type/verification/language/status/region/team/since; limit 1–100, offset 0–10000; kritik, belirsiz, yüksek sırasıyla, sonra oluşturma zamanı ve ID. Bilinmeyen öncelik görünür kalır.
- `GET /cases/{id}`, `GET /reports/{id}`: kaynak mesaj/analiz. Başka kurum ID'si 404.
- `POST /reports/{id}/audio`: ham `audio/wav`; 16 kHz, mono, 16-bit PCM, 0.2–30 saniye. AES-GCM ile şifrelenmiş karantinaya alınır; aynı içerik idempotent, farklı içerik 409. Açık ses veya şifreli blob yanıtta dönmez.
- `POST /cases/{id}/review`: explicit expected_version, reason, verification, priority, koordinat ve onay.
- `POST /cases/{id}/dispatch`: expected_version ve team_id; verified + confirmed location + coordinator/admin. Çakışma 409.
- `GET/POST /teams`; `GET /map/layers`; `GET /auth/me`.
- `GET /events?after=n`: ID tabanlı tekrar okunabilir olaylar. `WS /events/ws`: ilk frame `{token,after}`; URL'ye token koymayın. İçerik IDs/version ile sınırlı, her tur auth yenilenir.

## Testler

```powershell
.venv\Scripts\python -m pytest -q
$env:KOMSU_RUN_POSTGRES_TESTS='1'
.venv\Scripts\python -m pytest tests/test_postgres.py -q
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
cd apps/web
npm test
npm run build
```

PostgreSQL testleri yerel DB'de yeni **sentetik** kurumlar oluşturur. Gerçek operasyon DB'sine yönlendirmeyin. SQLite testleri RLS/spatial/vector kanıtı değildir. Test yüzdesi yerine kritik invariants esas alınır. Son test sonuçları PROJECT_STATUS içinde belirtilir.

## Android

`apps/mobile` Android Studio projesini açın; SDK 36 ve JDK 17+ yapılandırın. Gradle 8.14 wrapper repo içindedir. Windows: `gradlew.bat :app:assembleDebug :app:testDebugUnitTest :relay:test :app:lintDebug`. Emülatör/cihaz bağlıysa `:app:connectedDebugAndroidTest`.

Bir kez Bağlantı ekranında API ve geçici token doğrulanır. Debug emülatörde `http://10.0.2.2:8000`; fiziksel cihaz/release için HTTPS kurum sunucusu. HTTP yalnız debug loopback/emülatör adreslerinde açık. Token Android Keystore ile şifrelenir, yedekleme kapalıdır. Raporlar önce Room'a, sonra network constraint ile WorkManager'a gider. Retry aynı UUID'yi korur; 409 CONFLICT, 401/403 yeniden kimlik doğrulama, geçici ağ/5xx tekrar deneme. Görev cache'i zamanı ile görünür. Kurum değiştirme başka kurumun kuyruğunu göndermez.

Sözlükte PDF'nin üç TR/EL/EN ifadesi çevrimdışı bulunur; kayıtlı ses dosyaları henüz sağlanmadı. Relay modülü sınırlı TTL/hop/UUID/tenant politikasına ek olarak Room üzerinde tam zarf saklama, ECDSA kaynak imzası ve AES-GCM doğrulamalı şifreleme sağlar. Room v1→v2 migration ve yeniden açma testi vardır. Kurum anahtarı dağıtımı, kullanıcıya görünür relay oturumu ve gerçek Wi-Fi Direct/Bluetooth transport'u henüz bağlı değildir; fiziksel A→B→C saha testi olmadan relay uçtan uca çalışıyor denmez.

## Harita ve modeller

Halka açık Nominatim afet akışına bağlanmaz; kişisel/confidential veri gönderilmez. Public OSM tiles üzerinden offline paket indirilmez. [Araştırma](docs/research/STACK_AND_AI.md) limitleri ve kaynakları içerir. Şu an MapLibre altlıksız koordinat çalışma alanı olduğunu açıkça belirtir. Kuruma ait lisanslı tile/GIS paketiyle yapılandırma sonraki adımdır.

Model adapter'ları local-only ağırlık yükler; gizli download veya vendor API yoktur. Baseline konum uydurmaz. Çeviri paketi yapılandırılmadığında çeviri `UNAVAILABLE` kalır; yapılandırıldığında model sürümü/yol/pivot kaydedilir, sayı ve olumsuzluk kaybı uyarılır. Sentetik fixture doğruluğu gerçek afet doğruluğu değildir.

İsteğe bağlı `KOMSU_GEOCODER_URL`, kendi kurumunuzun Nominatim adresini worker'a verir; varsayılan kapalıdır. Aday seçimi web formunu doldurur, onay veya sevk yapmaz. Canlı sağlayıcı bu geliştirme ortamında denenmedi.

Admin `POST /api/v1/map/layers` ile `kind`, `name`, `provenance` ve sınırlı `geojson` FeatureCollection yükleyebilir. İlk sürüm Point/LineString, en fazla 200 feature/1000 koordinat ve 32 KiB istek kabul eder; uzaktan URL veya ikon yüklemez. Katmanlar haritada açılıp kapanır, kaynak ve yükleme zamanı görünür. `python scripts/seed_gis_demo.py` yalnız sentetik örnekleri yerel demo kurumuna ekler; gerçek tesis/yol bilgisi değildir.

Web derlemesi için MapLibre 6 worker'ı `?worker&url` ile paketlenir; yalnız `?url` üretim paketinde gerekli bağımlılığı eksik bırakır. [Resmî MapLibre kurulum belgesi](https://maplibre.org/maplibre-gl-js/docs/#installation), erişim 2026-09-14. `npm exec vite preview -- --host 127.0.0.1 --port 5173` ile derlenmiş paketi yerel API karşısında inceleyebilirsiniz.

`python scripts/evaluate.py` şablon regresyonunu; `--input data/challenge.synthetic.jsonl --output docs/evaluation/challenge-results.json --kind synthetic_challenge_not_independent_validation` zorlayıcı örnekleri ölçer. `python scripts/benchmark_local.py` localhost API ve ayrı sentetik kurumda 30 mesajlık HTTP burst + kuyruk boşaltma ölçümü yapar. Sonuçların sınırları `docs/evaluation/INTERPRETATION.md` içinde açıklanmıştır.

## Güvenlik, deployment, sorun giderme

[Threat model](docs/security/THREAT_MODEL.md), [saklama yürütmesi](docs/security/RETENTION.md) ve [deployment ADR](docs/adr/008-deployment.md). Scoped DB rolü, RLS, parametreli sorgu, validation, versioned insan işlemleri ve audit test edildi. TLS termination, encrypted host/backup, OIDC/MFA, merkezi quota, backup/cache re-purge, tam observability, uzak restore, pentest ve hukuk/saha doğrulaması tamamlanmadan gerçek veri veya pilot açmayın. Bu sınırlar bir sertifikasyon iddiası değildir.

API `/metrics` yolu yalnız admin token ile HTTP istek sayısı/gecikmesi verir. Worker'a isteğe bağlı `KOMSU_WORKER_METRICS_PORT` verildiğinde yalnız `127.0.0.1` üzerinde kuyruk derinliği/yaşı, iş sonucu ve analiz/toplam/bekleme histogramları açılır. Metrikler mesaj, tenant veya report ID taşımaz. Merkezi scrape, dashboard, alert ve OTLP henüz kurulmadı; ayrıntı [gözlemlenebilirlik runbook'unda](docs/operations/OBSERVABILITY.md).

- 401: sekiz saatlik token süresi/iptal; yerel demo session refresh aracı.
- 403: rol yetersiz; istemci role/tenant alanı göndererek yükseltemez.
- 409: aynı UUID farklı içerik veya eski vaka version; özgün kaydı koruyup yeniden inceleyin.
- 503: DB/schema/queue; `docker compose ps`, `/health/ready`, worker durumunu inceleyin; yerel raporu silmeyin.
- Queue bekliyor: tenant worker çalışıyor mu, ağ constraint var mı, token geçerli mi?
- Harita boş: altlık yapılandırılmamış olabilir veya raporlar konumsuzdur; vaka listesi çalışmaya devam eder.
- Model yok: ilk baseline çalışır; manuel inceleme devam eder; eksik özellikleri tamamlandı saymayın.

Projenin açık çekirdek lisansı hak sahipleri tarafından kesinleştirilmelidir; dosyalara onların adına lisans verilmedi. Model ve GIS lisansları ayrı değerlendirilir.

## Yerel anlamsal öneriler ve insan gruplaması

Migration `0002_case_merge` uygulanmalıdır. Birleştirme/ayırma API ve web paneli gerekçe, mevcut vaka sürümleri ve koordinatör/admin rolü ister. Özgün raporlar korunur; yeniden gruplama konum/öncelik doğrulamasını sıfırlar. `POST /api/v1/cases/{id}/merge` ve `/split` otomatik model kararı değildir.

Migration `0003` ve `0004`, iki ayrı yönetici onaylı saklama planları ile süreli yasal bekletmeleri ekler. Migration `0005`, tenant RLS korumalı şifreli ses karantinasını ekler. API planı ses sayısını da önizler; kalıcı yürütme eşleşen ses ciphertext'ini aynı işlemde siler. Kalıcı redaksiyon yalnız yönetici CLI komutuyla ve plan UUID'si tekrar girilerek çalışır. Gerçek veri öncesi hukuk onayı şarttır.

bge-m3 için API ortamından ayrı Python 3.12 ortamı kullanın. Aşağıdaki komutları depo kökünde, bu ortamın Python'u ile çalıştırın:

```powershell
python -m pip install torch==2.14.0+cpu --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-models.lock
python -m pip install --no-deps -e .
python scripts/download_bge.py
python scripts/evaluate_bge.py
python scripts/evaluate_duplicate_retrieval.py
python scripts/embed_reports.py --tenant KURUM_UUID --limit 100
python scripts/download_translation_models.py
python scripts/evaluate_translation.py
python scripts/download_whisper.py
python scripts/evaluate_whisper.py
```

İndirme yalnızca sabitlenmiş resmi BAAI model sürümüdür (ağırlık yaklaşık 2.27 GB); raporlar dış servise gönderilmez. `models/` Git/Docker bağlamına dahil değildir. Script SHA-256 denetler ve provenance kaydeder; model yerel dosyalardan, uzaktan kod çalıştırmadan yüklenir. Son kod, 512 token ile sınırlı yoğun embedding kullanır; uzun metinlerin tamamının temsil edildiği varsayılmaz.

Batch çıktısındaki `model_revision` değerini `.env` içinde `KOMSU_EMBEDDING_REVISION` olarak ayarlayıp `docker compose up -d api` çalıştırın. Boş bırakılırsa öneriler devre dışıdır. Sürekli yerel işleme için aynı komuta `--watch` ekleyin (varsayılan 5 saniye sorgulama, Ctrl+C ile durur); tek seferlik batch de desteklenir. Model ilk ihtiyaçta bir kez yüklenir; aynı sürümün mevcut vektörleri değiştirilmez. `GET /api/v1/cases/{id}/similar` aynı kuruma/sürüme ait, rapor zamanları arasında en fazla 24 saat olan beş açık vaka getirir. Uzaklık bilinmiyorsa açıkça gösterilir. Skor aynı olay olasılığı değildir: farklı bina örneği 0.958, kimlik eki çıkarılmış farklı olay şablonları 1.0 olmuş; 240 mesajlık stress testinde semantic recall@1 her dilde 0.0 çıkmıştır. Ayrıntı: [ölçüm ve sınırlar](docs/evaluation/SEMANTIC.md).

Çeviri paketleri toplam yaklaşık 974 MB aktif ağırlıktır. Dört yön sabit resmi Helsinki-NLP sürümünden indirilir, SHA-256 ile provisioning sırasında ve ilk yüklemede doğrulanır, uzaktan kod çalıştırılmaz. TR↔EL İngilizce üzerinden gider ve arayüz bunu açıkça gösterir. Yerel worker için `KOMSU_TRANSLATION_MODEL_DIR=models/opus-mt` ayarlayın; temel Compose imajı model bağımlılıklarını/ağırlıkları içermez. Altı yazarlı sentetik örnekte tüm rakamlar yalnız 3/6, olumsuzluk işareti 1/4 ve özel adlar birebir 0/6 korundu. Bu nedenle çeviri sınıflandırma, bastırma, vaka birleştirme veya sevk kararı vermez; koordinatör özgün metni kontrol eder. Ayrıntı: [çeviri kanıtı ve sınırları](docs/evaluation/TRANSLATION.md).

Whisper-tiny adaptörü yalnız açıkça onaylanan bir yerel kök altındaki, en fazla 30 saniyelik 16 kHz/16-bit/mono PCM WAV dosyalarını kabul eder; sessizliği model yüklemeden reddeder. Sabit Apache-2.0 `safetensors` ağırlığı yaklaşık 151 MB'dır ve ilk yüklemede tekrar doğrulanır. Ayrı API sınırı aynı biçim ve enerji kontrollerinden geçen sesi HKDF ile ayrılmış anahtarlar ve AES-GCM kullanarak PostgreSQL'de `QUARANTINED` durumda saklar; anahtar commit edilmez, ham ses indirme yolu yoktur ve saklama yürütmesi ciphertext'i siler. Bu karantina, zararlı içerik taraması veya transcription onayı değildir. İki işletim sistemi TTS örneğinde mikro WER 0.3793'tür; Türkçe/İngilizce plumbing kanıtıdır, insan/saha ses doğruluğu değildir. Yunanca örnek, karantinadan transcription'a onaylı geçiş ve web/Android ses girişi eksiktir. Ayrıntı: [transcription kanıtı](docs/evaluation/TRANSCRIPTION.md).

`python scripts/check_embedding_watch.py` gerçek yerel modelle ayrı sentetik kurumda iki ardışık rapor gelişini doğrular. İşçi hatayla durursa önceki alt-batch commitleri korunur; yeniden başlatıldığında eksik vektörler sorgudan bulunur. Bozuk model çıktısı PostgreSQL testinde hata üretir ve özgün raporlar korunur. Embedding komutunda --metrics-port 9102 ile localhost ölçümleri açılır; sayaç yalnız commit edilmiş yeni vektörleri sayar. Kısmi hata ve tekrar işleme PostgreSQL testinde doğrulanmıştır. Bekleyen rapor göstergesi son sorgunun --limit ile sınırlı sonucudur. Üretim süreç yöneticisi/otomatik yeniden başlatma ve merkezi izleme henüz yapılandırılmamıştır.

Yerel konteyner taraması ve kalan bulgular: [CONTAINER_SCAN.md](docs/security/CONTAINER_SCAN.md). İmaj güncellemesinden sonra PostgreSQL 17.11 ve tam Python test paketi doğrulandı. API imajında paket kurucusu bulunmaz; bağımlılıklar Docker build sırasında değiştirilmeli ve imaj yeniden üretilmelidir.
