package io.aura.personal

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class) @Config(sdk=[33])
class ProcessGroupsTest {
    private fun row(pid:Int,icon:String?,memory:Double)=JSONObject().put("pid",pid).put("name","chrome.exe").put("created_at",pid.toDouble()).put("ram_mb",memory).put("icon_id",icon?:JSONObject.NULL)
    @Test fun groupsOnlyVerifiedExecutableIdentities(){
        val rows=listOf(row(1,"a".repeat(64),10.0),row(2,"a".repeat(64),20.0),row(3,"b".repeat(64),40.0),row(4,null,2.0),row(5,null,3.0))
        val groups=ProcessGroups.group(rows+rows)
        assertEquals(4,groups.size)
        val chrome=groups.single{it.getInt("pid")==1}
        assertEquals(30.0,chrome.getDouble("ram_mb"),.001)
        assertEquals(2,ProcessGroups.members(chrome).size)
        assertTrue(ProcessGroups.contains(chrome,"2"))
        assertEquals(groups.map{it.toString()},ProcessGroups.group(groups).map{it.toString()})
        assertEquals(2,ProcessGroups.payload(ProcessGroups.members(chrome)[1]).getInt("pid"))
        assertFalse(ProcessGroups.payload(chrome).has("members"))
    }
    @Test fun bottomNavigationHasThreeItemsAndSettingsStayInHeader(){
        val controller=org.robolectric.Robolectric.buildActivity(MainActivity::class.java).setup()
        try{
            val activity=controller.get()
            val nav=MainActivity::class.java.getDeclaredField("bottomNavigation").apply{isAccessible=true}.get(activity) as android.widget.LinearLayout
            assertEquals(3,nav.childCount)
            assertEquals(listOf("Início","Aplicativos","Energia"),(0 until nav.childCount).map{nav.getChildAt(it).contentDescription.toString()})
            val gear=MainActivity::class.java.getDeclaredField("settingsAction").apply{isAccessible=true}.get(activity) as android.widget.ImageButton
            assertEquals("Configurações",gear.contentDescription)
            gear.performClick()
            assertEquals("settings",MainActivity::class.java.getDeclaredField("currentPage").apply{isAccessible=true}.get(activity))
        }finally{controller.pause().stop().destroy()}
    }
}
