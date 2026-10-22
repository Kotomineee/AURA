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
class WakePolicyTest {
    private fun phrase(text:String="ok aura",confidence:Double=.95)=JSONObject().put("text",text).put("result",JSONArray().put(JSONObject().put("word","ok").put("conf",confidence).put("start",.1).put("end",.4)).put(JSONObject().put("word","aura").put("conf",confidence).put("start",.45).put("end",.9)))
    @Test fun ambientPartialInlineAndForcedGuessesCannotActivate(){
        val policy=WakePolicy()
        for(invalid in listOf(JSONObject().put("partial","ok aura"),phrase("desligar pc"),phrase("ok aura desligar pc"),phrase(confidence=.5),JSONObject(),phrase().put("result",JSONArray()))){
            assertFalse(policy.arm(invalid,phrase(),100000));assertFalse(policy.arm(phrase(),invalid,100000))
        }
        assertFalse(policy.acceptsCommand(100000))
    }
    @Test fun independentConfirmationSingleCommandTimeoutAndCooldown(){
        val policy=WakePolicy()
        assertTrue(policy.arm(phrase(),phrase(),100000))
        assertFalse(policy.acceptsCommand(100100));assertTrue(policy.acceptsCommand(100300))
        assertFalse(policy.arm(phrase(),phrase(),100500))
        policy.finish(101000)
        assertFalse(policy.acceptsCommand(101300));assertFalse(policy.arm(phrase(),phrase(),101500))
        assertTrue(policy.arm(phrase(),phrase(),102000));assertTrue(policy.expire(112000))
        assertFalse(policy.acceptsCommand(112000));assertFalse(policy.arm(phrase(),phrase(),112500))
    }
    @Test fun requiresPlausibleWordTiming(){
        for(field in listOf("start","end","conf")){
            val invalid=phrase();invalid.getJSONArray("result").getJSONObject(0).put(field,if(field=="start")-1 else 20)
            assertFalse(WakePolicy.confirmed(invalid))
        }
    }
}
