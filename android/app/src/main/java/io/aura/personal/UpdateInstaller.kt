package io.aura.personal

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import java.io.File
import java.net.URL
import java.security.MessageDigest
import javax.net.ssl.HttpsURLConnection

object UpdateInstaller {
    fun file(context:Context)=File(context.filesDir,"updates/update.apk")
    fun uri(context:Context):Uri=Uri.parse("content://${context.packageName}.updates/update.apk")

    @Suppress("DEPRECATION")
    fun signatures(info:PackageInfo):Set<String> {
        val values=if(Build.VERSION.SDK_INT>=28)info.signingInfo?.apkContentsSigners else info.signatures
        return values?.map{signature->MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString(""){"%02x".format(it.toInt() and 255)}}?.toSet()?:emptySet()
    }
    fun verifyDigest(file:File,expected:String){
        val hash=MessageDigest.getInstance("SHA-256")
        file.inputStream().use{stream->val buffer=ByteArray(65536);while(true){val count=stream.read(buffer);if(count<0)break;hash.update(buffer,0,count)}}
        val actual=hash.digest().joinToString(""){"%02x".format(it.toInt() and 255)}
        require(actual==expected){"O APK está incompleto ou corrompido. Tente novamente."}
    }
    @Suppress("DEPRECATION")
    fun verifyPackage(context:Context,apk:File,result:UpdateClient.Result){
        verifyDigest(apk,result.sha256)
        val flags=if(Build.VERSION.SDK_INT>=28)PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        val archive=context.packageManager.getPackageArchiveInfo(apk.absolutePath,flags)?:throw IllegalArgumentException("APK inválido.")
        val current=context.packageManager.getPackageInfo(context.packageName,flags)
        val code=if(Build.VERSION.SDK_INT>=28)archive.longVersionCode else archive.versionCode.toLong()
        require(archive.packageName==context.packageName && code==result.build.toLong() && archive.versionName==result.version){"O APK não corresponde à versão anunciada."}
        val installed=signatures(current);val incoming=signatures(archive)
        require(installed.isNotEmpty() && incoming==installed){"O APK tem outra assinatura e não pode atualizar sua instalação."}
    }
    fun download(context:Context,result:UpdateClient.Result,progress:((Long,Long)->Unit)?=null):File {
        require(result.available && result.build>AuraVersion.build)
        require(result.url.startsWith("https://github.com/${UpdateClient.repository}/releases/download/"))
        val target=file(context);target.parentFile!!.mkdirs()
        val partial=File(target.parentFile,"update.part")
        val connection=URL(result.url).openConnection() as HttpsURLConnection
        connection.connectTimeout=15000;connection.readTimeout=30000
        connection.setRequestProperty("User-Agent","AURA-update-download")
        try {
            require(connection.responseCode in 200..299 && connection.url.protocol=="https"){"Não foi possível baixar a atualização."}
            var size=0L
            val total=connection.contentLengthLong
            require(total<=150L*1024*1024){"APK excedeu o limite de tamanho."}
            connection.inputStream.use{stream->partial.outputStream().use{output->
                val buffer=ByteArray(65536)
                while(true){if(Thread.currentThread().isInterrupted)throw java.io.InterruptedIOException();val count=stream.read(buffer);if(count<0)break;size+=count;require(size<=150L*1024*1024){"APK excedeu o limite de tamanho."};output.write(buffer,0,count);progress?.invoke(size,total)}
            }}
            require(total<=0 || size==total){"O download ficou incompleto. Tente novamente."}
            verifyPackage(context,partial,result)
            java.nio.file.Files.move(partial.toPath(),target.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING)
            val metadata=org.json.JSONObject().put("version",result.version).put("build",result.build).put("sha256",result.sha256).put("url",result.url)
            File(target.parentFile,"pending.json").writeText(metadata.toString())
            return target
        } finally {connection.disconnect();partial.delete()}
    }
    fun pending(context:Context):UpdateClient.Result? {
        return try {
            val data=org.json.JSONObject(File(file(context).parentFile,"pending.json").readText())
            val result=UpdateClient.Result(true,data.getString("version"),data.getInt("build"),data.getString("url"),data.getString("sha256"))
            if(result.build<=AuraVersion.build){file(context).delete();File(file(context).parentFile,"pending.json").delete();null}
            else result.takeIf{file(context).isFile}
        }catch(_:Exception){null}
    }
    fun intent(context:Context)=Intent(Intent.ACTION_VIEW).setDataAndType(uri(context),"application/vnd.android.package-archive")
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
}
