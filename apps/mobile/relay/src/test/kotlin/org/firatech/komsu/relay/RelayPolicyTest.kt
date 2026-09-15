package org.firatech.komsu.relay

import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.UUID

class RelayPolicyTest {
    private val tenant = UUID.randomUUID()
    private val now = 1_000_000L
    private fun envelope() = Envelope(UUID.randomUUID(), tenant, now, now + 60000, 3, 0, byteArrayOf(1), byteArrayOf(2))
    private fun policy(trusted: Boolean = true): RelayPolicy {
        val ids = mutableSetOf<UUID>()
        return RelayPolicy(tenant, object: CustodyStore { override fun retainIfNew(envelope: Envelope) = ids.add(envelope.messageId) }, OriginVerifier { trusted })
    }
    @Test fun duplicateLoopIsRejected() { val p=policy(); val e=envelope(); assertEquals(Acceptance.ACCEPT,p.accept(e,now)); assertEquals(Acceptance.SEEN,p.accept(e.copy(hops=1),now)) }
    @Test fun expiredAndExhaustedDoNotRelay() { val p=policy(); assertEquals(Acceptance.EXPIRED,p.accept(envelope(),now+60001)); assertEquals(Acceptance.HOP_LIMIT,p.accept(envelope().copy(hops=3),now)) }
    @Test fun rejectsTenantAndUntrustedOrigin() { assertEquals(Acceptance.WRONG_TENANT,policy().accept(envelope().copy(tenantId=UUID.randomUUID()),now)); assertEquals(Acceptance.UNTRUSTED,policy(false).accept(envelope(),now)) }
    @Test fun sizeAndFutureTimestampBounded() { assertEquals(Acceptance.INVALID,policy().accept(envelope().copy(ciphertext=ByteArray(32769)),now)); assertEquals(Acceptance.INVALID,policy().accept(envelope().copy(createdAt=now+400000),now)) }
    @Test fun failedStorageCannotAcknowledgeAndRetryCanPersist() {
        var fail=true
        val retained=mutableMapOf<UUID,Envelope>()
        val p=RelayPolicy(tenant,object:CustodyStore {
            override fun retainIfNew(envelope:Envelope):Boolean {
                if(fail) throw java.io.IOException("synthetic disk failure")
                return retained.putIfAbsent(envelope.messageId,envelope)==null
            }
        },OriginVerifier { true })
        val e=envelope()
        org.junit.Assert.assertThrows(java.io.IOException::class.java) { p.accept(e,now) }
        assertEquals(0,retained.size)
        fail=false
        assertEquals(Acceptance.ACCEPT,p.accept(e,now))
        assertEquals(e,retained[e.messageId])
        assertEquals(Acceptance.SEEN,p.accept(e,now))
    }
}
