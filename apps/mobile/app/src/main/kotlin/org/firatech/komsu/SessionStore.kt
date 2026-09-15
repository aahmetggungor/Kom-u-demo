package org.firatech.komsu

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Hardware-backed where available; private preferences hold only ciphertext and public API URI. */
class SessionStore(context:Context) {
    private val prefs=context.getSharedPreferences("session",Context.MODE_PRIVATE)
    private val alias="komsu-session-v1"
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias,null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun tenant():String = prefs.getString("tenant", "") ?: ""
    fun save(baseUrl:String,token:String,tenantId:String) {
        java.util.UUID.fromString(tenantId)
        val uri=java.net.URI(baseUrl)
        require(uri.userInfo==null && uri.query==null && uri.fragment==null && (uri.path.isNullOrEmpty() || uri.path=="/"))
        require(uri.scheme=="https" || (BuildConfig.DEBUG && uri.scheme=="http" && uri.host in setOf("10.0.2.2","127.0.0.1","localhost")))
        require(token.length in 32..256)
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE,key()) }
        val encrypted=cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        check(prefs.edit().putString("tenant",tenantId).putString("base",baseUrl.trimEnd('/')).putString("iv",Base64.encodeToString(cipher.iv,Base64.NO_WRAP)).putString("token",Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit())
    }
    fun read():Triple<String,String,String>? = try {
        val snapshot=prefs.all
        val base=snapshot["base"] as? String
        val encrypted=snapshot["token"] as? String
        val iv=snapshot["iv"] as? String
        val tenantId=snapshot["tenant"] as? String
        if(base==null || encrypted==null || iv==null || tenantId==null) null else {
            val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(iv,Base64.NO_WRAP))) }
            Triple(base,String(cipher.doFinal(Base64.decode(encrypted,Base64.NO_WRAP)),Charsets.UTF_8),tenantId)
        }
    } catch(_:Exception) { null }
}
