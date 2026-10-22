package io.aura.personal

import android.content.Context
import android.graphics.*
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.view.View
import org.json.JSONObject

/** Shared charcoal surfaces and teal accents from the approved 0.4.1 reference. */
object AuraTheme {
    val bg = Color.rgb(11,16,23)
    val panel = Color.rgb(18,29,41)
    val line = Color.rgb(36,54,72)
    val text = Color.rgb(237,244,255)
    val muted = Color.rgb(155,175,197)
    val teal = Color.rgb(109,220,207)
    val selected = Color.rgb(23,59,66)
    val red = Color.rgb(255,147,166)
    fun dp(context: Context, value: Int) = (value * context.resources.displayMetrics.density + .5f).toInt()
    fun surface(context: Context, fill: Int = panel, radius: Int = 22, stroke: Int = line) = GradientDrawable().apply {
        setColor(fill); cornerRadius = dp(context,radius).toFloat(); setStroke(dp(context,1),stroke)
    }
}

/** Vector stroke icons; no emoji, web assets or dependency on installed icon fonts. */
class AuraIcon(private val kind: String, private val tint: Int = AuraTheme.muted) : Drawable() {
    private val p = Paint(Paint.ANTI_ALIAS_FLAG).apply { color=tint; style=Paint.Style.STROKE; strokeWidth=1.6f; strokeCap=Paint.Cap.ROUND; strokeJoin=Paint.Join.ROUND }
    override fun draw(canvas: Canvas) {
        canvas.save(); canvas.translate(bounds.left.toFloat(),bounds.top.toFloat()); canvas.scale(bounds.width()/24f,bounds.height()/24f)
        fun line(vararg pts: Float) { val path=Path(); path.moveTo(pts[0],pts[1]); var i=2; while(i<pts.size){path.lineTo(pts[i],pts[i+1]);i+=2}; canvas.drawPath(path,p) }
        fun box(a:Float,b:Float,c:Float,d:Float)=canvas.drawRect(a,b,c,d,p)
        when(kind) {
            "home" -> { line(2f,11f,12f,2f,22f,11f); line(5f,9f,5f,22f,10f,22f,10f,15f,15f,15f,15f,22f,20f,22f,20f,9f) }
            "processes" -> for(y in listOf(5f,12f,19f)){canvas.drawCircle(3f,y,1f,p);line(8f,y,22f,y)}
            "power" -> line(14f,1f,4f,14f,11f,14f,9f,23f,21f,9f,13f,9f,14f,1f)
            "calendar" -> {box(3f,5f,21f,22f);line(3f,10f,21f,10f);line(8f,2f,8f,7f);line(16f,2f,16f,7f)}
            "cpu" -> {box(5f,5f,19f,19f);box(9f,9f,15f,15f);for(v in listOf(8f,12f,16f)){line(v,1f,v,4f);line(v,20f,v,23f);line(1f,v,4f,v);line(20f,v,23f,v)}}
            "ram" -> {box(2f,5f,22f,18f);for(v in listOf(6f,11f,16f)){box(v,8f,v+2,13f);line(v,18f,v,22f)};line(2f,22f,22f,22f)}
            "search" -> {canvas.drawCircle(9.5f,9.5f,7.5f,p);line(15f,15f,22f,22f)}
            "trash" -> {line(3f,6f,21f,6f);box(6f,6f,18f,22f);line(9f,6f,9f,2f,15f,2f,15f,6f);line(10f,10f,10f,18f);line(14f,10f,14f,18f)}
            "refresh" -> {canvas.drawArc(3f,3f,21f,21f,40f,285f,false,p);line(21f,2f,21f,8f,15f,8f)}
            "settings" -> {canvas.drawCircle(12f,12f,4f,p);canvas.drawCircle(12f,12f,8f,p);for(i in 0..7){canvas.save();canvas.rotate(i*45f,12f,12f);line(12f,1f,12f,4f);canvas.restore()}}
            "connection" -> {canvas.drawCircle(12f,12f,2f,p);for(r in listOf(6f,10f)){canvas.drawArc(12-r,12-r,12+r,12+r,135f,90f,false,p);canvas.drawArc(12-r,12-r,12+r,12+r,-45f,90f,false,p)}}
            "history" -> {canvas.drawCircle(12f,12f,10f,p);line(12f,6f,12f,12f,17f,15f)}
            else -> {box(3f,3f,21f,21f);line(8f,8f,16f,8f);line(8f,12f,16f,12f)}
        }
        canvas.restore()
    }
    override fun setAlpha(alpha:Int){p.alpha=alpha;invalidateSelf()}
    override fun setColorFilter(filter:ColorFilter?){p.colorFilter=filter;invalidateSelf()}
    @Deprecated("Deprecated in Java") override fun getOpacity()=PixelFormat.TRANSLUCENT
}

