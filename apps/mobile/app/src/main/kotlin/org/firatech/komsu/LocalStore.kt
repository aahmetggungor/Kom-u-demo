package org.firatech.komsu

import androidx.room.*
import kotlinx.coroutines.flow.Flow
import java.time.Instant
import java.util.UUID
import org.firatech.komsu.relay.Envelope

enum class SyncStatus { LOCAL_ONLY, QUEUED, SYNCING, SYNCED, FAILED, CONFLICT }

@Entity(tableName = "reports", indices = [Index(value = ["syncStatus", "lastAttempt"])])
data class LocalReport(
    @PrimaryKey val localId: String = UUID.randomUUID().toString(),
    val serverId: String? = null,
    val caseId: String? = null,
    val text: String,
    val language: String,
    val tenantId: String,
    val createdAt: String = Instant.now().toString(),
    val syncStatus: String = SyncStatus.QUEUED.name,
    val lastAttempt: Long = 0,
    val retryCount: Int = 0,
    val version: Int = 1,
    val errorCode: String? = null
)

@Entity(
    tableName = "report_audio",
    foreignKeys = [
        ForeignKey(
            entity = LocalReport::class,
            parentColumns = ["localId"],
            childColumns = ["localReportId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index(value = ["tenantId", "syncStatus", "lastAttempt"])],
)
data class LocalAudio(
    @PrimaryKey val localReportId: String,
    val tenantId: String,
    val durationMs: Int,
    val byteCount: Int,
    val syncStatus: String = SyncStatus.QUEUED.name,
    val lastAttempt: Long = 0,
    val retryCount: Int = 0,
    val errorCode: String? = null,
)

@Entity(tableName="cached_cases")
data class CachedCase(@PrimaryKey val id: String, val tenantId:String, val json: String, val cachedAt: Long, val version: Int)

@Dao
interface ReportDao {
    @Query("SELECT * FROM reports WHERE tenantId=:tenant ORDER BY createdAt DESC") fun observe(tenant:String): Flow<List<LocalReport>>
    @Insert(onConflict = OnConflictStrategy.ABORT) suspend fun insert(report: LocalReport)
    @Query("SELECT * FROM reports WHERE syncStatus='QUEUED' AND tenantId=:tenant ORDER BY createdAt LIMIT 50") suspend fun queued(tenant:String): List<LocalReport>
    @Query("UPDATE reports SET syncStatus='SYNCING', lastAttempt=:now, retryCount=retryCount+1 WHERE localId=:id AND syncStatus='QUEUED'") suspend fun claim(id:String, now:Long):Int
    @Query("UPDATE reports SET syncStatus=:status, errorCode=:error, serverId=:serverId, caseId=:caseId WHERE localId=:id AND syncStatus='SYNCING' AND lastAttempt=:claimTime") suspend fun finish(id:String, claimTime:Long, status:String, error:String?, serverId:String?, caseId:String?):Int
    @Query("UPDATE reports SET syncStatus='QUEUED', errorCode='RECOVERED_INTERRUPTED_SYNC' WHERE syncStatus='SYNCING' AND lastAttempt<:cutoff") suspend fun recover(cutoff:Long)
    @Query("UPDATE reports SET syncStatus='QUEUED', errorCode=NULL WHERE tenantId=:tenant AND syncStatus='FAILED' AND errorCode='AUTH_REQUIRED'") suspend fun resumeAuthenticated(tenant:String)
    // A recent interrupted claim must keep WorkManager retrying until its lease expires.
    @Query("SELECT COUNT(*) FROM reports WHERE syncStatus IN ('QUEUED','SYNCING') AND tenantId=:tenant") suspend fun pendingCount(tenant:String):Int
    @Query("SELECT * FROM reports WHERE localId=:id") suspend fun get(id:String):LocalReport?
}

@Dao
interface AudioDao {
    @Query("SELECT * FROM report_audio WHERE tenantId=:tenant")
    fun observe(tenant: String): Flow<List<LocalAudio>>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insert(audio: LocalAudio)

    @Query("SELECT * FROM report_audio WHERE syncStatus='QUEUED' AND tenantId=:tenant ORDER BY localReportId LIMIT 50")
    suspend fun queued(tenant: String): List<LocalAudio>

    @Query("UPDATE report_audio SET syncStatus='SYNCING', lastAttempt=:now, retryCount=retryCount+1 WHERE localReportId=:id AND tenantId=:tenant AND syncStatus='QUEUED'")
    suspend fun claim(id: String, tenant: String, now: Long): Int

    @Query("UPDATE report_audio SET syncStatus=:status, errorCode=:error WHERE localReportId=:id AND tenantId=:tenant AND syncStatus='SYNCING' AND lastAttempt=:claimTime")
    suspend fun finish(
        id: String,
        tenant: String,
        claimTime: Long,
        status: String,
        error: String?,
    ): Int

    @Query("UPDATE report_audio SET syncStatus='QUEUED', errorCode='RECOVERED_INTERRUPTED_SYNC' WHERE syncStatus='SYNCING' AND lastAttempt<:cutoff")
    suspend fun recover(cutoff: Long)

    @Query("UPDATE report_audio SET syncStatus='QUEUED', errorCode=NULL WHERE tenantId=:tenant AND syncStatus='FAILED' AND errorCode='AUTH_REQUIRED'")
    suspend fun resumeAuthenticated(tenant: String)

    @Query("SELECT COUNT(*) FROM report_audio WHERE syncStatus IN ('QUEUED','SYNCING') AND tenantId=:tenant")
    suspend fun pendingCount(tenant: String): Int

    @Query("SELECT * FROM report_audio WHERE localReportId=:id AND tenantId=:tenant")
    suspend fun get(id: String, tenant: String): LocalAudio?

    @Query("UPDATE report_audio SET syncStatus=:status, errorCode=:error WHERE localReportId=:id AND tenantId=:tenant AND syncStatus IN ('QUEUED','SYNCING')")
    suspend fun blockForReport(id: String, tenant: String, status: String, error: String?): Int
}

@Dao
interface CaseDao {
    @Query("SELECT * FROM cached_cases WHERE tenantId=:tenant ORDER BY cachedAt DESC LIMIT 100") fun observe(tenant:String):Flow<List<CachedCase>>
    @Insert(onConflict=OnConflictStrategy.REPLACE) suspend fun save(cases:List<CachedCase>)
    @Query("DELETE FROM cached_cases WHERE tenantId=:tenant") suspend fun clearTenant(tenant:String)
    @Transaction suspend fun replaceSnapshot(tenant:String,cases:List<CachedCase>) {
        require(cases.all { it.tenantId==tenant })
        clearTenant(tenant)
        save(cases)
    }
}

@Entity(
    tableName="relay_custody",
    primaryKeys=["tenantId","messageId"],
    indices=[Index(value=["tenantId","expiresAt"])]
)
data class RelayEnvelopeRow(
    val tenantId:String,
    val messageId:String,
    val createdAt:Long,
    val expiresAt:Long,
    val maxHops:Int,
    val hops:Int,
    val ciphertext:ByteArray,
    val signature:ByteArray
) {
    fun envelope()=Envelope(UUID.fromString(messageId),UUID.fromString(tenantId),createdAt,
        expiresAt,maxHops,hops,ciphertext,signature)
}

@Dao
interface RelayDao {
    @Insert(onConflict=OnConflictStrategy.IGNORE) fun retain(row:RelayEnvelopeRow):Long
    @Query("SELECT * FROM relay_custody WHERE tenantId=:tenant AND messageId=:messageId") fun get(tenant:String,messageId:String):RelayEnvelopeRow?
    @Query("DELETE FROM relay_custody WHERE expiresAt<=:now") suspend fun purgeExpired(now:Long):Int
    @Query("SELECT COUNT(*) FROM relay_custody WHERE tenantId=:tenant") suspend fun count(tenant:String):Int
}

@Database(
    entities=[LocalReport::class,CachedCase::class,RelayEnvelopeRow::class,LocalAudio::class],
    version=3,
    exportSchema=true,
)
abstract class FieldDatabase:RoomDatabase() {
    abstract fun reports():ReportDao
    abstract fun audio():AudioDao
    abstract fun cases():CaseDao
    abstract fun relay():RelayDao
}
