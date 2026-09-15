package org.firatech.komsu.relay

import java.util.UUID

/** Payload must already be sealed and signed by the origin. Transport never sees report PII. */
data class Envelope(
    val messageId: UUID,
    val tenantId: UUID,
    val createdAt: Long,
    val expiresAt: Long,
    val maxHops: Int,
    val hops: Int,
    val ciphertext: ByteArray,
    val signature: ByteArray
)

enum class Acceptance { ACCEPT, SEEN, EXPIRED, INVALID, WRONG_TENANT, HOP_LIMIT, UNTRUSTED }

interface CustodyStore {
    /**
     * Atomically persist the complete envelope and its deduplication key before returning true.
     * Return false only when durable custody already exists. Throw on storage failure: callers
     * must not acknowledge ACCEPT/SEEN until this transaction commits. Retain through expiry.
     */
    fun retainIfNew(envelope: Envelope): Boolean
}

fun interface OriginVerifier { fun verify(envelope: Envelope): Boolean }

interface RelayTransport {
    /** Call only within an explicit user-visible relay session after permission checks. */
    suspend fun send(peerId: String, envelope: Envelope): Boolean
}

class RelayPolicy(private val tenantId: UUID, private val custody: CustodyStore, private val verifier: OriginVerifier) {
    fun accept(envelope: Envelope, now: Long): Acceptance {
        if (envelope.tenantId != tenantId) return Acceptance.WRONG_TENANT
        if (envelope.ciphertext.isEmpty() || envelope.ciphertext.size > 32768 || envelope.signature.isEmpty() ||
            envelope.maxHops !in 1..8 || envelope.hops < 0 || envelope.expiresAt <= envelope.createdAt ||
            envelope.expiresAt - envelope.createdAt > 24 * 60 * 60 * 1000L || envelope.createdAt > now + 300000L) return Acceptance.INVALID
        if (envelope.expiresAt <= now) return Acceptance.EXPIRED
        if (envelope.hops >= envelope.maxHops) return Acceptance.HOP_LIMIT
        if (!verifier.verify(envelope)) return Acceptance.UNTRUSTED
        return if (custody.retainIfNew(envelope)) Acceptance.ACCEPT else Acceptance.SEEN
    }
}