/** Charts only render samples actually received from the PC. */
class MetricView(context:Context,private val kind:String):View(context) {
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG)
    private var value:Float?=null
    private var used:Double?=null
    private var total:Double?=null
    private val samples=ArrayList<Float>()
    init { contentDescription=kind.uppercase()+": aguardando conexão"; importantForAccessibility=IMPORTANT_FOR_ACCESSIBILITY_YES }
    fun update(data:JSONObject?) {
        value=data?.optDouble(kind)?.toFloat();used=data?.optDouble("ram_used_gb");total=data?.optDouble("ram_total_gb")
        if(data==null)samples.clear() else if(kind=="cpu"){samples.add(value?:0f);if(samples.size>24)samples.removeAt(0)}
        contentDescription=kind.uppercase()+": "+(value?.let{"$it por cento"}?:"indisponível")
        invalidate()
    }
    override fun onDraw(canvas:Canvas) {
        super.onDraw(canvas)
        val density=resources.displayMetrics.density
        canvas.save();canvas.scale(density,density)
        val w=width/density;val h=height/density
        paint.style=Paint.Style.FILL;paint.color=AuraTheme.panel
        canvas.drawRoundRect(1f,1f,w-1,h-1,11f,11f,paint)
        paint.style=Paint.Style.STROKE;paint.strokeWidth=1f;paint.color=AuraTheme.line
        canvas.drawRoundRect(1f,1f,w-1,h-1,11f,11f,paint)
        val symbol=AuraIcon(kind);symbol.setBounds(14,22,38,46);symbol.draw(canvas)
        paint.style=Paint.Style.FILL;paint.typeface=Typeface.create("sans-serif",Typeface.NORMAL);paint.textSize=11f;paint.color=AuraTheme.muted
        canvas.drawText(kind.uppercase(),48f,23f,paint)
        paint.textSize=19f;paint.typeface=Typeface.create("sans-serif",Typeface.BOLD);paint.color=AuraTheme.text
        fun format(n:Double)=java.text.DecimalFormat("0.#").format(n)
        val text=if(kind=="ram" && used!=null)format(used!!)+" GB" else value?.let{format(it.toDouble())+"%"}?:"—"
        canvas.drawText(text,48f,46f,paint)
        if(kind=="ram") {
            paint.textSize=10f;paint.typeface=Typeface.create("sans-serif",Typeface.NORMAL);paint.color=AuraTheme.muted
            canvas.drawText(total?.let{"de "+format(it)+" GB"}?:"Sem conexão",48f,62f,paint)
            paint.color=AuraTheme.line;canvas.drawRoundRect(14f,h-17,w-45,h-11,3f,3f,paint)
            value?.let { paint.color=AuraTheme.teal;canvas.drawRoundRect(14f,h-17,14+(w-59)*it.coerceIn(0f,100f)/100,h-11,3f,3f,paint)
                paint.color=AuraTheme.muted;paint.textSize=9f;canvas.drawText(format(it.toDouble())+"%",w-38,h-10,paint) }
        } else if(samples.size>1) {
            val path=Path()
            samples.forEachIndexed { index,v -> val x=48+(w-62)*index/(samples.size-1);val y=h-12-v.coerceIn(0f,100f)*.22f;if(index==0)path.moveTo(x,y) else path.lineTo(x,y) }
            paint.style=Paint.Style.STROKE;paint.strokeWidth=1.4f;paint.color=AuraTheme.teal;canvas.drawPath(path,paint)
        }
        canvas.restore()
    }
}
