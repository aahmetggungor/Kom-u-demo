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

class RoomCustodyStore(private val dao:RelayDao):CustodyStore {
    override fun retainIfNew(envelope:Envelope):Boolean = dao.retain(
        RelayEnvelopeRow(envelope.tenantId.toString(),envelope.messageId.toString(),
            envelope.createdAt,envelope.expiresAt,envelope.maxHops,envelope.hops,
            envelope.ciphertext.copyOf(),envelope.signature.copyOf())) != -1L
}
