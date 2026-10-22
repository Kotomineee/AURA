package io.aura.personal

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** JVM Android lifecycle/resource regression checks; no emulator or desktop UI. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk=[26,28,30,33,35])
@GraphicsMode(GraphicsMode.Mode.LEGACY)
class StartupTest {
    private fun descendants(view:View):List<View> = listOf(view) +
        if(view is ViewGroup)(0 until view.childCount).flatMap{descendants(view.getChildAt(it))} else emptyList()

    @Test fun coldStartAndFirstLayout() {
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            val activity=controller.get()
            val root=activity.window.decorView
            root.measure(View.MeasureSpec.makeMeasureSpec(1080,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(1920,View.MeasureSpec.EXACTLY))
            root.layout(0,0,1080,1920)
            root.draw(Canvas(Bitmap.createBitmap(1080,1920,Bitmap.Config.ARGB_8888)))
            assertTrue(descendants(root).filterIsInstance<TextView>().any{it.text.toString()=="Visão geral"})
            assertFalse(activity.isFinishing)
        } finally { controller.pause().stop().destroy() }
    }

    @Test fun navigationAndActivityRecreation() {
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            for(destination in listOf("Aplicativos","Energia","Configurações","Início")) {
                val root=controller.get().window.decorView
                val nav=descendants(root).first{it.contentDescription?.toString()==destination}
                assertTrue(nav.performClick())
            }
            controller.recreate()
            assertFalse(controller.get().isFinishing)
        } finally { controller.pause().stop().destroy() }
    }

    @Test @Config(sdk=[33]) fun diagnosticExcludesExceptionMessagesAndSecrets() {
        val sensitive="Bearer secret-token C:/private/path 192.168.1.2"
        val report=StartupDiagnostics.report(IllegalStateException(sensitive,NullPointerException(sensitive)))
        assertTrue(report.contains("AURA-START-NULL"))
        assertFalse(report.contains("secret-token"));assertFalse(report.contains("private/path"));assertFalse(report.contains("192.168.1.2"))
    }

    @Test @Config(sdk=[33]) fun recoveryShowsCodeAndPreservesSavedProfile() {
        val controller=Robolectric.buildActivity(MainActivity::class.java).setup()
        try {
            val activity=controller.get()
            val prefs=activity.getSharedPreferences("aura",android.content.Context.MODE_PRIVATE)
            prefs.edit().putString("profile","saved-profile-fixture").commit()
            val method=MainActivity::class.java.getDeclaredMethod("showStartupFailure",Throwable::class.java).apply{isAccessible=true}
            method.invoke(activity,IllegalStateException("must-not-appear"))
            val labels=descendants(activity.window.decorView).filterIsInstance<TextView>().map{it.text.toString()}
            assertTrue(labels.any{it.contains("AURA-START-001")})
            assertTrue(labels.any{it=="Copiar diagnóstico"})
            assertFalse(labels.any{it.contains("must-not-appear")})
            assertEquals("saved-profile-fixture",prefs.getString("profile",null))
        } finally { controller.pause().stop().destroy() }
    }
}
