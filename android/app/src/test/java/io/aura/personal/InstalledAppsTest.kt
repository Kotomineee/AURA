package io.aura.personal

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk=[33])
class InstalledAppsTest {
    private fun row(name:String,vararg aliases:String)=JSONObject().put("id",name.hashCode().toString()).put("name",name).put("source","Windows").put("aliases",JSONArray(aliases.toList()))
    @Test fun acceptsOpeningCommandsForAnyAppName(){
        for((phrase,name) in listOf("abrir Black Desert" to "black desert","pode abrir o aplicativo Discord por favor" to "discord","abra a Steam" to "steam","inicie o launcher Stove" to "stove","abrir Zeta Studio" to "zeta studio"))assertEquals(VoiceCommand("launch",name),VoiceCommands.parse(phrase))
        for(phrase in listOf("não abra steam","talvez abrir discord","se abrir steam","abrir","clicar em iniciar jogo"))assertNull(VoiceCommands.parse(phrase))
    }
    @Test fun resolvesDynamicCatalogAndEnglishNames(){
        val rows=listOf(row("Black Desert","black desert"),row("Discord","discord","discordia"),row("Portable Editor","meu editor"))
        assertEquals(rows[0],InstalledApps.match(rows,VoiceCommand("launch","black desert")).rows.single())
        assertTrue(InstalledApps.match(rows,VoiceCommand("launch","discórdia")).exact)
        val other=InstalledApps.match(rows,VoiceCommand("launch","estranho",english="open black desert"));assertEquals(rows[0],other.rows.single());assertFalse(other.exact)
        assertEquals(rows[2],InstalledApps.match(rows,VoiceCommand("launch","meu editor")).rows.single())
        assertTrue(InstalledApps.match(rows,VoiceCommand("launch","nada desse nome")).rows.isEmpty())
    }
    @Test fun ambiguousAndApproximateNamesRequireSelection(){
        val rows=listOf(row("Steam","steam"),row("Steam second installation","steam"))
        assertEquals(2,InstalledApps.match(rows,VoiceCommand("launch","steam")).rows.size)
        assertFalse(InstalledApps.match(rows,VoiceCommand("launch","stean")).exact)
        assertEquals(2,InstalledApps.search(rows,"steam").size)
    }
    @Test fun homeOffersInstalledAppsWithoutAddingBottomNavigation(){
        val controller=org.robolectric.Robolectric.buildActivity(MainActivity::class.java).setup()
        try{
            fun all(view:android.view.View):List<android.view.View> = listOf(view)+if(view is android.view.ViewGroup)(0 until view.childCount).flatMap{all(view.getChildAt(it))}else emptyList()
            assertTrue(all(controller.get().window.decorView).filterIsInstance<android.widget.Button>().any{it.text.toString()=="Programas instalados no PC"})
        }finally{controller.pause().stop().destroy()}
    }
}
