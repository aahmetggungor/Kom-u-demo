package org.firatech.komsu

fun sessionExpired(expiresAt:Long,now:Long):Boolean = expiresAt>0 && now>=expiresAt

fun syncLabel(status:String):String = when(status) {
    "LOCAL_ONLY" -> "Telefonda kayıtlı"
    "QUEUED" -> "Bağlantı bekliyor"
    "SYNCING" -> "Gönderiliyor"
    "SYNCED" -> "Sunucuya ulaştı"
    "CONFLICT" -> "Kimlik çakışması · inceleme gerekli"
    else -> "Gönderim durdu · inceleme gerekli"
}

fun syncErrorLabel(code:String):String = when(code) {
    "AUTH_REQUIRED" -> "Oturum yenilenmeli. Rapor telefonda korunuyor. Bağlantı bölümünden yeniden giriş yapın."
    "NETWORK_ERROR" -> "Bağlantı kurulamadı. Rapor bağlantı geldiğinde yeniden gönderilecek."
    "RECOVERED_INTERRUPTED_SYNC" -> "Yarım kalan gönderim güvenli biçimde yeniden sıraya alındı."
    "HTTP_409", "REPORT_CONFLICT" -> "Bu rapor kimliği sunucuda farklı içerikle kayıtlı. Kaydı değiştirmeden koordinatöre danışın."
    else -> "Gönderim tamamlanamadı. Kayıt telefonda korunuyor."
}
