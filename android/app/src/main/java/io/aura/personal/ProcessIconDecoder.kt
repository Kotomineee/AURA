package io.aura.personal

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import org.json.JSONObject

object ProcessIconDecoder {
    fun decode(value:JSONObject):Bitmap? {
        if(value.optString("state")!="ready")return null
        val png=value.optString("png")
        if(png.length !in 1..16384)return null
        return try {
            val bytes=Base64.decode(png,Base64.NO_WRAP)
            val options=BitmapFactory.Options().apply{inJustDecodeBounds=true}
            BitmapFactory.decodeByteArray(bytes,0,bytes.size,options)
            if(options.outWidth!=32 || options.outHeight!=32)null
            else BitmapFactory.decodeByteArray(bytes,0,bytes.size)
        }catch(_:IllegalArgumentException){null}
    }
}
