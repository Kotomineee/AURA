package io.aura.personal

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[33])
class VoiceTest {
    @Test fun understandsVariationsAndDynamicEnglishCatalog(){
        for(phrase in listOf("desligar Windows","desligue o computador","pode desligar meu notebook por favor","quero que voce desligue o sistema"))assertEquals(VoiceCommand("shutdown"),VoiceCommands.parse(phrase))
        assertEquals(VoiceCommand("restart"),VoiceCommands.parse("reinicie o Windows"))
        assertEquals(VoiceCommand("wake"),VoiceCommands.parse("acorde meu computador"))
        assertEquals(VoiceCommand("schedule",seconds=1500),VoiceCommands.parse("desliga o windows daqui a vinte e cinco minutos"))
        assertTrue(VoiceCommands.selectedReference(VoiceCommands.parse("encerre esse app")!!.argument))
        val rows=listOf(JSONObject().put("name","STOVEClient.exe").put("pid",123),JSONObject().put("name","ZetaLauncher.exe").put("pid",124))
        assertEquals(listOf(rows[0]),VoiceCommands.candidates(rows,VoiceCommand("terminate","estou",english="close stove")))
        assertEquals(listOf(rows[1]),VoiceCommands.candidates(rows,VoiceCommand("terminate","zeta")))
        assertTrue(VoiceCommands.candidates(rows,VoiceCommand("terminate","nada",english="anything")).isEmpty())
    }
    @Test fun homeHasMicrophoneMeterWithoutActivationButton(){
        val controller=org.robolectric.Robolectric.buildActivity(MainActivity::class.java).setup()
        try{
            val root=controller.get().window.decorView
            fun all(view:android.view.View):List<android.view.View> = listOf(view)+if(view is android.view.ViewGroup)(0 until view.childCount).flatMap{all(view.getChildAt(it))}else emptyList()
            val views=all(root)
            assertTrue(views.any{it is VoiceMeterView})
            assertFalse(views.filterIsInstance<android.widget.Button>().any{it.text.toString().contains("ativar escuta",ignoreCase=true)})
        }finally{controller.pause().stop().destroy()}
    }
    @Test fun rejectsUnboundedAndUnknownCommands(){
        for(value in listOf("não desligar pc","desligar em zero minutos","desligar em 999999999 horas","executar cmd","fechar"))assertNull(VoiceCommands.parse(value))
        assertEquals(VoiceCommand("schedule",seconds=3600),VoiceCommands.parse("desligar em uma hora"))
        assertEquals(VoiceCommand("wake"),VoiceCommands.parse("ligar o pc"))
        assertEquals(VoiceCommand("terminate","discord"),VoiceCommands.parse("encerrar o programa Discord"))
    }
    @Test fun selectsProgramByExactNameOrPid(){
        val row=JSONObject().put("name","Discord.exe").put("pid",123)
        assertTrue(VoiceCommands.matchesProcess(row,"discord"))
        assertTrue(VoiceCommands.matchesProcess(row,"processo 123"))
        assertFalse(VoiceCommands.matchesProcess(row,"disc"))
        assertFalse(VoiceCommands.matchesProcess(row,"processo 124"))
    }
}
