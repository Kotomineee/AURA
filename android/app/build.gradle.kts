import java.io.File
import java.net.URI
import java.security.MessageDigest

plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "io.aura.personal"
    compileSdk = 35
    buildFeatures { buildConfig = true }
    defaultConfig {
        applicationId = "io.aura.personal"
        minSdk = 26
        targetSdk = 35
        versionCode = 408
        versionName = "0.1.6"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            it.systemProperty("robolectric.dependency.repo.url", "https://repo.maven.apache.org/maven2")
        }
    }
}
dependencies {
    implementation("net.java.dev.jna:jna:5.18.1@aar")
    implementation("com.alphacephei:vosk-android:0.3.75@aar")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}

val voiceAssets=layout.buildDirectory.dir("generated/voiceAssets")
val prepareVoiceModel=tasks.register("prepareVoiceModel") {
    val archive=voiceAssets.map{it.file("voice-model.zip")}
    outputs.file(archive)
    outputs.file(voiceAssets.map{it.file("voice-model-en.zip")})
    doLast {
        val target=archive.get().asFile
        target.parentFile.mkdirs()
        val local=System.getenv("AURA_VOICE_MODEL_ZIP")
        if(local!=null)File(local).copyTo(target,overwrite=true)
        else URI("https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip").toURL().openStream().use{input->target.outputStream().use{input.copyTo(it)}}
        val digest=MessageDigest.getInstance("SHA-256").digest(target.readBytes()).joinToString(""){"%02x".format(it)}
        check(digest=="6e1ce909032e1afa7a88e68a3d628ecafff302bdf195befab308826c395e93b7"){"Modelo de voz inválido"}
        val enTarget=voiceAssets.get().file("voice-model-en.zip").asFile
        val localEn=System.getenv("AURA_VOICE_MODEL_EN_ZIP")
        if(localEn!=null)File(localEn).copyTo(enTarget,overwrite=true)
        else URI("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip").toURL().openStream().use{input->enTarget.outputStream().use{input.copyTo(it)}}
        val enDigest=MessageDigest.getInstance("SHA-256").digest(enTarget.readBytes()).joinToString(""){"%02x".format(it)}
        check(enDigest=="30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"){"Modelo de inglês inválido"}
    }
}
android.sourceSets.getByName("main").assets.srcDir(voiceAssets)
tasks.named("preBuild").configure{dependsOn(prepareVoiceModel)}
