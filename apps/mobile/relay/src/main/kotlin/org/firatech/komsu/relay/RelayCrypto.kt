package org.firatech.komsu.relay

import java.nio.ByteBuffer
import java.security.PrivateKey
import java.security.PublicKey
import java.security.SecureRandom
import java.security.Signature
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Hop count is transport metadata and is deliberately excluded from the origin signature. */
fun Envelope.signedBytes(): ByteArray {
    val ciphertextLength = ciphertext.size
    return ByteBuffer.allocate(16 + 16 + 8 + 8 + 4 + 4 + ciphertextLength)
        .putLong(messageId.mostSignificantBits).putLong(messageId.leastSignificantBits)
        .putLong(tenantId.mostSignificantBits).putLong(tenantId.leastSignificantBits)
        .putLong(createdAt).putLong(expiresAt).putInt(maxHops)
        .putInt(ciphertextLength).put(ciphertext).array()
}

class EcOriginVerifier(private val trustedKey: PublicKey) : OriginVerifier {
    override fun verify(envelope: Envelope): Boolean = try {
        Signature.getInstance("SHA256withECDSA").run {
            initVerify(trustedKey)
            update(envelope.signedBytes())
            verify(envelope.signature)
        }
    } catch (_: Exception) { false }
}

fun signOrigin(envelope: Envelope, privateKey: PrivateKey): Envelope {
    require(envelope.signature.isEmpty())
    val signature = Signature.getInstance("SHA256withECDSA").run {
        initSign(privateKey)
        update(envelope.signedBytes())
        sign()
    }
    return envelope.copy(signature = signature)
}

class AesGcmPayloadCipher(private val key: SecretKey, private val random: SecureRandom = SecureRandom()) {
    fun seal(plaintext: ByteArray, associatedData: ByteArray): ByteArray {
        require(plaintext.size <= 30_000)
        val nonce = ByteArray(12).also(random::nextBytes)
        val sealed = Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, nonce))
            updateAAD(associatedData)
            doFinal(plaintext)
        }
        return nonce + sealed
    }

    fun open(ciphertext: ByteArray, associatedData: ByteArray): ByteArray {
        require(ciphertext.size in 29..32_768)
        val nonce = ciphertext.copyOfRange(0, 12)
        return try {
            Cipher.getInstance("AES/GCM/NoPadding").run {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, nonce))
                updateAAD(associatedData)
                doFinal(ciphertext.copyOfRange(12, ciphertext.size))
            }
        } catch (error: AEADBadTagException) {
            throw SecurityException("Relay payload authentication failed", error)
        }
    }
}
