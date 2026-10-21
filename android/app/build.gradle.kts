plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "io.aura.personal"
    compileSdk = 35
    defaultConfig {
        applicationId = "io.aura.personal"
        minSdk = 26
        targetSdk = 35
        versionCode = 400
        versionName = "0.4.0-dev"
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}
