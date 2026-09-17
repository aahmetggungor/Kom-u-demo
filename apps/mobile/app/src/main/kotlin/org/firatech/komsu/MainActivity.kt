package org.firatech.komsu

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class Phrase(val tr:String,val el:String,val en:String)
val phrasebook=listOf(
    Phrase("Beni duyabiliyor musunuz?","Με ακούτε;","Can you hear me?"),
    Phrase("İçeride başka biri var mı?","Υπάρχει κανείς άλλος μέσα;","Is anyone else inside?"),
    Phrase("Kıpırdamayın, geliyoruz.","Μην κουνιέστε, ερχόμαστε.","Don't move, we are coming.")
)

class MainActivity:ComponentActivity() {
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        val app=application as KomsuApplication
        setContent { MaterialTheme(colorScheme=lightColorScheme(primary=Color(0xFF204E5A),surface=Color(0xFFF5F7F4))) { FieldScreen(app) } }
    }
}

@Composable
fun FieldScreen(app:KomsuApplication) {
    val scope=rememberCoroutineScope()
    var tenant by remember { mutableStateOf(app.sessions.tenant()) }
    val reports by remember(tenant) { app.database.reports().observe(tenant) }.collectAsStateWithLifecycle(emptyList())
    val cases by remember(tenant) { app.database.cases().observe(tenant) }.collectAsStateWithLifecycle(emptyList())
    var tab by remember { mutableIntStateOf(0) }
    var text by remember { mutableStateOf("") }
    var language by remember { mutableStateOf("tr") }
    var base by remember { mutableStateOf(app.sessions.base()) }
    var token by remember { mutableStateOf("") }
    var demoMode by remember { mutableStateOf(true) }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var capturedAudio by remember { mutableStateOf<CapturedAudio?>(null) }
    var recordingSeconds by remember { mutableIntStateOf(0) }
    val recorder=remember { PcmRecorder() }
    val context=LocalContext.current
    val permissionLauncher=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if(granted) {
            try { recorder.start(scope);recordingSeconds=0;message="Ses kaydı başladı. En fazla 30 saniye." }
            catch(_:Exception) { message="Ses kaydı başlatılamadı." }
        } else message="Mikrofon izni reddedildi. Metin raporu göndermeye devam edebilirsiniz."
    }
    LaunchedEffect(recorder.isRecording,recordingSeconds) {
        if(recorder.isRecording) {
            kotlinx.coroutines.delay(1000)
            recordingSeconds++
            if(recordingSeconds>=30) {
                try { capturedAudio=recorder.stop();message="30 saniyelik kayıt hazır." }
                catch(_:Exception) { message="Ses kaydı tamamlanamadı." }
            }
        }
    }
    val hostedTextDemo=app.sessions.base().trimEnd('/').equals("https://komsu-demo.onrender.com",ignoreCase=true)
    val repository=remember { ReportRepository(app,app.database) }
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().systemBarsPadding().padding(20.dp)) {
            Text("komşu / γείτονας",style=MaterialTheme.typography.headlineMedium)
            Text("Saha koordinasyonu · Demo 0.1.1",style=MaterialTheme.typography.labelSmall)
            Spacer(Modifier.height(12.dp))
            Text("Sentetik veriyle test edin. AI sevk kararı vermez.",color=Color(0xFF936028),style=MaterialTheme.typography.bodySmall)
            Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                listOf("Raporlar","Sözlük","Vakalar","Bağlantı").forEachIndexed { index,label -> TextButton(onClick={tab=index}) { Text(label) } }
            }
            if(message.isNotEmpty()) { Text(message,color=MaterialTheme.colorScheme.primary);Spacer(Modifier.height(8.dp)) }
            when(tab) {
                0 -> {
                    if(tenant.isEmpty()) Text("Önce Bağlantı bölümünden kurum oturumunu bir kez açın. Sonrasında raporlar çevrimdışı kaydedilebilir.")
                    OutlinedTextField(value=text,onValueChange={if(it.length<=8000)text=it},label={Text("Özgün saha raporu")},modifier=Modifier.fillMaxWidth(),minLines=3,enabled=!busy)
                    Row { listOf("tr","el","en").forEach { code -> FilterChip(selected=language==code,onClick={language=code},label={Text(code.uppercase())},modifier=Modifier.padding(end=8.dp)) } }
                    if(!hostedTextDemo) Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        if(!recorder.isRecording) Button(enabled=!busy,onClick={
                            if(context.checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED) {
                                try { recorder.start(scope);recordingSeconds=0;message="Ses kaydı başladı. En fazla 30 saniye." }
                                catch(_:Exception) { message="Ses kaydı başlatılamadı." }
                            } else permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }) { Text(if(capturedAudio==null)"Ses kaydet" else "Yeniden kaydet") }
                        if(recorder.isRecording) {
                            Button(onClick={scope.launch { try { capturedAudio=recorder.stop();message="Ses kaydı hazır." } catch(_:Exception) { message="Kayıt çok kısa veya bozuk." } }}) { Text("Durdur ${recordingSeconds}s") }
                            TextButton(onClick={scope.launch { runCatching { recorder.stop(discard=true) };message="Ses kaydı iptal edildi." }}) { Text("İptal") }
                        }
                        if(capturedAudio!=null && !recorder.isRecording) TextButton(onClick={capturedAudio=null}) { Text("Sesi kaldır") }
                    }
                    if(hostedTextDemo) Text("Bu demoda metin raporlarını kullanın.",style=MaterialTheme.typography.bodySmall)
                    capturedAudio?.let { Text("WAV hazır · ${it.durationMs/1000.0} sn · ${it.wav.size/1024} KiB",style=MaterialTheme.typography.bodySmall) }
                    Button(enabled=text.isNotBlank() && tenant.isNotEmpty() && !busy && !recorder.isRecording,onClick={
                        busy=true
                        scope.launch { try { repository.create(text,language,tenant,if(hostedTextDemo)null else capturedAudio);text="";capturedAudio=null;message="Rapor ve varsa sesi telefona kaydedildi. Sunucuya ulaşana kadar kuyrukta tutulur." } catch(_:Exception) { message="Rapor kaydedilemedi. Metni ve sesi koruyup yeniden deneyin." } finally { busy=false } }
                    },modifier=Modifier.fillMaxWidth()) { Text("Telefona kaydet ve sıraya al") }
                    if(app.sessions.needsLogin() && tenant.isNotEmpty()) Text("Oturum yenilenmeli. Çevrimdışı kayıtlar korunuyor; Bağlantı bölümünden yeniden giriş yapın.");Text("${reports.count { it.syncStatus in setOf("QUEUED","SYNCING") }} rapor gönderim bekliyor · ${reports.count { it.syncStatus=="CONFLICT" }} çakışma");TextButton(onClick={SyncWorker.schedule(app);message="Bağlantı uygunsa kuyruk yeniden denenecek."}) { Text("Senkronizasyonu yeniden dene") };Spacer(Modifier.height(16.dp));Text("Kalıcı rapor kuyruğu",style=MaterialTheme.typography.titleMedium)
                    val audios by remember(tenant) { app.database.audio().observe(tenant) }.collectAsStateWithLifecycle(emptyList())
                    val audioByReport=audios.associateBy { it.localReportId }
                    LazyColumn { items(reports,key={it.localId}) { report -> Card(Modifier.fillMaxWidth().padding(vertical=5.dp)) { Column(Modifier.padding(12.dp)) { Text(report.text);Text("${report.language.uppercase()} · ${syncLabel(report.syncStatus)} · Deneme ${report.retryCount}",style=MaterialTheme.typography.labelSmall);audioByReport[report.localId]?.let { Text("Ses · ${syncLabel(it.syncStatus)} · Deneme ${it.retryCount}",style=MaterialTheme.typography.labelSmall) }; report.errorCode?.let { Text(syncErrorLabel(it),style=MaterialTheme.typography.bodySmall) } } } } }
                }
                1 -> LazyColumn { item { Text("Çevrimdışı TR / EL / EN sözlük",style=MaterialTheme.typography.titleMedium);Text("Kayıtlı ses paketi henüz eklenmedi; saha dil doğrulaması bekleniyor.",style=MaterialTheme.typography.bodySmall) }; items(phrasebook) { phrase -> Card(Modifier.fillMaxWidth().padding(vertical=8.dp)) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) { Text(phrase.tr);Text(phrase.el);Text(phrase.en) } } } }
                2 -> { Text("Son indirilen vakalar",style=MaterialTheme.typography.titleMedium);Text("Son alınan ilk 100 vaka gösterilir. Çevrimdışı bilgiler güncel olmayabilir. Bu uygulamadan sevk yapılmaz.",style=MaterialTheme.typography.bodySmall);LazyColumn { items(cases,key={it.id}) { cached -> val item=JSONObject(cached.json);Card(Modifier.fillMaxWidth().padding(vertical=6.dp)) { Column(Modifier.padding(12.dp)) { Text("#${cached.id.take(8)} · ${item.optString("urgency_level")}");Text(item.optString("status"));Text("Önbellek: ${java.time.Instant.ofEpochMilli(cached.cachedAt)}",style=MaterialTheme.typography.labelSmall) } } } } }
                3 -> { Row { Checkbox(checked=demoMode,onCheckedChange={demoMode=it});Text("Render demo şifresiyle giriş") };OutlinedTextField(value=base,onValueChange={base=it},label={Text("Kurum API adresi")},modifier=Modifier.fillMaxWidth());OutlinedTextField(value=token,onValueChange={token=it},label={Text(if(demoMode) "Demo şifresi" else "Geçici erişim anahtarı")},visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth());Button(enabled=!busy,onClick={busy=true;scope.launch {try { val credential=withContext(Dispatchers.IO) { if(demoMode) FieldNetwork.demoLogin(base,token) else DemoCredential(token,0) };val identity=withContext(Dispatchers.IO) { FieldNetwork.get(base to credential.token,"/api/v1/auth/me") };check(identity.getString("role") in setOf("admin","coordinator","rescue-team"));val newTenant=identity.getString("tenant_id");app.sessions.save(base,credential.token,newTenant,credential.expiresAt);tenant=newTenant;token="";app.database.reports().resumeAuthenticated(tenant);app.database.audio().resumeAuthenticated(tenant);SyncWorker.schedule(app);message="Oturum doğrulandı. Senkronizasyon sıraya alındı." } catch(_:Exception) {message="Bağlantı veya kimlik doğrulama başarısız. Anahtar ve adresi kontrol edin."} finally{busy=false} }}){Text("Doğrula ve bağlan")};Text("Bluetooth / Wi-Fi Direct aktarımı araştırma aşamasında. Donanım bağlantısı bu sürümde etkin değil.",style=MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
