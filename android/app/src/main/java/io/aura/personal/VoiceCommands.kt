package io.aura.personal

import java.text.Normalizer
import org.json.JSONObject

data class VoiceCommand(val action:String,val argument:String="",val seconds:Int=0,val english:String="")
object VoiceCommands {
    fun normalize(value:String)=Normalizer.normalize(value.lowercase(java.util.Locale.ROOT),Normalizer.Form.NFD).replace(Regex("\\p{M}"),"").replace(Regex("[^a-z0-9 ]")," ").replace(Regex("\\s+")," ").trim()
    private val numbers=mapOf("um" to 1,"uma" to 1,"dois" to 2,"duas" to 2,"tres" to 3,"quatro" to 4,"cinco" to 5,"seis" to 6,"sete" to 7,"oito" to 8,"nove" to 9,"dez" to 10,"onze" to 11,"doze" to 12,"treze" to 13,"quatorze" to 14,"catorze" to 14,"quinze" to 15,"dezesseis" to 16,"dezessete" to 17,"dezoito" to 18,"dezenove" to 19,"vinte" to 20,"trinta" to 30,"quarenta" to 40,"cinquenta" to 50,"sessenta" to 60,"setenta" to 70,"oitenta" to 80,"noventa" to 90,"cem" to 100,"cento" to 100)
    private const val target="(?:o |meu |o meu )?(?:pc|computador|windows|sistema|notebook|desktop)"
    fun names(row:JSONObject):Set<String>{
        val base=row.getString("name").replace(Regex("\\.exe$",RegexOption.IGNORE_CASE),"")
        val split=base.replace(Regex("(?<=[a-z])(?=[A-Z])")," ").replace(Regex("(?<=[A-Z])(?=[A-Z][a-z])")," ")
        val suffix=base.replace(Regex("(?:client|launcher|helper|application|app|host|service|x64|x86)$",RegexOption.IGNORE_CASE),"")
        val core=normalize(split).replace(Regex("\\b(?:client|launcher|helper|application|app|host|service|x64|x86)\\b"),"")
        return setOf(normalize(base),normalize(split),normalize(core),if(suffix.length>=3)normalize(suffix)else "").filter{it.isNotBlank()}.toSet()
    }
    fun matchesProcess(row:JSONObject,argument:String,english:String=""):Boolean {
        Regex("(?:processo|pid) (\\d+)").matchEntire(argument)?.let{return row.getInt("pid").toString()==it.groupValues[1]}
        return names(row).any{it==normalize(argument) || (it.length>=3 && Regex("(?<!\\w)"+Regex.escape(it)+"(?!\\w)").containsMatchIn(normalize(english)))}
    }
    private fun similarity(a:String,b:String):Double {
        var previous=IntArray(b.length+1){it}
        for(i in a.indices){val current=IntArray(b.length+1);current[0]=i+1;for(j in b.indices)current[j+1]=minOf(current[j]+1,previous[j+1]+1,previous[j]+if(a[i]==b[j])0 else 1);previous=current}
        return 1.0-previous[b.length].toDouble()/maxOf(a.length,b.length,1)
    }
    fun candidates(rows:List<JSONObject>,command:VoiceCommand):List<JSONObject>{
        val exact=rows.filter{matchesProcess(it,command.argument,command.english)}
        if(exact.isNotEmpty())return exact
        val spoken=normalize(command.argument).replace(" ","")
        if(spoken.length<4)return emptyList()
        return rows.map{row->row to names(row).maxOf{similarity(spoken,it.replace(" ",""))}}.filter{it.second>=.68}.sortedByDescending{it.second}.take(8).map{it.first}
    }
    fun selectedReference(value:String)=value in listOf("esse","este","isso","esse app","este app","esse aplicativo","este aplicativo","esse programa","este programa","esse processo","este processo","selecionado","app selecionado","aplicativo selecionado","programa selecionado")
    fun parse(value:String):VoiceCommand? {
        var text=normalize(value)
        if(Regex("\\b(?:nao|nunca|talvez|se|sem)\\b").containsMatchIn(text))return null
        text=text.replace(Regex("^(?:aura |por favor |pode |poderia |voce pode |quero que voce |quero |preciso que voce )+"),"").replace(Regex("(?: por favor| pra mim| para mim| agora)$"),"")
        if(Regex("(?:cancelar|cancele|cancela|remover|remova|desmarcar|desmarque)(?: o)? (?:desligamento|agendamento|desligamento agendado)").matches(text))return VoiceCommand("cancel")
        if(Regex("(?:estado|status|atualizar estado|atualize o estado|como esta (?:o )?(?:pc|computador)|qual o estado do pc|uso (?:de|da) memoria|uso de cpu|mostre (?:o )?(?:estado|status|uso de memoria))").matches(text))return VoiceCommand("status")
        Regex("(desligar|desligue|desliga|apagar|apague|reiniciar|reinicie|reinicia|reinicializar|ligar|ligue|liga|acordar|acorde)(?: $target)?(?: (?:em|daqui a) (.+?) (minuto|minutos|hora|horas|segundo|segundos))?").matchEntire(text)?.let{
            val verb=it.groupValues[1];val amount=it.groupValues[2];val unit=it.groupValues[3]
            val action=if(verb.startsWith("reini"))"restart" else if(verb.startsWith("lig") || verb.startsWith("acord"))"wake" else "shutdown"
            if(amount.isEmpty())return VoiceCommand(action)
            if(action!="shutdown")return null
            val words=amount.split(" ");val count=amount.toLongOrNull()?:if(words.all{w->w in numbers || w=="e"})words.sumOf{w->(numbers[w]?:0).toLong()}else 0L
            if(count !in 1..604800)return null
            val seconds=count*(if(unit.startsWith("hora"))3600 else if(unit.startsWith("minuto"))60 else 1)
            return if(seconds in 1..604800)VoiceCommand("schedule",seconds=seconds.toInt())else null
        }
        Regex("(?:encerrar|encerre|encerra|fechar|feche|fecha|finalizar|finalize|finaliza|terminar|termine) (?:(?:o |a )?(?:app|aplicativo|programa|processo) |o |a )?(.+)").matchEntire(text)?.let{
            val pid=Regex("\\b(?:processo|pid) (\\d+)$").find(text)
            return VoiceCommand("terminate",if(pid!=null)"processo "+pid.groupValues[1]else it.groupValues[1])
        }
        return null
    }

}

object VoiceInbox {
    @Volatile var active=false
    @Volatile var paused=false
    @Volatile var level=0f
    @Volatile var message="Preparando escuta automática…"
    private var pending:Pair<Long,VoiceCommand?>?=null
    @Synchronized fun offer(command:VoiceCommand?){pending=android.os.SystemClock.elapsedRealtime() to command}
    @Synchronized fun take():Pair<Long,VoiceCommand?>?{val value=pending;pending=null;return value?.takeIf{android.os.SystemClock.elapsedRealtime()-it.first<30000}}
    @Synchronized fun clear(){pending=null}
}
