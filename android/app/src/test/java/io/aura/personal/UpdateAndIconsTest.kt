package io.aura.personal

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.drawable.BitmapDrawable
import android.util.Base64
import android.util.LruCache
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.ImageView
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[33])
class UpdateAndIconsTest {
    private val url="https://github.com/Kotomineee/AURA/releases/download/v0.1.2/AURA-Android-0.1.2.apk"
    private fun release()=JSONObject().put("tag_name","v0.1.2").put("published_at","2026-10-21T00:00:00Z").put("assets",JSONArray().put(JSONObject().put("name","AURA-Android-0.1.2.apk").put("browser_download_url",url)).put(JSONObject().put("name","AURA-Windows-0.1.2.exe").put("browser_download_url","https://github.com/Kotomineee/AURA/releases/download/v0.1.2/AURA-Windows-0.1.2.exe")))
    private fun manifest()=JSONObject().put("version","0.1.2").put("build",404).put("assets",JSONObject().put("android","AURA-Android-0.1.2.apk").put("windows","AURA-Windows-0.1.2.exe")).put("sha256",JSONObject().put("android","a".repeat(64)).put("windows","b".repeat(64)))

    @Test fun upgradeUsesMonotonicBuildAcrossVersionRename(){
        assertTrue(UpdateClient.parse(release(),manifest(),402).available)
        assertTrue(UpdateClient.parse(release(),manifest(),403).available)
        assertFalse(UpdateClient.parse(release(),manifest(),404).available)
    }
    @Test fun rejectsExternalDownloadAndIncompleteRelease(){
        val changed=release();changed.getJSONArray("assets").getJSONObject(0).put("browser_download_url","https://evil.example/a.apk")
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(changed,manifest())}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release().put("prerelease",true),manifest())}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release().put("draft",true),manifest())}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release().put("published_at",JSONObject.NULL),manifest())}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release(),manifest().put("sha256",JSONObject().put("android","bad")))}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release(),manifest().put("version","0.1.3"))}
        assertThrows(IllegalArgumentException::class.java){UpdateClient.parse(release().put("assets",JSONArray()),manifest())}
    }
    @Test fun processAdapterUsesDecodedBitmapInsteadOfMonogram(){
        val bitmap=Bitmap.createBitmap(32,32,Bitmap.Config.ARGB_8888).apply{eraseColor(Color.CYAN)}
        val output=java.io.ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,output)
        val payload=JSONObject().put("state","ready").put("png",Base64.encodeToString(output.toByteArray(),Base64.NO_WRAP))
        val decoded=ProcessIconDecoder.decode(payload)
        assertNotNull(decoded)
        assertNull(ProcessIconDecoder.decode(JSONObject().put("state","pending")))
        assertNull(ProcessIconDecoder.decode(JSONObject().put("state","ready").put("png","invalid")))
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            val activity=controller.get();val key="a".repeat(64)
            val field=MainActivity::class.java.getDeclaredField("icons").apply{isAccessible=true}
            @Suppress("UNCHECKED_CAST") val cache=field.get(activity) as LruCache<String,Bitmap>
            cache.put(key,decoded!!)
            MainActivity::class.java.getDeclaredMethod("showPage",String::class.java,Boolean::class.javaPrimitiveType).apply{isAccessible=true}.invoke(activity,"processes",false)
            val row=JSONObject().put("name","Discord.exe").put("pid",123).put("created_at",42.0).put("ram_mb",20.0).put("icon_id",key)
            MainActivity::class.java.getDeclaredMethod("acceptProcesses",JSONArray::class.java).apply{isAccessible=true}.invoke(activity,JSONArray().put(row))
            val adapter=MainActivity::class.java.getDeclaredField("adapter").apply{isAccessible=true}.get(activity) as BaseAdapter
            val view=adapter.getView(0,null,activity.window.decorView as ViewGroup) as ViewGroup
            val image=view.getChildAt(0) as ImageView
            assertSame(decoded,(image.drawable as BitmapDrawable).bitmap)
        } finally {controller.pause().stop().destroy()}
    }
}
