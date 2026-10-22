package io.aura.personal

import org.json.JSONObject

/** Final utterance and independent unrestricted transcript must both agree. */
class WakePolicy {
    var until=0L;private set
    var cooldown=0L;private set
    private var ready=0L
    fun arm(proposal:JSONObject,verification:JSONObject,now:Long):Boolean {
        if(until!=0L || now<cooldown || !confirmed(proposal) || !confirmed(verification))return false
        until=now+10000;ready=now+250;return true
    }
    fun acceptsCommand(now:Long)=now>=ready && now<until
    fun finish(now:Long){until=0;ready=0;cooldown=now+900}
    fun expire(now:Long):Boolean {if(until!=0L && now>=until){finish(now);return true};return false}
    companion object {
        fun confirmed(result:JSONObject):Boolean {
            if(VoiceCommands.normalize(result.optString("text"))!="ok aura")return false
            val words=result.optJSONArray("result")?:return false
            if(words.length()!=2)return false
            return try {
                val a=words.getJSONObject(0);val b=words.getJSONObject(1)
                if(VoiceCommands.normalize(a.getString("word"))!="ok" || VoiceCommands.normalize(b.getString("word"))!="aura")return false
                for(w in listOf(a,b)) {
                    val c=w.getDouble("conf");val s=w.getDouble("start");val e=w.getDouble("end")
                    if(!c.isFinite() || !s.isFinite() || !e.isFinite() || c !in .8..1.0 || s<0 || e-s !in .06..1.8)return false
                }
                (a.getDouble("conf")+b.getDouble("conf"))/2>=.85 &&
                    b.getDouble("start")-a.getDouble("end") in 0.0..0.9 &&
                    b.getDouble("end")-a.getDouble("start") in .25..3.0
            }catch(_:Exception){false}
        }
    }
}
