# Geliştirmeye ara verme ve devam noktası

Tarih: 18 Eylül 2026. Demo sürümü: `demo-v0.1.1`. Yeni geliştirme aşamalarına geçilmeden demo checkpoint'i kaydedildi.

## Kaynak ve barındırma

- GitHub: https://github.com/aahmetggungor/Kom-u-demo — yayımlanan dal `main`.
- Yerel ana repo: `C:/Users/rog/Documents/Codex/2026-09-14/files-mentioned-by-the-user-ahmet/outputs/komsu`; yerel dal `master`, uzak dal `origin/main`.
- Render: https://komsu-demo.onrender.com; servis `srv-dal8745bedkc73bk4k80`.
- Render Blueprint: `render.yaml`; GitHub `main` güncellemeleri otomatik deploy edilir.
- Veritabanı: `dpg-dal86qtbedkc73bk3nv0-a`, PostgreSQL 17, ücretsiz plan. Dashboard'dan doğrulanan sona erme tarihi: 16 Ekim 2026.
- APK'nın kalıcı sürüm sayfası: https://github.com/aahmetggungor/Kom-u-demo/releases/tag/demo-v0.1.1

Sırlar GitHub'a eklenmez. Render Environment ve yerel ignored `.env` dosyaları ayrı tutulur. Yerel Android debug anahtarı `C:/Users/rog/.android/debug.keystore` dosyasındadır; güncelleme imzasını korumak için saklanmalıdır, GitHub'a yüklenmemelidir.

## Nerede kaldık?

Prompt 9 tamamlandı: kurum kapsamlı inbound sözleşmesi, HMAC/zaman kontrolü, tekrar teslim kaydı, atomik rapor/ses/receipt işlemi ve PostgreSQL kota eşzamanlılığı. Migration head `0010`. Gerçek sağlayıcı hesabı bağlı değil.

Prompt 10 kısmen tamamlandı: Android'de sunucunun bildirdiği oturum ömrü, süresi dolan kimlik bilgisinin güvenli iptali, kurum ve çevrimdışı kuyruğun korunması, yeniden girişle gönderimin sürmesi ve kayıtlı API adresi. Ayrıntı: [Android stabilization](operations/ANDROID_STABILIZATION.md).

Ara verme rötuşları: APK 0.1.1 / versionCode 2; web girişinde bekleme, timeout ve anlaşılır hata mesajları; web ve README'de Releases indirme bağlantısı; barındırılan metin demosunda kullanılamayan ses ekleme kontrollerinin gizlenmesi. Ağır modeller, dış harita ve sağlayıcılar etkinleştirilmedi.

## Doğrulama kayıtları

Önceki backend checkpoint'inde 108 standart ve 11 gerçek PostgreSQL testi geçti. Yeni backend özelliği eklenmedi. Web'in 11 testi ve hosted-demo build'i; Android APK, app/relay birim testleri ve lint bu sürümde tekrar kontrol edilir. Son emulator checkpoint'inde Pixel 7 / Android 14 üzerinde 7 instrumentation testi geçti. Son sürümün kesin sonuçları GitHub Release notlarında ve PROJECT_STATUS belgesindedir. Bunlar fiziksel saha doğrulaması değildir.

## Devam sırası

1. Önce repo durumunu, Release notlarını, Render servis/veritabanı sağlığını ve [PROJECT_STATUS](../PROJECT_STATUS.md) belgesini okuyun. Kullanıcının yeni kapsamını teyit ederek mevcut checkpoint'ten devam edin.
2. [EXECUTION_PROMPTS](EXECUTION_PROMPTS.md) içindeki Prompt 10'u tamamlayın: sürümlü/checksum'lı üç dilli ifade paketi, güvenli profesyonel ses paketi doğrulama/import ve erişilebilirlik/yerleşim provası. Profesyonel kayıt ve anadil değerlendirmesi henüz sağlanmadı.
3. Ardından Prompt 11 fiziksel cihaz aktarımı, Prompt 12 yük/hata dayanıklılığı, Prompt 13 merkezi izleme. Gerçek GIS/geocoder/mesaj sağlayıcısı entegrasyonları veri, izin ve servis erişimlerine bağlıdır.

Render veritabanı sona ermişse mevcut kaydı silmeyin. Önce dashboard durumunu ve varsa yedeği inceleyin. Kalıcı erişim için kullanıcıyla plan seçin; ücretli yükseltmeyi otomatik yapmayın. Yeni ücretsiz veritabanıyla sentetik demo yeniden kurulabilir, ancak eski test kayıtları yedeksiz taşınamaz. Veritabanını değiştirme/silme bu checkpoint'in parçası değildir.

## Sonraki oturum için istem

> Komşu projesine devam ediyoruz. Önce README, PROJECT_STATUS.md, docs/PAUSE_HANDOFF.md, docs/operations/ANDROID_STABILIZATION.md ve docs/EXECUTION_PROMPTS.md dosyalarını oku. demo-v0.1.1 checkpoint'ini, yerel git durumunu ve Render veritabanının süresini doğrula. Bitmiş işleri tekrar yapmadan Prompt 10'un kalan ifade/ses paketi ve erişilebilirlik işlerinden devam et. Gerçek veri/servis yokken sentetik sözleşmeler kullan, eksikleri açık tut ve demo APK'sının güncelleme imzasını koru.
