package io.aura.personal

import java.net.URL
import java.io.ByteArrayInputStream
import java.security.cert.Certificate
import javax.net.ssl.HttpsURLConnection
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class) @Config(sdk=[33])
class UpdateTransportTest {
    class Response(url:String,private val code:Int,private val body:String="",private val etag:String?=null):HttpsURLConnection(URL(url)){
        override fun connect(){}
        override fun disconnect(){}
        override fun usingProxy()=false
        override fun getResponseCode()=code
        override fun getInputStream()=ByteArrayInputStream(body.toByteArray())
        override fun getHeaderField(name:String?):String?=if(name=="ETag")etag else null
        override fun getCipherSuite()="TLS_TEST"
        override fun getLocalCertificates():Array<Certificate>?=null
        override fun getServerCertificates():Array<Certificate> = emptyArray()
    }
    @Test fun revalidatesCachedReleaseInsteadOfReturningStaleSuccess(){
        val url="https://api.github.com/test/aura/conditional"
        assertEquals(1,UpdateClient.json(url){Response(it,200,"{\"id\":1}","\"v1\"")}.getInt("id"))
        val unchanged=Response(url,304)
        assertEquals(1,UpdateClient.json(url){unchanged}.getInt("id"))
        assertEquals("\"v1\"",unchanged.getRequestProperty("If-None-Match"))
        assertEquals("no-cache",unchanged.getRequestProperty("Cache-Control"))
        assertThrows(IllegalArgumentException::class.java){UpdateClient.json(url){Response(it,500)}}
        assertEquals(2,UpdateClient.json(url){Response(it,200,"{\"id\":2}","\"v2\"")}.getInt("id"))
    }
    @Test fun rejectsUnsolicitedNotModifiedAndOversizedJson(){
        assertThrows(IllegalArgumentException::class.java){UpdateClient.json("https://api.github.com/test/aura/missing"){Response(it,304)}}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.json("https://api.github.com/test/aura/large"){Response(it,200,"x".repeat(262145))}}
    }
}
