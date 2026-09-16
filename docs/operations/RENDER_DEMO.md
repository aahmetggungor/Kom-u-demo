# Render synthetic demo

Connect the GitHub main branch as a Blueprint using render.yaml. Both resources explicitly
use the free plan in Frankfurt. The database rejects external connections. All seeded
messages are synthetic. Never import real incident reports into this deployment.

The web dashboard and API share the HTTPS hostname. KOMSU_DEMO_PASSWORD is generated
by Render; retrieve it privately in the service environment dashboard. Password login
issues an eight-hour coordinator token kept in browser memory. Refresh requires login.
Runtime processes have neither the migration database credentials nor token-table grants.
Startup fails closed if the provider cannot create the restricted komsu_app role or extensions.

The baseline worker runs with the web service. Large embedding, translation and speech
models are disabled in this free deployment. Disk uploads are ephemeral; use text reports.
Free services sleep after inactivity; the free database expires after 30 days. This is
a presentation deployment, not an operational disaster service.

Android source is apps/mobile. GitHub Actions builds the debug demo APK and uploads
komsu-demo-android-apk as a downloadable artifact. Android connects to this same HTTPS API;
an APK is installed on a phone rather than hosted as an executing Render service.

Demo URL: https://komsu-demo.onrender.com
In Android, open Bağlantı, keep Render demo password login enabled, enter the same demo
password and select Doğrula ve bağlan. Only the resulting token is encrypted in session
storage; the password is cleared. Enter text reports while offline, reconnect, and
verify the reports appear in the web dashboard. Speech models are disabled here.
