package org.firatech.komsu

import org.junit.Assert.assertEquals
import org.junit.Test

class SyncPolicyTest {
    @Test fun transientErrorsRetry() { listOf(408,429,500,503).forEach { assertEquals(SyncStatus.QUEUED,classifyHttp(it)) } }
    @Test fun conflictsAreNotSilentlyOverwritten() { assertEquals(SyncStatus.CONFLICT,classifyHttp(409)) }
    @Test fun authAndValidationStopAutomaticRetries() { listOf(401,403,422,400).forEach { assertEquals(SyncStatus.FAILED,classifyHttp(it)) } }
    @Test fun successRequiresServerReceipt() { assertEquals(SyncStatus.SYNCED,classifyHttp(202));assertEquals(SyncStatus.FAILED,classifyHttp(204)) }
}
