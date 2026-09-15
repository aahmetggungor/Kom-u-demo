package org.firatech.komsu

import androidx.room.Room
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Test
import java.util.UUID
import org.firatech.komsu.relay.Acceptance
import org.firatech.komsu.relay.Envelope
import org.firatech.komsu.relay.OriginVerifier
import org.firatech.komsu.relay.RelayPolicy

class QueuePersistenceTest {
    @Test fun relayCustodyCommitsEnvelopeBeforeAckAndSurvivesReopen()=runBlocking {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val name="relay-test-${UUID.randomUUID()}.db"
        val tenant=UUID.randomUUID();val message=UUID.randomUUID();val now=1_000L
        val envelope=Envelope(message,tenant,now,now+60_000,3,0,byteArrayOf(1,2),byteArrayOf(3,4))
        var db=Room.databaseBuilder(context,FieldDatabase::class.java,name).addMigrations(MIGRATION_1_2).build()
        try {
            var policy=RelayPolicy(tenant,RoomCustodyStore(db.relay()),OriginVerifier { true })
            assertEquals(Acceptance.ACCEPT,policy.accept(envelope,now))
            assertArrayEquals(envelope.ciphertext,db.relay().get(tenant.toString(),message.toString())!!.ciphertext)
            db.close()
            db=Room.databaseBuilder(context,FieldDatabase::class.java,name).addMigrations(MIGRATION_1_2).build()
            policy=RelayPolicy(tenant,RoomCustodyStore(db.relay()),OriginVerifier { true })
            assertEquals(Acceptance.SEEN,policy.accept(envelope.copy(hops=1),now+1))
            assertEquals(1,db.relay().count(tenant.toString()))
            assertEquals(1,db.relay().purgeExpired(now+60_001))
            assertEquals(0,db.relay().count(tenant.toString()))
        } finally { db.close();context.deleteDatabase(name) }
    }
    @Test fun cacheSnapshotRemovesMergedRowsOnlyForItsTenant()=runBlocking {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val name="cache-test-${UUID.randomUUID()}.db"
        val db=Room.databaseBuilder(context,FieldDatabase::class.java,name).build()
        val a=UUID.randomUUID().toString();val b=UUID.randomUUID().toString()
        val old=CachedCase(UUID.randomUUID().toString(),a,"{}",1000,1)
        val other=CachedCase(UUID.randomUUID().toString(),b,"{}",1000,1)
        val current=CachedCase(UUID.randomUUID().toString(),a,"{}",2000,2)
        try {
            db.cases().save(listOf(old,other))
            db.cases().replaceSnapshot(a,listOf(current))
            assertEquals(listOf(current),db.cases().observe(a).first())
            assertEquals(listOf(other),db.cases().observe(b).first())
            try { db.cases().replaceSnapshot(a,listOf(other));fail("cross-tenant snapshot accepted") } catch(_:IllegalArgumentException) { }
            assertEquals(listOf(current),db.cases().observe(a).first())
            db.cases().replaceSnapshot(a,emptyList())
            assertTrue(db.cases().observe(a).first().isEmpty())
            assertEquals(listOf(other),db.cases().observe(b).first())
        } finally { db.close();context.deleteDatabase(name) }
    }
    @Test fun queueSurvivesReopenAndClaimsOnce()=runBlocking {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val name="queue-test-${UUID.randomUUID()}.db"
        val tenant=UUID.randomUUID().toString()
        var db=Room.databaseBuilder(context,FieldDatabase::class.java,name).build()
        val report=LocalReport(text="Synthetic offline report",language="en",tenantId=tenant)
        try {
            db.reports().insert(report);db.close()
            db=Room.databaseBuilder(context,FieldDatabase::class.java,name).build()
            assertEquals(report.text,db.reports().get(report.localId)?.text)
            assertEquals(1,db.reports().claim(report.localId,1000))
            assertEquals(0,db.reports().claim(report.localId,2000))
            db.close()
            db=Room.databaseBuilder(context,FieldDatabase::class.java,name).build()
            db.reports().recover(500)
            assertTrue(db.reports().queued(tenant).isEmpty())
            assertEquals(1,db.reports().pendingCount(tenant))
            assertEquals(0,db.reports().pendingCount(UUID.randomUUID().toString()))
            db.reports().recover(3000)
            assertEquals(1,db.reports().queued(tenant).size)
            assertTrue(db.reports().queued(UUID.randomUUID().toString()).isEmpty())
            assertEquals(1,db.reports().claim(report.localId,4000))
            assertEquals(0,db.reports().finish(report.localId,1000,"SYNCED",null,"server",null))
            assertEquals(1,db.reports().finish(report.localId,4000,"CONFLICT","HTTP_409",null,null))
            assertEquals("CONFLICT",db.reports().get(report.localId)?.syncStatus)
            assertEquals(0,db.reports().pendingCount(tenant))
        } finally { db.close();context.deleteDatabase(name) }
    }
    @Test fun audioQueueSurvivesReopenAndRemainsTenantScoped()=runBlocking {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val name="audio-queue-${UUID.randomUUID()}.db"
        val tenant=UUID.randomUUID().toString();val other=UUID.randomUUID().toString()
        val report=LocalReport(text="Synthetic voice report",language="en",tenantId=tenant)
        var db=Room.databaseBuilder(context,FieldDatabase::class.java,name).addMigrations(MIGRATION_1_2,MIGRATION_2_3).build()
        try {
            db.reports().insert(report)
            db.audio().insert(LocalAudio(report.localId,tenant,500,16_044))
            db.close()
            db=Room.databaseBuilder(context,FieldDatabase::class.java,name).addMigrations(MIGRATION_1_2,MIGRATION_2_3).build()
            assertEquals(1,db.audio().queued(tenant).size)
            assertTrue(db.audio().queued(other).isEmpty())
            assertEquals(1,db.audio().claim(report.localId,tenant,1_000))
            assertEquals(0,db.audio().claim(report.localId,tenant,2_000))
            db.close()
            db=Room.databaseBuilder(context,FieldDatabase::class.java,name).addMigrations(MIGRATION_1_2,MIGRATION_2_3).build()
            assertEquals(1,db.audio().pendingCount(tenant))
            db.audio().recover(2_000)
            assertEquals(1,db.audio().queued(tenant).size)
            assertEquals(0,db.audio().finish(report.localId,tenant,1_000,"SYNCED",null))
            assertEquals(1,db.audio().claim(report.localId,tenant,3_000))
            assertEquals(1,db.audio().finish(report.localId,tenant,3_000,"SYNCED",null))
        } finally { db.close();context.deleteDatabase(name) }
    }
}
