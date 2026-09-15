package org.firatech.komsu

import android.content.Context

class ReportRepository(private val context:Context,private val database:FieldDatabase) {
    suspend fun create(text:String,language:String,tenantId:String):String {
        require(text.isNotBlank() && text.length<=8000)
        require(language in setOf("tr","el","en"))
        java.util.UUID.fromString(tenantId)
        val report=LocalReport(text=text,language=language,tenantId=tenantId)
        database.reports().insert(report)
        // If scheduling is interrupted by process death, Application startup schedules another drain.
        SyncWorker.schedule(context)
        return report.localId
    }
}
