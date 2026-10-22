package io.aura.personal

import android.content.Context
import android.graphics.*
import android.view.View

/** History of real PCM amplitude. No decorative speech is generated in silence. */
class VoiceMeterView(context:Context):View(context){
    private val paint=Paint(Paint.ANTI_ALIAS_FLAG)
    private val history=FloatArray(48)
    private var lastSample=0L
    init{contentDescription="Intensidade do microfone";importantForAccessibility=IMPORTANT_FOR_ACCESSIBILITY_YES}
    override fun onDraw(canvas:Canvas){
        super.onDraw(canvas)
        val now=android.os.SystemClock.elapsedRealtime()
        if(now-lastSample>=80){for(i in 0 until 47)history[i]=history[i+1];history[47]=if(VoiceInbox.active)VoiceInbox.level else 0f;lastSample=now}
        val middle=height/2f;val padding=AuraTheme.dp(context,10).toFloat();val span=(width-padding*2)/48
        paint.shader=null;paint.color=AuraTheme.line;paint.strokeWidth=1f;canvas.drawLine(padding,middle,width-padding,middle,paint)
        paint.shader=LinearGradient(0f,0f,width.toFloat(),0f,intArrayOf(AuraTheme.teal,Color.rgb(104,223,200)),null,Shader.TileMode.CLAMP)
        paint.strokeCap=Paint.Cap.ROUND;paint.strokeWidth=maxOf(2f,span*.45f)
        for(i in history.indices){val amplitude=maxOf(1f,history[i]*(middle-padding));val x=padding+i*span;canvas.drawLine(x,middle-amplitude,x,middle+amplitude,paint)}
        if(isAttachedToWindow && windowVisibility==VISIBLE)postInvalidateDelayed(40)
    }
}
