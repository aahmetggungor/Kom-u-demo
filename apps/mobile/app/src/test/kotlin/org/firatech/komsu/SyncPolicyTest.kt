package org.firatech.komsu

import java.nio.ByteBuffer
import java.nio.ByteOrder
import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncPolicyTest {
    private fun rejects(block:()->Unit) {
        try { block();fail("Expected invalid audio to be rejected") }
        catch(_:IllegalArgumentException) { }
    }
    @Test fun transientErrorsRetry() { listOf(408,429,500,503).forEach { assertEquals(SyncStatus.QUEUED,classifyHttp(it)) } }
    @Test fun conflictsAreNotSilentlyOverwritten() { assertEquals(SyncStatus.CONFLICT,classifyHttp(409)) }
    @Test fun authAndValidationStopAutomaticRetries() { listOf(401,403,422,400).forEach { assertEquals(SyncStatus.FAILED,classifyHttp(it)) } }
    @Test fun successRequiresServerReceipt() { assertEquals(SyncStatus.SYNCED,classifyHttp(202));assertEquals(SyncStatus.FAILED,classifyHttp(204)) }
    @Test fun audioUploadClassifiesReplayAndAuthExplicitly() {
        listOf(200,201).forEach { assertEquals(SyncStatus.SYNCED,classifyAudioHttp(it)) }
        assertEquals(SyncStatus.CONFLICT,classifyAudioHttp(409))
        listOf(401,403,422).forEach { assertEquals(SyncStatus.FAILED,classifyAudioHttp(it)) }
        listOf(408,429,500,503).forEach { assertEquals(SyncStatus.QUEUED,classifyAudioHttp(it)) }
    }
    @Test fun pcmWavIsBoundedAndRejectsSilenceOrMalformedData() {
        val pcm=ByteBuffer.allocate(6_400).order(ByteOrder.LITTLE_ENDIAN).apply {
            repeat(3_200) { putShort(if(it%2==0) 7_000 else -7_000) }
        }.array()
        val captured=PcmWav.encode(pcm)
        assertEquals(200,PcmWav.validate(captured.wav))
        assertTrue(captured.wav.size<2_000_000)
        rejects { PcmWav.encode(ByteArray(6_400)) }
        rejects { PcmWav.validate(captured.wav.copyOf(30)) }
        rejects { PcmWav.encode(ByteArray(PcmWav.maxPcmBytes+2) { 1 }) }
    }
}
