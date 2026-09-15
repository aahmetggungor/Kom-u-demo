package org.firatech.komsu

import android.app.Application
import androidx.room.Room

class KomsuApplication:Application() {
    val database by lazy { Room.databaseBuilder(this,FieldDatabase::class.java,"komsu-field.db").addMigrations(MIGRATION_1_2).build() }
    val sessions by lazy { SessionStore(this) }
    override fun onCreate() { super.onCreate(); SyncWorker.schedule(this) }
}
