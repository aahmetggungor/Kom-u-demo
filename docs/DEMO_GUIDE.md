# Komşu demo 0.1.1 — kullanım ve test

Geliştirme 18 Eylül 2026 tarihinde duraklatıldı. Bu sürüm sentetik verilerle sunum içindir; gerçek afet operasyonuna hazır değildir.

## İndirme ve giriş

- Web: https://komsu-demo.onrender.com
- Android APK: [komsu-demo-v0.1.1.apk](https://github.com/aahmetggungor/Kom-u-demo/releases/download/demo-v0.1.1/komsu-demo-v0.1.1.apk)
- Sürüm ve doğrulama dosyası: [GitHub Releases](https://github.com/aahmetggungor/Kom-u-demo/releases/tag/demo-v0.1.1)

Şifreyi Render → **komsu-demo** → **Environment** → `KOMSU_DEMO_PASSWORD` alanından alın. Web ve Android'de aynı şifre geçerlidir. Şifreyi README'ye veya herkese açık mesajlara koymayın. Şifreyi bilmeyenler panel verilerine erişemez; APK'yı indirebilirler.

Android 8.0 ve üzeri gerekir. APK'yı telefon tarayıcısından indirin, Android sorarsa yalnız bu tarayıcı için uygulama yükleme izni verin ve dosyayı açın. Bu bir debug demo APK'sıdır; Play Store / üretim sürümü değildir. Uygulamada API adresi `https://komsu-demo.onrender.com` ve demo girişi seçili olmalıdır. Bağlantı bölümünden giriş yapın.

Önceki test APK'sı farklı imzalıysa Android güncellemeyi reddedebilir. **Uygulamayı kaldırmadan önce bekleyen raporları senkronize edin.** Kaldırma, telefondaki yerel kayıtları siler. Bu yayımlanan APK yerel geliştirme anahtarıyla imzalanmıştır; gelecekte aynı anahtarla üretilen APK kullanılmalıdır. Actions APK'sının imzası farklı olabilir.

## Beş dakikalık gösterim

1. Web demosunu açıp giriş yapın. İlk açılış Render uykusundan uyanırken yaklaşık bir dakika sürebilir. Sayfa henüz açılmıyorsa bir süre sonra yenileyin.
2. Vaka listesini, Türkçe/İngilizce/Yunanca arayüz seçimini ve filtreleri deneyin. Altlık harita henüz bağlı değildir; konum çalışma alanı rapor noktalarını gösterir.
3. Web'den bir **sentetik** metin raporu ekleyin: `DEMO: İzmir test bölgesinde 2 kişi için su ve barınma gerekiyor.` İşlendikten sonra özgün mesajı vaka ayrıntısında kontrol edin.
4. Sentetik bir vakada konum ve gerekçeyi doğrulayın; ardından test ekibine insan onayıyla sevk edin. AI önerisi kesin karar değildir.
5. Android'den aynı demo şifresiyle giriş yapın; uçak modunda farklı bir test raporu kaydedin. Uygulamayı kapatıp açınca kuyrukta kaldığını kontrol edin. İnterneti açıp yeniden gönderin; web panelinde aynı raporun bir kez göründüğünü kontrol edin.

Oturum sekiz saat sonra biter. Android'de yeniden giriş mevcut kurumun bekleyen raporlarını koruyarak gönderimi sürdürür. Web taslağı sekme kapanınca korunmaz; çevrimdışı kayıt Android uygulamasındadır.

## Bu demodaki sınırlar

Metin raporu, kalıcı sunucu kuyruğu, canlı vaka listesi, insan doğrulaması/sevk ve Android çevrimdışı kuyruğu gösterilebilir. Ücretsiz sunucuda ağır benzerlik/çeviri/ses modelleri etkin değildir. Ses ekleme kontrolleri bu barındırılan demo için gizlenmiştir. Gerçek harita servisi, kurumsal GIS, SMS/mesaj sağlayıcısı ve fiziksel Bluetooth/Wi-Fi aktarımı bağlı değildir. Aynı şifreyi kullanan demo ziyaretçileri aynı sentetik kurumun kayıtlarını görür; özel kullanıcı hesapları değildir.

## Ara boyunca erişim

Render'ın ücretsiz web servisi 15 dakika hareketsiz kaldığında uyur. **Ücretsiz PostgreSQL veritabanı oluşturulduktan 30 gün sonra sona erer.** Mevcut veritabanının son tarihi Render ekranından doğrulandı: **16 Ekim 2026**. Sona erince panel ve Android sunucu bağlantısı çalışmaz. GitHub kodu ve Releases APK indirmesi bu tarihten bağımsızdır.

Kaynak: [Render ücretsiz plan sınırları](https://render.com/docs/free). Ücretsiz veritabanında otomatik yedek yoktur. Bu çalışma sırasında Render veritabanının yedeği alınmadı; gösterim kayıtlarını kalıcı arşiv olarak kullanmayın. Daha uzun erişim gerekirse süre dolmadan veritabanı için ücretli plan veya farklı barındırma kararı verilmelidir. Bu sürüm hazırlanırken ücretli hizmet açılmadı.

## Sorun giderme

- Giriş geçersiz: Render'daki güncel `KOMSU_DEMO_PASSWORD` değerini kullanın.
- Çok fazla giriş denemesi: bir dakika bekleyin.
- Servis hazır değil: [hazırlık kontrolünü](https://komsu-demo.onrender.com/health/ready) ve Render Events/Logs ekranını kontrol edin; veritabanının süresi dolmuş olabilir.
- Android raporu bekliyor: bağlantıyı ve oturumu kontrol edip aynı kurumla tekrar giriş yapın; yeniden gönderin. Kuyruğu temizlemeyin veya uygulamayı kaldırmayın.

Yerel kurulum README'dedir. PowerShell'de Python'u `./.venv/Scripts/python.exe`, npm'i `npm.cmd` şeklinde çağırın; npm komutlarını `apps/web` dizininde çalıştırın. Böylece `npm.ps1` yürütme ilkesi hatasına gerek kalmaz.
