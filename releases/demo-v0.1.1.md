# Komşu demo 0.1.1 — ara verme sürümü

Giriş korumalı sentetik metin demosu: https://komsu-demo.onrender.com

Android 8.0+ için `komsu-demo-v0.1.1.apk` dosyasını aşağıdaki Assets bölümünden indirin. Web ve Android aynı Render demo şifresini kullanır. Şifre herkese açık kaynak kodunda yer almaz.

- README ve web demosunda kalıcı APK / kullanım rehberi bağlantıları.
- Web girişinde bekleme durumu, iki dakikalık timeout ve TR/EL/EN hata mesajları.
- Ücretsiz barındırılan demoda kullanılamayan ses ekleme kontrolleri gizlendi; metin raporları kullanılabilir.
- Android sürümü 0.1.1-demo / versionCode 2; çevrimdışı rapor kuyruğu ve oturum yenileme checkpoint'i korundu.
- Kullanım rehberi: https://github.com/aahmetggungor/Kom-u-demo/blob/main/docs/DEMO_GUIDE.md
- Devam noktası: https://github.com/aahmetggungor/Kom-u-demo/blob/main/docs/PAUSE_HANDOFF.md

Doğrulama: 11 web testi ve hosted build; Android APK, 7 app birim testi, 7 Pixel 7 / Android 14 instrumentation testi ve lint (0 hata, 14 uyarı) başarılı. 7 relay testi mevcut başarılı Gradle cache'inden doğrulandı. Backend kodu değiştirilmedi; önceki checkpoint'te 108 standart + 11 PostgreSQL testi geçmişti.

Bu APK debug demo imzasını kullanır; Play Store / üretim sürümü değildir. Önceki Actions APK'sı farklı imzalı olabilir. Android güncellemeyi reddederse uygulamayı kaldırmadan önce bekleyen raporları senkronize edin; kaldırmak yerel kayıtları siler.

Render dashboard mevcut ücretsiz veritabanının **16 Ekim 2026** tarihinde sona ereceğini gösteriyor. Bu tarihten sonra sunucu erişimi plan değişikliği / yeniden kurulum gerektirebilir. GitHub APK indirmesi devam eder. Ağır AI modelleri, gerçek harita/GIS/mesaj sağlayıcıları ve fiziksel cihaz aktarımı etkin değildir. Geliştirme bu checkpoint'te duraklatıldı.

APK SHA-256: ead66eeafb00a25d144c1aa30d2f878385a588f17c42e779616736c5355f15ef

Boyut: 10120373 bayt. Assets içindeki SHA256SUMS.txt dosyasıyla doğrulanabilir.
