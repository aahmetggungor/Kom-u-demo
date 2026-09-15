# Komşu — tamamlanmaya kadar Codex çalışma promptları

Güncelleme: 2026-09-15. Başlangıç commit'i: `17f217b`.

Bu plan kredi kullanımını sınırlamak için her görevi tek bir doğrulanabilir parçaya böler. Promptları sırayla, tercihen ayrı Codex görevlerinde kullanın. Bir aşama başarısızsa sonraki aşamaya geçmeden aynı görevde yalnız hatayı düzeltin. Mock, fixture veya sentetik veriyle geçen kontrol gerçek kurum, saha ya da üretim doğrulaması olarak yazılmamalıdır.

## Güncel başlangıç noktası

- Kontrollü sunum demosu: yaklaşık `%85`.
- Uzun gereksinim kapsamı: yaklaşık `%55`.
- Gerçek kurum/saha pilotu hazırlığı: yaklaşık `%30`.
- Çalışan parçalar: FastAPI/PostgreSQL/PostGIS/pgvector, kalıcı kuyruk, tenant/RBAC, insan incelemesi ve sevk, üç dilli web paneli, sentetik GIS katmanları, Android çevrimdışı Room kuyruğu, şifreli relay zarfı ve şifreli ses karantinası.
- Bilinen kalite sınırları: sınıflandırma ihtiyaç recall `0.50`, semantic recall@1 `0.0`, kritik çeviri kayıpları ve yalnız iki sentetik TTS örneğinde Whisper WER `0.3793`.
- Dış bağımlılıklar: anadili konuşan değerlendiriciler, gerçek kurtarma sesleri, belediye GIS/geocoder erişimi, mesaj sağlayıcıları, üç fiziksel Android cihaz, hukuk/kurum onayı ve pilot altyapısı.

## Kullanım kuralı

Her prompt sonunda Codex şunları yapmalıdır: ilgili testleri çalıştırmak, kanıtı belgelemek, `PROJECT_STATUS.md` ile `docs/REQUIREMENTS.md` durumlarını yalnız kanıta göre güncellemek, tek bir açıklayıcı commit oluşturmak ve Türkçe kısa sonuç vermek. Tam paket testleri her küçük düzeltmede değil, aşama tamamlanınca çalıştırılmalıdır.

## Prompt 1 — Ses karantinası tarama ve serbest bırakma

```text
C:\Users\rog\Documents\Codex\2026-09-14\files-mentioned-by-the-user-ahmet\outputs\komsu içinde çalış. Önce PROJECT_STATUS.md, docs/AUDIT_2026-09-15.md, docs/REQUIREMENTS.md ve docs/adr/009-encrypted-audio-quarantine.md dosyalarını oku; tamamlanmış işleri tekrar yapma. Yalnız ses karantinası tarama ve açık serbest bırakma aşamasını tamamla. Karantinadaki şifreli WAV için durum makinesi, ayrıcalıklı scanner arayüzü, zararlı/bozuk içerik sonucu, iki kişilik veya uygun yetkili serbest bırakma kararı, audit kaydı, idempotency ve fail-closed davranışını geliştir. Tarama başarılı ve açıkça serbest bırakılmış ses dışında hiçbir içerik Whisper'a gitmesin. Plaintext'i API yanıtı veya loglara koyma. Gerçek tarayıcı motoru yoksa adapter ve deterministik güvenli test doubles kullan; bunu gerçek tarama diye sunma. Tenant/RLS, tekrar, yarış, ret, bozuk ciphertext ve retention testlerini ekle. İlgili backend testlerini, ardından tam Python paketini çalıştır; belgeleri güncelle ve tek commit oluştur. Sonuçta kalan dış bağımlılıkları ve Prompt 2'ye hazır olup olmadığını yaz.
```

## Prompt 2 — Transkripsiyon işçisi ve insan incelemesi

