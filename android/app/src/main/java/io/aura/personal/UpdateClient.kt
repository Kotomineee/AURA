package io.aura.personal

import org.json.JSONObject
import java.net.URL
import javax.net.ssl.HttpsURLConnection

object AuraVersion {
    const val name = "0.1.2"
    const val build = 404
}

/** Uses public TLS trust, never the PC certificate or the pairing token. */
object UpdateClient {
    const val repository = "Kotomineee/AURA"
    data class Result(val available:Boolean,val version:String,val build:Int,val url:String,val sha256:String)

    private fun json(url:String):JSONObject {
        require(url.startsWith("https://"))
        val connection=URL(url).openConnection() as HttpsURLConnection
        connection.connectTimeout=10000;connection.readTimeout=12000
        connection.setRequestProperty("User-Agent","AURA-update-check")
        connection.setRequestProperty("Accept","application/json")
        try {
            val code=connection.responseCode
            if(code==404)throw IllegalStateException("Repositório privado, inexistente ou sem Release pública.")
            if(code==403 || code==429)throw IllegalStateException("Limite de consultas do GitHub atingido. Tente mais tarde.")
            require(code in 200..299){"Não foi possível consultar a atualização."}
            require(connection.url.protocol=="https")
            val output=java.io.ByteArrayOutputStream()
            connection.inputStream.use { stream ->
                val buffer=ByteArray(4096)
                while(true){val count=stream.read(buffer);if(count<0)break;require(output.size()+count<=262144);output.write(buffer,0,count)}
            }
            return JSONObject(output.toString("UTF-8"))
        } finally {connection.disconnect()}
    }

    fun parse(release:JSONObject,manifest:JSONObject,currentBuild:Int=AuraVersion.build):Result {
        return try {parseManifest(release,manifest,currentBuild)}
        catch(_:org.json.JSONException){throw IllegalArgumentException("A Release ainda não contém os dois aplicativos prontos e verificados.")}
    }
    private fun parseManifest(release:JSONObject,manifest:JSONObject,currentBuild:Int):Result {
        require(!release.optBoolean("draft") && !release.optBoolean("prerelease") && release.optString("published_at").isNotBlank() && !release.isNull("published_at")){"A versão ainda não foi publicada como estável."}
        val rawBuild=manifest.get("build")
        require(rawBuild is Int && rawBuild>0){"Número de versão inválido."}
        val version=manifest.getString("version")
        require(version.matches(Regex("\\d+\\.\\d+\\.\\d+")) && release.getString("tag_name")=="v$version"){"Versão do manifesto inválida."}
        val name=manifest.getJSONObject("assets").getString("android")
        require(name.endsWith(".apk"))
        val assets=release.getJSONArray("assets")
        for((kind,ending) in listOf("windows" to ".exe","android" to ".apk")){
            val filename=manifest.getJSONObject("assets").getString(kind)
            val checksum=manifest.getJSONObject("sha256").getString(kind)
            require(filename.endsWith(ending) && checksum.matches(Regex("[0-9a-fA-F]{64}"))){"A Release ainda não contém os dois aplicativos prontos e verificados."}
            require((0 until assets.length()).map{assets.getJSONObject(it)}.any{it.optString("name")==filename && it.optString("browser_download_url").startsWith("https://github.com/$repository/releases/download/")}){"A Release ainda não contém os dois aplicativos prontos e verificados."}
        }
        val asset=(0 until assets.length()).map{assets.getJSONObject(it)}.firstOrNull{it.optString("name")==name}
            ?:throw IllegalArgumentException("APK ausente na Release.")
        val url=asset.getString("browser_download_url")
        require(url.startsWith("https://github.com/$repository/releases/download/")){"Endereço de atualização inválido."}
        val digest=manifest.getJSONObject("sha256").getString("android")
        require(digest.matches(Regex("[0-9a-fA-F]{64}"))){"SHA-256 da atualização ausente ou inválido."}
        return Result(rawBuild>currentBuild,version,rawBuild,url,digest.lowercase())
    }

    fun check():Result {
        val release=json("https://api.github.com/repos/$repository/releases/latest")
        val assets=release.getJSONArray("assets")
        val asset=(0 until assets.length()).map{assets.getJSONObject(it)}.firstOrNull{it.optString("name")=="aura-update.json"}
            ?:throw IllegalArgumentException("A Release não contém aura-update.json.")
        val url=asset.getString("browser_download_url")
        require(url.startsWith("https://github.com/$repository/releases/download/"))
        return parse(release,json(url))
    }
}
