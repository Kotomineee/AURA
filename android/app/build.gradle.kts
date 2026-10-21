plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "io.aura.personal"
    compileSdk = 35
    defaultConfig {
        applicationId = "io.aura.personal"
        minSdk = 26
        targetSdk = 35
        versionCode = 404
        versionName = "0.1.2"
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
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}
