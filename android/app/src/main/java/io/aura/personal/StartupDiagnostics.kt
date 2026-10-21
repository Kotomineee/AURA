package io.aura.personal

import android.content.Context
import android.content.res.Resources
import android.os.Build

/** Deliberately excludes exception messages, saved profiles, tokens and paths. */
object StartupDiagnostics {
    fun report(error:Throwable):String {
        val causes=generateSequence(error){it.cause}.take(6).toList()
        val code=when {
            causes.any{it is Resources.NotFoundException}->"AURA-START-RESOURCES"
            causes.any{it is LinkageError}->"AURA-START-CLASS"
            causes.any{it is UninitializedPropertyAccessException}->"AURA-START-STATE"
            causes.any{it is NullPointerException}->"AURA-START-NULL"
            else->"AURA-START-001"
        }
        val frames=causes.flatMap{it.stackTrace.toList()}.filter{it.className.startsWith("io.aura.personal.")}.take(8)
        return buildString {
            appendLine("Código: $code")
            appendLine("AURA ${AuraVersion.name} • Android API ${Build.VERSION.SDK_INT}")
            appendLine("Tipos: "+causes.joinToString(" → "){it.javaClass.simpleName})
            frames.forEach{appendLine("${it.className}.${it.methodName}:${it.lineNumber}")}
        }.take(4000)
    }
    fun save(context:Context,report:String){
        try{context.openFileOutput("startup-diagnostic.txt",Context.MODE_PRIVATE).use{it.write(report.take(4000).toByteArray(Charsets.UTF_8))}}
        catch(_:Exception){/* The recovery screen still works if storage is unavailable. */}
    }
}
