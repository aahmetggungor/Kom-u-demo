package org.firatech.komsu

import androidx.room.testing.MigrationTestHelper
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import java.io.IOException
import java.util.UUID

class RelayMigrationTest {
    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        FieldDatabase::class.java,
    )

    @Test
    @Throws(IOException::class)
    fun versionOneQueueMigratesWithoutLossAndAddsCustody() {
        val name = "migration-${UUID.randomUUID()}.db"
        val localId = UUID.randomUUID().toString()
        val tenant = UUID.randomUUID().toString()
        helper.createDatabase(name, 1).apply {
            execSQL(
                "INSERT INTO reports(localId,serverId,caseId,text,language,tenantId,createdAt," +
                    "syncStatus,lastAttempt,retryCount,version,errorCode) VALUES(?,NULL,NULL,?,?" +
                    ",?,?,?,0,0,1,NULL)",
                arrayOf(localId, "Synthetic migration report", "en", tenant,
                    "2026-09-15T00:00:00Z", "QUEUED"),
            )
            close()
        }
        helper.runMigrationsAndValidate(name, 2, true, MIGRATION_1_2).apply {
            query("SELECT text,tenantId FROM reports WHERE localId=?", arrayOf(localId)).use {
                it.moveToFirst()
                assertEquals("Synthetic migration report", it.getString(0))
                assertEquals(tenant, it.getString(1))
            }
            query("SELECT count(*) FROM relay_custody").use {
                it.moveToFirst()
                assertEquals(0, it.getInt(0))
            }
            close()
        }
        InstrumentationRegistry.getInstrumentation().targetContext.deleteDatabase(name)
    }
}
