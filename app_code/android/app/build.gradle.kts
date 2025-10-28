import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
    id("com.google.gms.google-services") // google-services.json 없으면 이 줄 주석
}

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}
val mapsApiKey: String = localProps.getProperty("MAPS_API_KEY") ?: System.getenv("MAPS_API_KEY") ?: ""
val flutterVersionCode: Int = localProps.getProperty("flutter.versionCode")?.toIntOrNull() ?: 1
val flutterVersionName: String = localProps.getProperty("flutter.versionName") ?: "1.0"

android {
    namespace = "com.example.alter_bot"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.alter_bot"
        minSdk = maxOf(21, flutter.minSdkVersion.toInt()) // desugaring은 21+ 필요
        targetSdk = 36
        versionCode = flutterVersionCode
        versionName = flutterVersionName
        manifestPlaceholders["MAPS_API_KEY"] = mapsApiKey
    }

    buildTypes {
        getByName("debug") { }
        getByName("release") {
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }
    kotlinOptions { jvmTarget = "17" }
}

flutter { source = "../.." }

dependencies {
    implementation("com.google.android.gms:play-services-maps:18.2.0")
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4") // ⬅️ Kotlin DSL 형식
}
