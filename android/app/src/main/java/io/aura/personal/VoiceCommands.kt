package io.aura.personal

import java.text.Normalizer

data class VoiceCommand(val action:String,val argument:String="",val seconds:Int=0)
object VoiceCommands {
    fun normalize(value:String)=Normalizer.normalize(value.lowercase(java.util.Locale.ROOT),Normalizer.Form.NFD).replace(Regex("\\p{M}"),"").replace(Regex("[^a-z0-9 ]"),"").trim()
    private val numbers=mapOf("um" to 1,"uma" to 1,"dois" to 2,"duas" to 2,"tres" to 3,"quatro" to 4,"cinco" to 5,"seis" to 6,"sete" to 7,"oito" to 8,"nove" to 9,"dez" to 10,"onze" to 11,"doze" to 12,"quinze" to 15,"vinte" to 20,"trinta" to 30,"quarenta" to 40,"cinquenta" to 50,"sessenta" to 60)
    fun matchesProcess(row:org.json.JSONObject,argument:String):Boolean {
        Regex("(?:processo|pid) (\\d+)").matchEntire(argument)?.let{return row.getInt("pid").toString()==it.groupValues[1]}
        val aliases=mapOf("discordia" to "discord","disco" to "discord","cromo" to "chrome","bloco de notas" to "notepad","calculadora" to "calculator")
        return normalize(row.getString("name").lowercase(java.util.Locale.ROOT).removeSuffix(".exe"))==(aliases[argument]?:argument)
    }
    fun parse(value:String):VoiceCommand? {
        val text=normalize(value)
        if(text in listOf("cancelar desligamento","cancele o desligamento","cancelar agendamento","cancele o agendamento"))return VoiceCommand("cancel")
        if(text in listOf("estado","status","atualizar estado","qual o estado do pc","uso de memoria","uso da memoria","uso de cpu"))return VoiceCommand("status")
        if(text in listOf("ligar pc","ligar o pc","ligue o computador","ligar computador"))return VoiceCommand("wake")
        Regex("(?:desligar|desligue|agendar desligamento)(?: o)?(?: pc| computador)? em (.+) (minuto|minutos|hora|horas)").matchEntire(text)?.let {
            val words=it.groupValues[1].split(" ")
            val amount=it.groupValues[1].toIntOrNull()?:if(words.all{w->w in numbers || w=="e"})words.sumOf{w->numbers[w]?:0}else 0
            val seconds=amount.toLong()*(if(it.groupValues[2].startsWith("hora"))3600 else 60)
            return if(seconds in 60..604800)VoiceCommand("schedule",seconds=seconds.toInt())else null
        }
        if(text in listOf("desligar pc","desligar o pc","desligue o computador","desligar computador"))return VoiceCommand("shutdown")
        if(text in listOf("reiniciar pc","reiniciar o pc","reinicie o computador","reiniciar computador"))return VoiceCommand("restart")
        Regex("(?:fechar|feche|encerrar|encerre) (?:(?:o |a )?programa |o |a )?(.+)").matchEntire(text)?.let{return VoiceCommand("terminate",it.groupValues[1])}
        return null
    }
    class Gate {
        private var deadline=0L
        fun feed(value:String,now:Long):Pair<String,VoiceCommand?>? {
            var text=normalize(value)
            val wake=Regex("^(?:ok|okay|oquei) aura(?: |$)").find(text)
            if(wake!=null){deadline=now+10000;text=text.substring(wake.range.last+1).trim();if(text.isEmpty())return "awake" to null}
            else if(now>=deadline)return null
            if(text.isEmpty())return null
            deadline=0
            return "command" to parse(text)
        }
    }
}

object VoiceInbox {
    @Volatile var active=false
    @Volatile var message="Escuta desativada. Ative e diga “Ok Aura”."
    private var pending:Pair<Long,VoiceCommand?>?=null
    @Synchronized fun offer(command:VoiceCommand?){pending=android.os.SystemClock.elapsedRealtime() to command}
    @Synchronized fun take():Pair<Long,VoiceCommand?>?{val value=pending;pending=null;return value?.takeIf{android.os.SystemClock.elapsedRealtime()-it.first<30000}}
    @Synchronized fun clear(){pending=null}
}
