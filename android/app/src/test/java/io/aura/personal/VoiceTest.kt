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
    @Test fun requiresWakeAndExpires(){
        val gate=VoiceCommands.Gate()
        assertNull(gate.feed("desligar pc",100000))
        assertEquals("awake",gate.feed("Ok Aura",100000)!!.first)
        assertEquals(VoiceCommand("schedule",seconds=1800),gate.feed("desligar em trinta minutos",105000)!!.second)
        assertNull(gate.feed("reiniciar pc",106000))
        gate.feed("Ok Aura",110000)
        assertNull(gate.feed("desligar pc",121000))
        assertEquals(VoiceCommand("terminate","discord"),gate.feed("Ok Aura encerrar Discord",122000)!!.second)
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
