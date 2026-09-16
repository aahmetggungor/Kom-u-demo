package org.firatech.komsu

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

object FieldNetwork {
    fun demoLogin(base:String,password:String):String {
        val uri=URI(base)
        require(uri.scheme=="https" && uri.host!=null && uri.userInfo==null && uri.query==null && uri.fragment==null && (uri.path.isNullOrEmpty() || uri.path=="/"))
        require(password.length in 1..256)
        val connection=URL(base.trimEnd('/')+"/api/v1/demo/session").openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout=15000;connection.readTimeout=90000;connection.instanceFollowRedirects=false
            connection.requestMethod="POST";connection.doOutput=true
            connection.setRequestProperty("Content-Type","application/json")
            val body=JSONObject().put("password",password).toString().toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(body.size)
            connection.outputStream.use { it.write(body) }
            check(connection.responseCode==200) { "Demo login failed" }
            val token=JSONObject(String(connection.inputStream.use { readBounded(it,4096) },Charsets.UTF_8)).getString("token")
            require(token.length in 32..256)
            token
        } finally { connection.disconnect() }
    }
    fun readBounded(input:InputStream,limit:Int):ByteArray {
        val output=ByteArrayOutputStream();val chunk=ByteArray(4096)
        while(true) { val count=input.read(chunk);if(count<0)break;require(output.size()+count<=limit);output.write(chunk,0,count) }
        return output.toByteArray()
    }
    fun get(session:Pair<String,String>,path:String):JSONObject {
        val uri=URI(session.first)
        require(uri.userInfo==null && uri.query==null && uri.fragment==null && (uri.path.isNullOrEmpty() || uri.path=="/"))
        require(uri.scheme=="https" || (BuildConfig.DEBUG && uri.scheme=="http" && uri.host in setOf("10.0.2.2","127.0.0.1","localhost")))
        val connection=URL(session.first.trimEnd('/')+path).openConnection() as HttpURLConnection
        return try {
            connection.connectTimeout=10000;connection.readTimeout=15000;connection.instanceFollowRedirects=false
            connection.setRequestProperty("Authorization","Bearer ${session.second}")
            check(connection.responseCode==200) { "Authentication or connection failed" }
            JSONObject(String(connection.inputStream.use { readBounded(it,524288) },Charsets.UTF_8))
        } finally { connection.disconnect() }
    }
}
