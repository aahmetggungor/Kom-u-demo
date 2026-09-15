package org.firatech.komsu

import android.content.Context
import androidx.work.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

data class UploadResult(val status:SyncStatus,val error:String?=null,val serverId:String?=null,val caseId:String?=null)
fun classifyHttp(code:Int):SyncStatus=when(code) { 200,202->SyncStatus.SYNCED;409->SyncStatus.CONFLICT;408,429->SyncStatus.QUEUED;in 500..599->SyncStatus.QUEUED;else->SyncStatus.FAILED }
fun classifyAudioHttp(code:Int):SyncStatus=when(code) { 200,201->SyncStatus.SYNCED;409->SyncStatus.CONFLICT;408,429->SyncStatus.QUEUED;in 500..599->SyncStatus.QUEUED;else->SyncStatus.FAILED }

class SyncWorker(context:Context,params:WorkerParameters):CoroutineWorker(context,params) {
    override suspend fun doWork():Result=withContext(Dispatchers.IO) {
        val app=applicationContext as KomsuApplication
        val dao=app.database.reports()
        val audioDao=app.database.audio()
        dao.recover(System.currentTimeMillis()-300000)
        audioDao.recover(System.currentTimeMillis()-300000)
        val session=app.sessions.read()
        if(session==null) return@withContext Result.failure()
        var retry=false
        val tenant=session.third
        for(report in dao.queued(tenant)) {
            val claimTime=System.currentTimeMillis()
            if(dao.claim(report.localId,claimTime)!=1) continue
            val outcome=upload(session,report)
            dao.finish(report.localId,claimTime,outcome.status.name,outcome.error,outcome.serverId,outcome.caseId)
            if(outcome.status==SyncStatus.QUEUED) retry=true
            if(outcome.status==SyncStatus.CONFLICT) audioDao.blockForReport(report.localId,tenant,SyncStatus.CONFLICT.name,"REPORT_CONFLICT")
            if(outcome.status==SyncStatus.FAILED && outcome.error!="AUTH_REQUIRED") audioDao.blockForReport(report.localId,tenant,SyncStatus.FAILED.name,"REPORT_FAILED")
            if(outcome.error=="AUTH_REQUIRED") return@withContext Result.failure()
        }
        for(audio in audioDao.queued(tenant)) {
            val report=dao.get(audio.localReportId)
            val serverId=report?.serverId ?: continue
            val claimTime=System.currentTimeMillis()
            if(audioDao.claim(audio.localReportId,tenant,claimTime)!=1) continue
            val outcome=uploadAudio(session,serverId,audio)
            val finished=audioDao.finish(audio.localReportId,tenant,claimTime,outcome.status.name,outcome.error)
            if(finished==1 && outcome.status==SyncStatus.SYNCED) AudioFiles.file(applicationContext,tenant,audio.localReportId).delete()
            if(outcome.status==SyncStatus.QUEUED) retry=true
            if(outcome.error=="AUTH_REQUIRED") return@withContext Result.failure()
        }
        try {
            val json=FieldNetwork.get(session.first to session.second,"/api/v1/cases?limit=100")
            val items=json.getJSONArray("items")
            app.database.cases().replaceSnapshot(tenant,(0 until items.length()).map { index -> val item=items.getJSONObject(index); CachedCase(item.getString("id"),tenant,item.toString(),System.currentTimeMillis(),item.getInt("version")) })
        } catch(_:Exception) { /* Existing cache remains, timestamp shows staleness. */ }
        if(retry || dao.pendingCount(tenant)>0 || audioDao.pendingCount(tenant)>0) Result.retry() else Result.success()
    }
    private fun uploadAudio(
        session:Triple<String,String,String>,
        serverReportId:String,
        audio:LocalAudio,
    ):UploadResult {
        var connection:HttpURLConnection?=null
        return try {
            val file=AudioFiles.file(applicationContext,audio.tenantId,audio.localReportId)
            if(!file.isFile) return UploadResult(SyncStatus.FAILED,"AUDIO_FILE_MISSING")
            if(file.length()!=audio.byteCount.toLong() || file.length()>2_000_000) return UploadResult(SyncStatus.FAILED,"AUDIO_FILE_INVALID")
            val bytes=file.readBytes()
            if(bytes.size!=audio.byteCount || PcmWav.validate(bytes)!=audio.durationMs) {
                return UploadResult(SyncStatus.FAILED,"AUDIO_FILE_INVALID")
            }
            connection=URL(session.first+"/api/v1/reports/$serverReportId/audio").openConnection() as HttpURLConnection
            connection.requestMethod="POST";connection.connectTimeout=10000;connection.readTimeout=15000;connection.instanceFollowRedirects=false
            connection.setRequestProperty("Authorization","Bearer ${session.second}");connection.setRequestProperty("Content-Type","audio/wav");connection.doOutput=true
            connection.setFixedLengthStreamingMode(bytes.size)
            connection.outputStream.use { it.write(bytes) }
            val code=connection.responseCode
            val state=classifyAudioHttp(code)
            UploadResult(state,if(code==401 || code==403) "AUTH_REQUIRED" else if(state==SyncStatus.SYNCED)null else "HTTP_$code")
        } catch(_:java.io.IOException) { UploadResult(SyncStatus.QUEUED,"NETWORK_ERROR") }
          catch(_:Exception) { UploadResult(SyncStatus.FAILED,"AUDIO_FILE_INVALID") }
          finally { connection?.disconnect() }
    }
    private fun upload(session:Triple<String,String,String>,report:LocalReport):UploadResult {
        var connection:HttpURLConnection?=null
        return try {
            connection=URL(session.first+"/api/v1/reports").openConnection() as HttpURLConnection
            connection.requestMethod="POST";connection.connectTimeout=10000;connection.readTimeout=15000;connection.instanceFollowRedirects=false
            connection.setRequestProperty("Authorization","Bearer ${session.second}");connection.setRequestProperty("Content-Type","application/json");connection.doOutput=true
            val body=JSONObject().put("client_id",report.localId).put("text",report.text).put("source","android").put("language",report.language).put("occurred_at",report.createdAt)
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            val code=connection.responseCode
            val state=classifyHttp(code)
            if(state==SyncStatus.SYNCED) {
                val bytes=connection.inputStream.use { FieldNetwork.readBounded(it,32768) }
                require(bytes.size<=32768)
                val json=JSONObject(String(bytes,Charsets.UTF_8))
                UploadResult(state,serverId=json.getString("report_id"),caseId=json.getString("case_id"))
            } else UploadResult(state,if(code==401 || code==403) "AUTH_REQUIRED" else "HTTP_$code")
        } catch(_:java.io.IOException) { UploadResult(SyncStatus.QUEUED,"NETWORK_ERROR") }
          catch(_:Exception) { UploadResult(SyncStatus.FAILED,"INVALID_RESPONSE") }
          finally { connection?.disconnect() }
    }
    companion object {
        fun schedule(context:Context) {
            val constraints=Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
            val work=OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(constraints).setBackoffCriteria(BackoffPolicy.EXPONENTIAL,30,TimeUnit.SECONDS).build()
            WorkManager.getInstance(context).enqueueUniqueWork("report-sync",ExistingWorkPolicy.APPEND_OR_REPLACE,work)
        }
    }
}
