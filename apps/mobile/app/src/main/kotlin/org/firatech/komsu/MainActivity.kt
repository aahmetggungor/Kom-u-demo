package org.firatech.komsu

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
    var base by remember { mutableStateOf(if(BuildConfig.DEBUG) "http://10.0.2.2:8000" else "") }
    var token by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val repository=remember { ReportRepository(app,app.database) }
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().systemBarsPadding().padding(20.dp)) {
            Text("komşu / γείτονας",style=MaterialTheme.typography.headlineMedium)
            Text("Saha koordinasyonu · Geliştirme sürümü",style=MaterialTheme.typography.labelSmall)
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
                    Button(enabled=text.isNotBlank() && tenant.isNotEmpty() && !busy,onClick={
                        busy=true
                        scope.launch { try { repository.create(text,language,tenant);text="";message="Telefona kaydedildi. Sunucuya ulaşana kadar kuyrukta tutulur." } catch(_:Exception) { message="Rapor kaydedilemedi. Metni koruyup yeniden deneyin." } finally { busy=false } }
                    },modifier=Modifier.fillMaxWidth()) { Text("Telefona kaydet ve sıraya al") }
                    Spacer(Modifier.height(16.dp));Text("Kalıcı rapor kuyruğu",style=MaterialTheme.typography.titleMedium)
                    LazyColumn { items(reports,key={it.localId}) { report -> Card(Modifier.fillMaxWidth().padding(vertical=5.dp)) { Column(Modifier.padding(12.dp)) { Text(report.text);Text("${report.language.uppercase()} · ${report.syncStatus} · Deneme ${report.retryCount}",style=MaterialTheme.typography.labelSmall); report.errorCode?.let { Text(it,style=MaterialTheme.typography.bodySmall) } } } } }
                }
                1 -> LazyColumn { item { Text("Çevrimdışı TR / EL / EN sözlük",style=MaterialTheme.typography.titleMedium);Text("Kayıtlı ses paketi henüz eklenmedi; saha dil doğrulaması bekleniyor.",style=MaterialTheme.typography.bodySmall) }; items(phrasebook) { phrase -> Card(Modifier.fillMaxWidth().padding(vertical=8.dp)) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(7.dp)) { Text(phrase.tr);Text(phrase.el);Text(phrase.en) } } } }
                2 -> { Text("Son indirilen vakalar",style=MaterialTheme.typography.titleMedium);Text("Son alınan ilk 100 vaka gösterilir. Çevrimdışı bilgiler güncel olmayabilir. Bu uygulamadan sevk yapılmaz.",style=MaterialTheme.typography.bodySmall);LazyColumn { items(cases,key={it.id}) { cached -> val item=JSONObject(cached.json);Card(Modifier.fillMaxWidth().padding(vertical=6.dp)) { Column(Modifier.padding(12.dp)) { Text("#${cached.id.take(8)} · ${item.optString("urgency_level")}");Text(item.optString("status"));Text("Önbellek: ${java.time.Instant.ofEpochMilli(cached.cachedAt)}",style=MaterialTheme.typography.labelSmall) } } } } }
                3 -> { OutlinedTextField(value=base,onValueChange={base=it},label={Text("Kurum API adresi")},modifier=Modifier.fillMaxWidth());OutlinedTextField(value=token,onValueChange={token=it},label={Text("Geçici erişim anahtarı")},visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth());Button(enabled=!busy,onClick={busy=true;scope.launch {try { val identity=withContext(Dispatchers.IO) { FieldNetwork.get(base to token,"/api/v1/auth/me") };val newTenant=identity.getString("tenant_id");app.sessions.save(base,token,newTenant);tenant=newTenant;token="";app.database.reports().resumeAuthenticated(tenant);SyncWorker.schedule(app);message="Oturum doğrulandı. Senkronizasyon sıraya alındı." } catch(_:Exception) {message="Bağlantı veya kimlik doğrulama başarısız. Anahtar ve adresi kontrol edin."} finally{busy=false} }}){Text("Doğrula ve bağlan")};Text("Bluetooth / Wi-Fi Direct aktarımı araştırma aşamasında. Donanım bağlantısı bu sürümde etkin değil.",style=MaterialTheme.typography.bodySmall) }
            }
        }
    }
}
