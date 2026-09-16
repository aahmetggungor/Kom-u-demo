# Demo erişimi

2026-09-16. Geliştirme demosu; yalnız sentetik veri içindir.

## Tek adresten yerel demo

Repo kökünde Docker Desktop açıkken:

```powershell
docker compose -f docker-compose.yml -f compose.demo.yml up -d --build web api
.venv\Scripts\python.exe scripts/refresh_demo_session.py
```

Panel: `http://127.0.0.1:8080`. Mevcut gitignored `.env.session.json` içindeki token ile giriş yapılır. Dosyayı GitHub'a yüklemeyin. İlk kurulumda README'deki configure/provision/seed adımlarını tamamlayın. Panel ve API aynı adresten çalışır; Caddy API ve WebSocket trafiğini iç Docker ağı üzerinden iletir. DB ve doğrudan API portları loopback üzerinde kalır.

Yerel kontrolde web/API/DB sağlıklı, HTML ve readiness 200, yetkili vaka listesi ve WebSocket event akışı çalışmıştır. Bu kontrol farklı fiziksel cihazdan erişim kanıtı değildir.

## Aynı Wi-Fi üzerinden

Bilgisayarın aktif Wi-Fi IPv4 adresini belirleyin. Aşağıdaki örnekte `192.168.1.50` yerine kendi adresinizi yazın:

```powershell
$env:KOMSU_DEMO_BIND='0.0.0.0'
$env:KOMSU_DEMO_ALLOWED_ORIGINS='["http://192.168.1.50:8080","http://127.0.0.1:8080","http://localhost:8080"]'
docker compose -f docker-compose.yml -f compose.demo.yml up -d web api
```

Telefon aynı ağa bağlanıp `http://192.168.1.50:8080` adresini açar. Windows güvenlik duvarında gerekirse yalnız özel ağ için TCP 8080 erişimi tanımlanır. Router'da port yönlendirmesi açılmaz. HTTP LAN adreslerinde tarayıcı mikrofonu güvenli bağlam şartı nedeniyle kullanılamayabilir; mikrofon demosu için HTTPS gerekir. Bilgisayar veya Docker kapanırsa erişim kesilir.

## İnternet demosu ve kalıcı sunucu

Geçici paylaşım için bu tek-adresli servisin önüne bir HTTPS tunnel; kalıcı demo için Docker çalıştıran sunucu ve HTTPS reverse proxy kullanılabilir. Dış URL, `KOMSU_DEMO_ALLOWED_ORIGINS` listesine tam origin olarak eklenmelidir; wildcard açılmaz. Kaynak kod GitHub'da tutulabilir, fakat GitHub Pages yalnız statik hosting sağlar; API/PostgreSQL/worker için ayrıca çalışma ortamı gerekir.

İnternete çıkmadan önce ayrı demo veritabanı/tenant, yalnız sentetik seed, ayrı kısa ömürlü demo oturumları ve dış URL üzerinden login/WS kontrolü hazırlanır. Mevcut yerel raporlar ve credential dosyaları yayın ortamına kopyalanmaz. GitHub repo URL'si, seçilen sunucu/hosting erişimi ve varsa alan adı gerekir. Secret'lar sohbet veya repo içine yazılmaz; sağlayıcının secret ayarları kullanılır.

Kaynaklar: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/). Erişim: 2026-09-16.