```text
Komşu reposunda güncel PROJECT_STATUS.md, REQUIREMENTS.md ve son commit'i oku. Yalnız serbest bırakılmış sesin transkripsiyon iş akışını tamamla. Worker lease/retry/idempotency kurallarını kullan; doğrulanmış yerel Whisper modelini yalnız RELEASED durumundaki ses için çağır. Transcript, dil, model revision, checksum/provenance, confidence/uyarı ve hata durumlarını sakla. Özgün ses ve transcript korunmalı; düşük güven otomatik karar üretmemeli. Yunanca model yolu eksikse açık UNAVAILABLE sonucu ver. Web vaka detayına yalnız yetkili kullanıcı için ses metadata, transcript ve insan düzeltme alanı ekle; ham ses indirme ekleme. API/DB/worker/web testlerini, bozuk ses/model yok/retry/tenant izolasyonu senaryolarını çalıştır. Tamamlanan kanıtları belgele, commit oluştur ve Prompt 3 için eksikleri yaz.
```

## Prompt 3 — Android ve web ses kaydı/kabul akışı

```text
Komşu reposunun güncel durum belgelerini oku. Yalnız kullanıcıdan kısa ses raporu alma akışını geliştir. Android'de açık izin isteme, en fazla 30 saniye kayıt, kullanıcıya süre/iptal/yeniden kayıt gösterimi, 16 kHz mono PCM WAV üretimi, çevrimdışı Room kuyruğu ve bağlantıda idempotent upload ekle. Web tarafında yalnız geliştirme/demo için erişilebilir dosya seçme veya kayıt akışı ekle; desteklenmeyen tarayıcıda açık hata göster. Boyut, MIME, sessizlik, izin reddi, process death, retry, 401/403/409 ve tenant değişimi testlerini kapsa. Mikrofon verisini loglama veya analitiğe gönderme. Android unit/instrumentation ve web testlerini çalıştır; fiziksel cihaz kanıtı yoksa bunu açık bırak. Belgeleri güncelle, commit oluştur ve Prompt 4'ü işaretle.
```

## Prompt 4 — İhtiyaç ve aciliyet sınıflandırma kalitesi

```text
Komşu reposunda AI değerlendirme belgelerini ve mevcut sentetik/zorlayıcı veri setlerini oku. Yalnız ihtiyaç türü ve aciliyet sınıflandırmasını iyileştir. Önce mevcut başarısız örnekleri hata türlerine ayır; mahsur, sağlık, barınak, su ve belirsiz durumlar için TR/EL/EN ayrı ölçüm üret. Kural tabanı ile açık kaynak model adaylarını tekrarlanabilir deneyle karşılaştır; veri sızıntısını önleyen train/dev/test ayrımı ve model provenance ekle. En güvenli aday yeterli değilse varsayılanı değiştirme. False negative, sayı/olumsuzluk ve düşük güven durumlarını insan incelemesine yönlendir; otomatik sevk ekleme. Hedef metrikleri ve başarısızlık eşiğini önceden yaz, test ve değerlendirmeleri çalıştır, sonuçları olduğu gibi kaydet. Belgeleri güncelle, commit oluştur ve gerçek etiketli veri ihtiyacını belirt.
```

## Prompt 5 — Çeviri güvenilirliği ve anadili konuşan inceleme paketi

```text
Komşu reposunda translation adapter, provenance ve diagnostic sonuçlarını oku. Yalnız TR-EL-EN çeviri güvenilirliğini geliştir. Sayı, adres, kişi/yer adı, olumsuzluk ve afet terimlerini koruyan placeholder/terminoloji katmanı ekle; özgün metni daima görünür tut. Model/pivot/yön ve uyarıları sakla. Mevcut OPUS modellerini aynı sabit veri setinde yeniden ölç; iyileşme ölçülmeden varsayılan davranışı yükseltme. Anadili konuşanların çevrimdışı değerlendirebileceği, kişisel veri içermeyen CSV/JSON değerlendirme paketi ve içe aktarma aracı üret. Çeviri hiçbir şekilde sınıflandırma, birleştirme veya sevki tek başına belirlemesin. Testleri çalıştır, belgeleri güncelle, commit oluştur; insan değerlendirmesi bekleyen alanları açıkça listele.
```

## Prompt 6 — Çok sinyalli duplicate önerileri

