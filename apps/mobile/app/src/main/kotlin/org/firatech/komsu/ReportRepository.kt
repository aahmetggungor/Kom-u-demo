package org.firatech.komsu

import android.content.Context
import androidx.room.withTransaction
import java.io.File
import java.util.UUID

object AudioFiles {
    fun file(context: Context, tenantId: String, localReportId: String): File {
        UUID.fromString(tenantId)
        UUID.fromString(localReportId)
        val directory = File(context.filesDir, "report-audio/$tenantId")
        check(directory.mkdirs() || directory.isDirectory)
        return File(directory, "$localReportId.wav")
    }
}

class ReportRepository(private val context:Context,private val database:FieldDatabase) {
    suspend fun create(
        text:String,
        language:String,
        tenantId:String,
        audio:CapturedAudio?=null,
    ):String {
        require(text.isNotBlank() && text.length<=8000)
        require(language in setOf("tr","el","en"))
        UUID.fromString(tenantId)
        val report=LocalReport(text=text,language=language,tenantId=tenantId)
        val audioFile = audio?.let {
            require(PcmWav.validate(it.wav) == it.durationMs)
            AudioFiles.file(context,tenantId,report.localId)
        }
        try {
            audioFile?.writeBytes(audio!!.wav)
            database.withTransaction {
                database.reports().insert(report)
                if(audio != null) database.audio().insert(
                    LocalAudio(report.localId,tenantId,audio.durationMs,audio.wav.size)
                )
            }
        } catch(error:Exception) {
            audioFile?.delete()
            throw error
        }
        // If scheduling is interrupted by process death, Application startup schedules another drain.
        SyncWorker.schedule(context)
        return report.localId
    }
}
