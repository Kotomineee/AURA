package io.aura.personal

import org.json.JSONObject

object InstalledApps {
    data class Matches(val rows:List<JSONObject>,val exact:Boolean)
    private fun names(row:JSONObject):List<String>{val list=row.optJSONArray("aliases")?:return emptyList();return (0 until list.length()).map{VoiceCommands.normalize(list.optString(it))}.filter{it.isNotBlank()}}
    fun search(rows:List<JSONObject>,query:String):List<JSONObject>{val text=VoiceCommands.normalize(query);return rows.filter{text.isEmpty() || names(it).any{n->text in n}}.sortedBy{it.optString("name").lowercase(java.util.Locale.ROOT)}}
    private fun similarity(a:String,b:String):Double {
        var previous=IntArray(b.length+1){it}
        for(i in a.indices){val current=IntArray(b.length+1);current[0]=i+1;for(j in b.indices)current[j+1]=minOf(current[j]+1,previous[j+1]+1,previous[j]+if(a[i]==b[j])0 else 1);previous=current}
        return 1.0-previous[b.length].toDouble()/maxOf(a.length,b.length,1)
    }
    fun match(rows:List<JSONObject>,command:VoiceCommand):Matches {
        val spoken=VoiceCommands.normalize(command.argument);val english=VoiceCommands.normalize(command.english)
        val exact=rows.filter{spoken.isNotBlank() && spoken in names(it)}
        if(exact.isNotEmpty())return Matches(exact,true)
        val secondary=rows.filter{names(it).any{n->n.length>=3 && Regex("(?<!\\w)"+Regex.escape(n)+"(?!\\w)").containsMatchIn(english)}}
        if(secondary.isNotEmpty())return Matches(secondary,false)
        if(spoken.length<3)return Matches(emptyList(),false)
        return Matches(rows.map{row->row to (names(row).maxOfOrNull{similarity(spoken.replace(" ",""),it.replace(" ",""))}?:0.0)}.filter{it.second>=.58}.sortedByDescending{it.second}.take(8).map{it.first},false)
    }
}