```text
Komşu reposunda semantic değerlendirmeleri, merge/split akışını ve bge-m3 kodunu oku. Yalnız duplicate aday üretimini iyileştir. Metin benzerliğini zaman, doğrulanmış/aday konum mesafesi, adres varlıkları, bina/landmark ve ihtiyaç uyumu ile açıklanabilir bir skorda birleştir. Aynı şablon-farklı olay ve farklı bina karşı örneklerini özellikle koru. Otomatik merge yapma; yalnız gerekçeli öneri üret ve her sinyalin katkısını web panelinde göster. Eşik kalibrasyonunu bağımsız development/test bölümüyle ölç; dil bazlı precision/recall ve yanlış birleştirme oranını raporla. PostgreSQL pgvector, tenant, zaman penceresi, eksik konum ve yeniden gruplama testlerini çalıştır. Belgeleri güncelle, commit oluştur ve gerçek olay etiketlerine kalan ihtiyacı yaz.
```

## Prompt 7 — Konum çıkarımı ve kurumsal geocoder

```text
Komşu reposunda geolocation adapter, güvenlik notları ve harita bileşenlerini oku. Yalnız güvenli konum aday üretimini tamamla. TR/EL adres, mahalle, sokak, landmark ve yazım hataları için gold test seti oluştur; koordinat uydurmama kuralını koru. Kurumun self-host geocoder servisi için timeout, retry, cache, rate limit, circuit breaker, provenance ve veri minimizasyonu ekle. Public Nominatim'e gerçek rapor gönderme. Canlı kurum URL/kimlik bilgisi yoksa contract server ile doğrula ve `docs/operations/GEOCODER_ONBOARDING.md` veri talep listesini oluştur; canlı entegrasyon iddiasında bulunma. Adaylar insan onayı olmadan vaka konumunu değiştirmesin. Testleri çalıştır, belgeleri güncelle, commit oluştur.
```

## Prompt 8 — Gerçek harita ve belediye GIS paketleri

```text
Komşu reposunda MapLibre, GIS import ve veri provenance kodunu oku. Yalnız kurumsal harita/GIS paketlemesini geliştir. Lisanslı raster/vector tile veya offline style paketi için yapılandırma, checksum, sürüm, son güncelleme ve devre dışı kalma davranışı ekle. Hastane, toplanma alanı, barınak ve kapalı yol verileri için doğrulama, admin import, güncellik uyarısı ve kaynak gösterimi ekle; Polygon/Multi geometry gereksinimini kontrollü sınırlarla tamamla. Tile servisi yokken vaka listesi ve koordinat çalışma alanı çalışmaya devam etsin. Sentetik fixture ve render/E2E kontrollerini yap; gerçek belediye verisi verilmediyse pilot kanıtı sayma. Belgeleri güncelle, commit oluştur ve gereken kurum dosyalarını listele.
```

## Prompt 9 — Dış mesaj kanalı adapterları

```text
Komşu reposunda ingestion, channel normalization/HMAC ve API sözleşmelerini oku. Yalnız dış kanal adapter katmanını tamamla. SMS, mesajlaşma, sosyal medya ve telefon operatörü için vendor bağımsız inbound sözleşme; imza doğrulama, replay engeli, timestamp toleransı, kaynak message ID idempotency, boyut limiti, abuse quota ve dead-letter davranışı geliştir. Sağlayıcı hesabı yoksa yerel contract test server ve kayıtlı güvenli fixtures kullan; canlı sağlayıcı bağlı dememe. Telefon sesi ses karantinasından geçsin. Secret'ları repo/loglara yazma. Provider outage, duplicate delivery, sahte imza, farklı tenant ve malformed payload testlerini çalıştır. OpenAPI/operasyon belgelerini güncelle, commit oluştur ve canlı sandbox erişimi için gerekenleri listele.
```

## Prompt 10 — Android çevrimdışı saha deneyimi ve sözlük sesi

