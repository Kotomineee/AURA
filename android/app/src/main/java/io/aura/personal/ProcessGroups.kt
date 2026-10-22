package io.aura.personal

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

object ProcessGroups {
    fun key(row:JSONObject):String {
        val opaque=row.optString("icon_id")
        return if(opaque.matches(Regex("[0-9a-f]{64}")))opaque+":"+row.getString("name").lowercase(Locale.ROOT)
        else "pid:${row.getInt("pid")}:${row.getDouble("created_at")}"
    }
    fun members(row:JSONObject):List<JSONObject> = row.optJSONArray("members")?.let{array->(0 until array.length()).map{array.getJSONObject(it)}}?:listOf(row)
    fun group(rows:List<JSONObject>):List<JSONObject>{
        val seen=HashSet<Pair<Int,Double>>()
        val buckets=linkedMapOf<String,MutableList<JSONObject>>()
        for(entry in rows)for(row in members(entry))if(seen.add(row.getInt("pid") to row.getDouble("created_at")))buckets.getOrPut(key(row)){mutableListOf()}.add(row)
        return buckets.map{(identity,children)->
            children.sortWith(compareBy<JSONObject>{it.getDouble("created_at")}.thenBy{it.getInt("pid")})
            JSONObject(children.first().toString()).put("group_id",identity).put("members",JSONArray(children)).put("process_count",children.size).put("ram_mb",kotlin.math.round(children.sumOf{it.getDouble("ram_mb")}*10)/10)
        }.sortedWith(compareByDescending<JSONObject>{it.getDouble("ram_mb")}.thenBy{it.getString("name").lowercase(Locale.ROOT)})
    }
    fun contains(row:JSONObject,term:String)=row.getString("name").contains(term,true) || members(row).any{it.getInt("pid").toString().contains(term)}
    fun payload(row:JSONObject)=JSONObject().put("pid",row.getInt("pid")).put("name",row.getString("name")).put("created_at",row.getDouble("created_at"))
}
