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

class SyncWorker(context:Context,params:WorkerParameters):CoroutineWorker(context,params) {
    override suspend fun doWork():Result=withContext(Dispatchers.IO) {
        val app=applicationContext as KomsuApplication
        val dao=app.database.reports()
        dao.recover(System.currentTimeMillis()-300000)
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
            if(outcome.error=="AUTH_REQUIRED") return@withContext Result.failure()
        }
        try {
            val json=FieldNetwork.get(session.first to session.second,"/api/v1/cases?limit=100")
            val items=json.getJSONArray("items")
            app.database.cases().replaceSnapshot(tenant,(0 until items.length()).map { index -> val item=items.getJSONObject(index); CachedCase(item.getString("id"),tenant,item.toString(),System.currentTimeMillis(),item.getInt("version")) })
        } catch(_:Exception) { /* Existing cache remains, timestamp shows staleness. */ }
        if(retry || dao.pendingCount(tenant)>0) Result.retry() else Result.success()
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