```text
Komşu reposunda Android Room/WorkManager/sözlük kodunu oku. Yalnız çevrimdışı saha deneyimini tamamla. Uçak modu, process death, yeniden başlatma, uzun süre bağlantısız kalma, token süresi, conflict çözümü, kuyruk görünürlüğü ve kullanıcıya güvenli hata mesajlarını iyileştir. TR/EL/EN kurtarma sözlüğünü sürümlü manifest ve checksum ile paketle; profesyonel kayıtlar sağlanmadıysa sentetik sesi ürün kaydı gibi koyma, bunun yerine güvenli import/validation akışı ve kayıt gereksinimi oluştur. Erişilebilirlik, büyük yazı, ekran okuyucu ve düşük ışık kontrolleri ekle. Unit, Room migration ve emulator testlerini çalıştır; belgeleri güncelle ve commit oluştur.
```

## Prompt 11 — Bluetooth/Wi-Fi Direct gerçek aktarım

```text
Komşu reposunda relay protokolü, ECDSA/AES-GCM zarfı ve Android custody tablolarını oku. Yalnız gerçek cihazlar arası taşıma katmanını geliştir. Android sürüm izinleri, kullanıcı tarafından açıkça başlatılan oturum, peer keşfi, karşılıklı kimlik doğrulama, Bluetooth ve Wi-Fi Direct transport abstraction, chunk/resume, delivery receipt, TTL/hop/seen cache ve iptal akışını ekle. Kurum anahtar dağıtımı ve rotasyonu için güvenli enrollment tasarla; sabit/shared demo anahtarını production yolu yapma. Fake transport ve en az iki emülatör/uygulanabilir cihaz testi oluştur. Üç fiziksel cihaz yoksa A→B→C→sunucu kabulünü BLOCKED bırak ve ayrıntılı saha test prosedürü yaz. Android test/lint/build çalıştır, belgeleri güncelle ve commit oluştur.
```

## Prompt 12 — Yük, backpressure ve arıza dayanıklılığı

```text
Komşu reposunda durable queue, worker leasing, benchmark ve failure belgelerini oku. Yalnız performans ve dayanıklılık aşamasını tamamla. 10/100/1000 mesaj/saniye için kontrollü yük senaryoları, duplicate storm, yavaş model, DB/geocoder kesintisi, worker crash/restart, WebSocket reconnect ve kuyruk dolması testleri oluştur. Donanım ve test ortamını sonuçla birlikte kaydet; ölçülmeyen 10000 mesaj/saniye iddiası yapma. Backpressure, bounded concurrency, batch boyutu, retry jitter, poison job/dead-letter ve graceful degradation davranışlarını iyileştir. Mesaj kaybı ve çift sevk olmamasını invariant olarak test et. Hedef SLO taslağı ile p50/p95/p99 sonuçlarını belgeye yaz, gerekli testleri çalıştır ve commit oluştur.
```

## Prompt 13 — Merkezi gözlemlenebilirlik ve operasyon runbookları

```text
Komşu reposunda metrics/logging/observability kodunu oku. Yalnız merkezi gözlemlenebilirlik katmanını tamamla. PII ve yüksek cardinality kimlik taşımayan yapılandırılmış loglar, API/worker/DB/queue/model/geocoder/WebSocket metrikleri, tracing context, dashboard ve uyarı kuralları ekle. Yerel Compose içinde tekrarlanabilir Prometheus/OpenTelemetry ve uygun dashboard bileşenleri kur; secrets ve rapor metinlerini telemetry'den dışla. Servis durması, kuyruk yaşı, hata oranı ve gecikme eşikleri için test/uyarı kanıtı üret. On-call, incident, manuel koordinasyon ve degraded-mode runbooklarını yaz. Gerekli testleri ve Compose smoke kontrolünü çalıştır, belgeleri güncelle ve commit oluştur.
```

## Prompt 14 — Kimlik, güvenlik ve gizlilik pilot kapıları

