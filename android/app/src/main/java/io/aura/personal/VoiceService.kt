package io.aura.personal

import android.app.*
import android.content.Intent
import android.content.pm.PackageManager
import android.media.*
import android.os.*
import org.json.JSONObject
import org.json.JSONArray
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File
import java.util.concurrent.Executors
import java.util.zip.ZipInputStream
import kotlin.math.sqrt

class VoiceService:Service() {
    private val worker=Executors.newSingleThreadExecutor()
    private val handler=Handler(Looper.getMainLooper())
    @Volatile private var destroyed=false
    override fun onBind(intent:Intent?)=null
    private fun notification(message:String):Notification {
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop=PendingIntent.getService(this,1,Intent(this,VoiceService::class.java).setAction("stop"),PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this,"aura-voice").setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("AURA • Escuta automática").setContentText(message).setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).addAction(android.R.drawable.ic_media_pause,"Pausar escuta",stop).build()
    }
    private fun state(message:String){
        if(destroyed)return
        VoiceInbox.message=message
        handler.post{if(!destroyed)(getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(130,notification(message))}
    }
    private fun unpack(asset:String,folder:String):File {
        val targetFolder=File(filesDir,folder)
        val ready=File(targetFolder,".ready")
        if(ready.exists())return targetFolder
        targetFolder.mkdirs()
        assets.open(asset).use{input->ZipInputStream(input).use{zip->
            var total=0L;var entry=zip.nextEntry
            while(entry!=null){
                if(destroyed)throw InterruptedException()
                val name=entry.name.substringAfter('/')
                if(name.isNotEmpty()){
                    val target=File(targetFolder,name)
                    check(target.canonicalPath.startsWith(targetFolder.canonicalPath+File.separator))
                    if(entry.isDirectory)target.mkdirs()else{
                        target.parentFile?.mkdirs()
                        target.outputStream().use{output->val buffer=ByteArray(16384);var size=zip.read(buffer);while(size!=-1){total+=size;check(total<200L*1024*1024);output.write(buffer,0,size);size=zip.read(buffer)}}
                    }
                }
                zip.closeEntry();entry=zip.nextEntry
            }
        }}
        ready.writeText("1");return targetFolder
    }
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        if(intent?.action=="stop"){VoiceInbox.paused=true;VoiceInbox.message="Escuta pausada. Abra a AURA para retomar.";stopSelf();return START_NOT_STICKY}
        if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){stopSelf();return START_NOT_STICKY}
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(NotificationChannel("aura-voice","Escuta Ok Aura",NotificationManager.IMPORTANCE_LOW))
        startForeground(130,notification("Preparando reconhecimento local…"))
        if(VoiceInbox.active)return START_NOT_STICKY
        VoiceInbox.active=true;VoiceInbox.paused=false
        worker.execute{listen()}
        return START_NOT_STICKY
    }
    @android.annotation.SuppressLint("MissingPermission")
    private fun listen(){
        var recorder:AudioRecord?=null
        var pt:Model?=null;var en:Model?=null
        var wake:Recognizer?=null;var command:Recognizer?=null;var english:Recognizer?=null
        try {
            pt=Model(unpack("voice-model.zip","voice-model").absolutePath)
            en=Model(unpack("voice-model-en.zip","voice-model-en").absolutePath)
            if(destroyed)return
            wake=Recognizer(pt,16000f,JSONArray(listOf("ok aura","[unk]")).toString())
            command=Recognizer(pt,16000f);english=Recognizer(en,16000f)
            val size=maxOf(AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT),6400)
            recorder=AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,size)
            check(recorder.state==AudioRecord.STATE_INITIALIZED)
            recorder.startRecording();check(recorder.recordingState==AudioRecord.RECORDSTATE_RECORDING)
            state("Escuta ativa • diga “Ok Aura”.")
            val samples=ShortArray(1280);var deadline=0L
            val englishParts=ArrayList<String>()
            while(!destroyed && !Thread.currentThread().isInterrupted){
                val count=recorder.read(samples,0,samples.size,AudioRecord.READ_BLOCKING)
                check(count>0)
                VoiceInbox.level=(sqrt((0 until count).sumOf{samples[it].toDouble()*samples[it]}/count)/6000).toFloat().coerceIn(0f,1f)
                val now=SystemClock.elapsedRealtime()
                if(deadline!=0L && now>=deadline){deadline=0;wake.reset();state("Escuta ativa • diga “Ok Aura”.")}
                if(deadline==0L){
                    val final=wake.acceptWaveForm(samples,count)
                    val hypothesis=JSONObject(if(final)wake.result else wake.partialResult).optString(if(final)"text" else "partial")
                    if(VoiceCommands.normalize(hypothesis)=="ok aura"){
                        deadline=now+10000;command.reset();english.reset();englishParts.clear()
                        state("Estou ouvindo. Diga o comando.")
                        handler.post{if(!destroyed){val tone=ToneGenerator(AudioManager.STREAM_NOTIFICATION,45);tone.startTone(ToneGenerator.TONE_PROP_BEEP,90);handler.postDelayed({tone.release()},150)}}
                    }
                    continue
                }
                if(english.acceptWaveForm(samples,count))englishParts.add(JSONObject(english.result).optString("text"))
                if(command.acceptWaveForm(samples,count)){
                    val text=JSONObject(command.result).optString("text")
                    if(VoiceCommands.normalize(text) in listOf("","ok","aura","ok aura"))continue
                    var parsed=VoiceCommands.parse(text)
                    if(parsed?.action=="terminate")parsed=parsed.copy(english=(englishParts+JSONObject(english.finalResult).optString("text")).joinToString(" "))
                    VoiceInbox.offer(parsed);deadline=0;wake.reset()
                    state("Comando recebido • confira na AURA.")
                }
            }
        }catch(_:Exception){if(!destroyed){VoiceInbox.message="Microfone indisponível. Confira as permissões e abra a AURA novamente.";handler.post{stopSelf()}}}
        finally{
            try{recorder?.stop()}catch(_:Exception){};recorder?.release()
            wake?.close();command?.close();english?.close();pt?.close();en?.close();VoiceInbox.level=0f
        }
    }
    override fun onDestroy(){
        destroyed=true;VoiceInbox.active=false;VoiceInbox.level=0f;VoiceInbox.clear();handler.removeCallbacksAndMessages(null);worker.shutdownNow()
        stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy()
    }
}
