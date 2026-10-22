package io.aura.personal

import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.os.*
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.File
import java.util.concurrent.Executors
import java.util.zip.ZipInputStream

class VoiceService:Service(),RecognitionListener {
    private val worker=Executors.newSingleThreadExecutor()
    private val handler=Handler(Looper.getMainLooper())
    private var speech:SpeechService?=null
    private var recognizer:Recognizer?=null
    private var model:Model?=null
    @Volatile private var destroyed=false
    private val gate=VoiceCommands.Gate()
    override fun onBind(intent:Intent?)=null
    private fun notification(message:String):Notification {
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop=PendingIntent.getService(this,1,Intent(this,VoiceService::class.java).setAction("stop"),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this,"aura-voice").setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("AURA • Ok Aura").setContentText(message).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).addAction(android.R.drawable.ic_media_pause,"Desativar escuta",stop).build()
    }
    private fun state(message:String){VoiceInbox.message=message;(getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(130,notification(message))}
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="stop"){stopSelf();return START_NOT_STICKY}
        if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){stopSelf();return START_NOT_STICKY}
        val manager=getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel("aura-voice","Escuta Ok Aura",NotificationManager.IMPORTANCE_LOW))
        startForeground(130,notification("Preparando reconhecimento local…"))
        if(VoiceInbox.active)return START_NOT_STICKY
        VoiceInbox.active=true
        worker.execute{
            try {
                val folder=File(filesDir,"voice-model")
                val ready=File(folder,".ready")
                if(!ready.exists()){
                    folder.mkdirs()
                    assets.open("voice-model.zip").use{input->ZipInputStream(input).use{zip->
                        var total=0L
                        var entry=zip.nextEntry
                        while(entry!=null){
                            val name=entry.name.substringAfter('/')
                            if(name.isNotEmpty()){
                                val target=File(folder,name)
                                check(target.canonicalPath.startsWith(folder.canonicalPath+File.separator))
                                if(entry.isDirectory)target.mkdirs()else{
                                    target.parentFile?.mkdirs()
                                    target.outputStream().use{output->val buffer=ByteArray(16384);var size=zip.read(buffer);while(size!=-1){total+=size;check(total<150L*1024*1024);output.write(buffer,0,size);size=zip.read(buffer)}}
                                }
                            }
                            zip.closeEntry();entry=zip.nextEntry
                        }
                    }}
                    ready.writeText("1")
                }
                val loaded=Model(folder.absolutePath)
                handler.post{
                    if(destroyed){loaded.close();return@post}
                    try {
                        model=loaded
                        recognizer=Recognizer(loaded,16000f)
                        speech=SpeechService(recognizer,16000f)
                        speech!!.startListening(this)
                        state("Diga “Ok Aura” e depois o comando.")
                    }catch(error:Exception){onError(error)}
                }
            }catch(error:Exception){handler.post{if(!destroyed)onError(error)}}
        }
        return START_NOT_STICKY
    }
    override fun onResult(hypothesis:String?){
        if(destroyed)return
        val text=try{JSONObject(hypothesis?:"{}").optString("text")}catch(_:Exception){return}
        val result=gate.feed(text,SystemClock.elapsedRealtime())?:return
        if(result.first=="awake"){
            state("Estou ouvindo. Diga o comando em até 10 segundos.")
            val tone=android.media.ToneGenerator(android.media.AudioManager.STREAM_NOTIFICATION,60)
            tone.startTone(android.media.ToneGenerator.TONE_PROP_BEEP,120)
            handler.postDelayed({tone.release()},200)
            handler.postDelayed({if(!destroyed)state("Diga “Ok Aura” e depois o comando.")},10000)
        }else{
            VoiceInbox.offer(result.second)
            state("Comando recebido. Abra a AURA para conferir e confirmar.")
        }
    }
    override fun onPartialResult(hypothesis:String?){}
    override fun onFinalResult(hypothesis:String?){}
    override fun onTimeout(){}
    override fun onError(exception:Exception?){VoiceInbox.message="Escuta interrompida. Verifique o microfone e tente ativar novamente.";stopSelf()}
    override fun onDestroy(){
        destroyed=true;VoiceInbox.active=false;VoiceInbox.clear();handler.removeCallbacksAndMessages(null)
        speech?.cancel();speech?.shutdown();recognizer?.close();model?.close();worker.shutdownNow()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
}
