package org.firatech.komsu

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import org.firatech.komsu.relay.CustodyStore
import org.firatech.komsu.relay.Envelope

val MIGRATION_1_2 = object : Migration(1,2) {
    override fun migrate(db:SupportSQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS `relay_custody` (
            `tenantId` TEXT NOT NULL, `messageId` TEXT NOT NULL,
            `createdAt` INTEGER NOT NULL, `expiresAt` INTEGER NOT NULL,
            `maxHops` INTEGER NOT NULL, `hops` INTEGER NOT NULL,
            `ciphertext` BLOB NOT NULL, `signature` BLOB NOT NULL,
            PRIMARY KEY(`tenantId`,`messageId`))""")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_relay_custody_tenantId_expiresAt` ON `relay_custody` (`tenantId`,`expiresAt`)")
    }
}

val MIGRATION_2_3 = object : Migration(2,3) {
    override fun migrate(db:SupportSQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS `report_audio` (
            `localReportId` TEXT NOT NULL, `tenantId` TEXT NOT NULL,
            `durationMs` INTEGER NOT NULL, `byteCount` INTEGER NOT NULL,
            `syncStatus` TEXT NOT NULL, `lastAttempt` INTEGER NOT NULL,
            `retryCount` INTEGER NOT NULL, `errorCode` TEXT,
            PRIMARY KEY(`localReportId`),
            FOREIGN KEY(`localReportId`) REFERENCES `reports`(`localId`) ON UPDATE NO ACTION ON DELETE CASCADE)""")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_report_audio_tenantId_syncStatus_lastAttempt` ON `report_audio` (`tenantId`,`syncStatus`,`lastAttempt`)")
    }
}

class RoomCustodyStore(private val dao:RelayDao):CustodyStore {
    override fun retainIfNew(envelope:Envelope):Boolean = dao.retain(
        RelayEnvelopeRow(envelope.tenantId.toString(),envelope.messageId.toString(),
            envelope.createdAt,envelope.expiresAt,envelope.maxHops,envelope.hops,
            envelope.ciphertext.copyOf(),envelope.signature.copyOf())) != -1L
}
