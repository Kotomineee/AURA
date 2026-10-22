package io.aura.personal

import android.content.Context
import android.content.Intent
import android.content.pm.ProviderInfo
import android.content.pm.PackageInfo
import android.content.pm.Signature
import android.net.Uri
import java.io.File
import java.io.FileNotFoundException
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[33])
class UpdateInstallerTest {
    private fun context():Context=RuntimeEnvironment.getApplication()
    @Test fun hashMismatchPreventsInstallation(){
        val file=File(context().cacheDir,"download-fixture.apk");file.writeBytes("fixture".toByteArray())
        val hash=MessageDigest.getInstance("SHA-256").digest(file.readBytes()).joinToString(""){"%02x".format(it.toInt() and 255)}
        UpdateInstaller.verifyDigest(file,hash)
        assertThrows(IllegalArgumentException::class.java){UpdateInstaller.verifyDigest(file,"0".repeat(64))}
        assertThrows(IllegalArgumentException::class.java){UpdateInstaller.verifyPackage(context(),file,UpdateClient.Result(true,"0.1.5",407,"https://github.com/Kotomineee/AURA/releases/download/v0.1.3/a.apk",hash))}
    }
    @Test fun providerOnlyGrantsReadAccessToTheDownloadedApk(){
        val ctx=context();val provider=UpdateApkProvider()
        provider.attachInfo(ctx,ProviderInfo().apply{authority="${ctx.packageName}.updates";exported=false;grantUriPermissions=true})
        val file=UpdateInstaller.file(ctx);file.parentFile!!.mkdirs();file.writeBytes(byteArrayOf(1,2,3))
        provider.openFile(UpdateInstaller.uri(ctx),"r").use{assertTrue(it.fileDescriptor.valid())}
        assertThrows(FileNotFoundException::class.java){provider.openFile(UpdateInstaller.uri(ctx),"w")}
        assertThrows(FileNotFoundException::class.java){provider.openFile(Uri.parse("content://${ctx.packageName}.updates/../identity.json"),"r")}
        val intent=UpdateInstaller.intent(ctx)
        assertEquals(Intent.ACTION_VIEW,intent.action)
        assertEquals("content",intent.data!!.scheme)
        assertEquals("application/vnd.android.package-archive",intent.type)
        assertTrue(intent.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION != 0)
    }
    @Test fun pendingUpdateSurvivesActivityRestartAndCleansAfterUpgrade(){
        val ctx=context();val file=UpdateInstaller.file(ctx);file.parentFile!!.mkdirs();file.writeBytes(byteArrayOf(1))
        val metadata=File(file.parentFile,"pending.json")
        metadata.writeText(JSONObject().put("version","0.1.5").put("build",407).put("url","https://github.com/Kotomineee/AURA/releases/download/v0.1.3/a.apk").put("sha256","a".repeat(64)).toString())
        assertEquals(407,UpdateInstaller.pending(ctx)!!.build)
        metadata.writeText(JSONObject().put("version","0.1.3").put("build",404).put("url","https://github.com/Kotomineee/AURA/releases/download/v0.1.3/a.apk").put("sha256","a".repeat(64)).toString())
        assertNull(UpdateInstaller.pending(ctx));assertFalse(file.exists())
    }
    @Suppress("DEPRECATION")
    @Test @Config(sdk=[26]) fun packageSignaturesAreComparedByCertificate(){
        val a=PackageInfo().apply{signatures=arrayOf(Signature(byteArrayOf(1,2,3)))}
        val b=PackageInfo().apply{signatures=arrayOf(Signature(byteArrayOf(4,5,6)))}
        assertTrue(UpdateInstaller.signatures(a).isNotEmpty())
        assertNotEquals(UpdateInstaller.signatures(a),UpdateInstaller.signatures(b))
    }
}