```text
Komşu reposunun threat model, auth/RBAC, retention ve deployment belgelerini oku. Yalnız pilot kimlik ve güvenlik kapılarını geliştir. OIDC Authorization Code + PKCE adapterı, MFA claim/policy kontrolü, kısa oturum, revoke, kurum üyeliği ve rol yönetimi ekle; yerel demo token yolunu yalnız development ortamında tut. TLS reverse proxy örneği, merkezi quota, secret rotation, CSRF/CORS/CSP, upload abuse, IDOR, mass assignment ve audit bütünlüğü kontrollerini tamamla. KVKK/GDPR için PII envanteri, veri akışı, sınır ötesi aktarım karar alanları ve hukuk onay kontrol listesini güncelle; hukuk onayı verilmiş gibi davranma. Security/integration testleri, dependency/container taraması ve tehdit modeli fark analizini çalıştır. Bulguları önceliklendir, belgeleri güncelle ve commit oluştur.
```

## Prompt 15 — Yedekleme, geri yükleme ve dağıtım dayanıklılığı

```text
Komşu reposunda deployment ADR, retention ve mevcut restore kanıtını oku. Yalnız yedekleme/geri yükleme ve staging dağıtımını tamamla. Migration 0005 ve şifreli ses dahil yeni mantıksal/fiziksel backup, ayrı ortam restore, anahtar kurtarma/rotasyon, cache/device re-purge ve retention sonrası backup davranışını test et. Tek host Compose dışı staging manifestleri, health/readiness, rolling migration, rollback sınırları, yüksek erişilebilirlik ve offsite şifreli backup tasarımı oluştur. Gerçek bulut/kurum altyapısı yoksa yerel veya geçici testin sınırını yaz; HA iddiası yapma. Restore süresi/veri kaybı ölçümünü kaydet, runbook ve felaket tatbikatını güncelle, testleri çalıştır ve commit oluştur.
```

## Prompt 16 — Uçtan uca pilot provası ve sürüm adayı

```text
Komşu reposunda tüm güncel belgeleri, requirement matrisi ve son commitleri oku. Bu son aşamada önce eksik/başarısız kabul kriterlerini listele; yeni özellik eklemeden yalnız pilot provası ve sürüm adayı hazırlığı yap. Deprem, sel ve orman yangını için TR/EL/EN sentetik senaryoları; text/ses/harici kanal/Android offline/relay/konum/duplicate/insan sevki/retention/restore uçtan uca akışlarını çalıştır. Dil bazlı precision/recall/F1/FNR, duplicate precision/recall, konum hatası, triage süresi, queue latency ve başarısızlık modlarını tek raporda topla. Anadili konuşan incelemesi, gerçek belediye GIS'i, üç fiziksel cihaz, iki kurum, hukuk onayı ve pentest kanıtı sağlanmamışsa ilgili kapıları FAILED veya BLOCKED bırak. Tüm uygun backend/web/Android/security testlerini bir kez çalıştır. Release notes, operasyon/el kitabı, demo senaryosu ve pilot kabul imza listesini hazırla. PROJECT_STATUS ve REQUIREMENTS durumlarını kanıta göre güncelle, release-candidate commit/tag taslağını oluştur; gerçek yayınlama veya production açma için kullanıcıdan son onay iste.
```

## Kullanıcının sağlaması gereken dış girdiler

Bu girdiler olmadan kod geliştirilebilir, fakat proje gerçek pilot için tamamlanmış sayılamaz:

1. Türkçe ve Yunanca anadili konuşan kurtarma dili değerlendiricileri.
2. Açık rızalı, kimliksizleştirilmiş, gürültülü gerçek saha sesleri.
3. Belediye geocoder, hastane, toplanma alanı, barınak, kapalı yol ve lisanslı harita verileri.
4. Seçilen SMS/mesajlaşma/telefon sağlayıcısının sandbox hesapları ve webhook bilgileri.
5. En az üç uygun Android fiziksel cihaz ve farklı Android sürümleri.
6. Kurum OIDC/MFA test tenantı, staging altyapısı ve secret yönetimi.
7. KVKK/GDPR hukuk incelemesi, kurum güvenlik/pentest ve saha tatbikatı katılımcıları.

Kod aşamaları tamamlandıktan sonra bu girdilerle ölçüm ve kurum kabulü yapılır. Son aşama ancak kritik güvenlik bulguları kapandığında, gerçek veri ölçümleri kabul eşiklerini karşıladığında ve yetkili kurumlar yazılı onay verdiğinde production/pilot-ready olarak işaretlenebilir.
