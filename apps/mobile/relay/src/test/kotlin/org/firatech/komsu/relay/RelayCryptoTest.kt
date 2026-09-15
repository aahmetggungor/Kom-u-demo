package org.firatech.komsu.relay

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.security.KeyPairGenerator
import java.util.UUID
import javax.crypto.KeyGenerator

class RelayCryptoTest {
    private val tenant = UUID.randomUUID()
    private fun unsigned(ciphertext: ByteArray) = Envelope(
        UUID.randomUUID(), tenant, 1_000L, 61_000L, 3, 0, ciphertext, byteArrayOf()
    )

    @Test fun originSignatureCoversImmutableEnvelopeAndAllowsHopIncrement() {
        val pair = KeyPairGenerator.getInstance("EC").apply { initialize(256) }.generateKeyPair()
        val signed = signOrigin(unsigned(byteArrayOf(4, 5, 6)), pair.private)
        val verifier = EcOriginVerifier(pair.public)
        assertTrue(verifier.verify(signed))
        assertTrue(verifier.verify(signed.copy(hops = 2)))
        assertFalse(verifier.verify(signed.copy(ciphertext = byteArrayOf(4, 5, 7))))
        assertFalse(verifier.verify(signed.copy(expiresAt = signed.expiresAt + 1)))
    }

    @Test fun authenticatedEncryptionRejectsCiphertextAndContextTampering() {
        val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        val cipher = AesGcmPayloadCipher(key)
        val context = "tenant-and-message".toByteArray()
        val sealed = cipher.seal("synthetic report".toByteArray(), context)
        assertArrayEquals("synthetic report".toByteArray(), cipher.open(sealed, context))
        sealed[sealed.lastIndex] = (sealed.last() + 1).toByte()
        assertThrows(SecurityException::class.java) { cipher.open(sealed, context) }
        assertThrows(SecurityException::class.java) {
            cipher.open(cipher.seal("x".toByteArray(), context), "other-message".toByteArray())
        }
    }
}
