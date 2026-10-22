package io.aura.personal

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.RippleDrawable
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.text.Editable
import android.text.InputType
import android.text.TextWatcher
import android.text.TextUtils
import android.util.Base64
import android.util.LruCache
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.widget.*
import org.json.JSONObject
import org.json.JSONArray
import java.net.*
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.UUID
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.*

class MainActivity : Activity() {
    private lateinit var page:LinearLayout
    private lateinit var topSection:LinearLayout
    private lateinit var bottomNavigation:LinearLayout
    private lateinit var status:TextView
    private lateinit var summary:TextView
    private lateinit var connectionDot:TextView
    private lateinit var title:TextView
    private lateinit var subtitle:TextView
    private lateinit var cpu:MetricView
    private lateinit var ram:MetricView
    private lateinit var progress:ProgressBar
    private val executor=Executors.newSingleThreadExecutor()
    private val iconExecutor=Executors.newFixedThreadPool(2)
    private val updateExecutor=Executors.newSingleThreadExecutor()
    private val updateHandler=android.os.Handler(android.os.Looper.getMainLooper())
    private var checkingUpdates=false
    private var downloadingUpdate=false
    private var updateForeground=false
    private var lastNotifiedBuild=0
    private var updateMessage="Verificação automática ao abrir o aplicativo."
    private var voiceStatusText:TextView?=null
    private val voicePoll=object:Runnable{override fun run(){
        if(!updateForeground)return
        voiceStatusText?.text=VoiceInbox.message
        VoiceInbox.take()?.let{receiveVoice(it.second)}
        updateHandler.postDelayed(this,400)
    }}
    private val updateCheck=object:Runnable{override fun run(){checkUpdates(false);updateHandler.postDelayed(this,15*60*1000L)}}
    @Volatile private var profile:JSONObject?=null
    @Volatile private var generation=0
    private var busy=false
    private var startupFailed=false
    private var connected=false
    private var currentPage="home"
    private var lastStatus:JSONObject?=null
    private var query=""
    private var allRows=emptyList<JSONObject>()
    private var filteredRows=emptyList<JSONObject>()
    private var selected:JSONObject?=null
    private var adapter:ProcessAdapter?=null
    private var selectedCard:LinearLayout?=null
    private var resultCount:TextView?=null
    private val navButtons=linkedMapOf<String,LinearLayout>()
    private val icons=object:LruCache<String,Bitmap>(2*1024*1024){override fun sizeOf(key:String,value:Bitmap)=value.byteCount}

    private fun dp(v:Int)=AuraTheme.dp(this,v)
    private fun vertical()=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL}
    private fun horizontal()=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL;gravity=Gravity.CENTER_VERTICAL}
    private fun text(value:String,size:Float=14f,color:Int=AuraTheme.text,bold:Boolean=false)=TextView(this).apply{
        text=value;textSize=size;setTextColor(color);typeface=Typeface.create("sans-serif",if(bold)Typeface.BOLD else Typeface.NORMAL)
    }
    private fun gap(parent:LinearLayout,height:Int){parent.addView(View(this),LinearLayout.LayoutParams(1,dp(height)))}
    private fun card(parent:LinearLayout):LinearLayout=vertical().apply{
        background=AuraTheme.surface(this@MainActivity);setPadding(dp(18),dp(18),dp(18),dp(18))
        parent.addView(this,LinearLayout.LayoutParams(-1,-2).apply{bottomMargin=dp(14)})
    }
    private fun actionButton(parent:LinearLayout,label:String,kind:String="",danger:Boolean=false,accent:Boolean=false,action:()->Unit):Button=Button(this).apply{
        text=label;textSize=14f;isAllCaps=false;gravity=Gravity.CENTER_VERTICAL or Gravity.START
        setTextColor(if(danger)AuraTheme.red else if(accent)AuraTheme.teal else AuraTheme.text)
        background=RippleDrawable(ColorStateList.valueOf(0x2231D0C3),AuraTheme.surface(this@MainActivity,if(danger)Color.rgb(56,35,45) else AuraTheme.panel,9,if(danger)Color.rgb(120,64,75) else AuraTheme.line),null)
        backgroundTintList=null
        setPadding(dp(14),dp(10),dp(14),dp(10));minimumHeight=dp(52);stateListAnimator=null
        if(kind.isNotEmpty()){val drawable=AuraIcon(kind,if(danger)AuraTheme.red else if(accent)AuraTheme.teal else AuraTheme.muted);drawable.setBounds(0,0,dp(22),dp(22));setCompoundDrawables(drawable,null,null,null);compoundDrawablePadding=dp(12)}
        setOnClickListener{action()}
        parent.addView(this,LinearLayout.LayoutParams(-1,-2).apply{topMargin=dp(8)})
    }
    private fun input(hintText:String)=EditText(this).apply{
        hint=hintText;textSize=14f;setTextColor(AuraTheme.text);setHintTextColor(AuraTheme.muted)
        background=AuraTheme.surface(this@MainActivity,AuraTheme.bg,9);setPadding(dp(14),dp(12),dp(14),dp(12))
        backgroundTintList=null
    }
    private fun safeUi(action:()->Unit){runOnUiThread{if(!isDestroyed && !isFinishing && !startupFailed)action()}}

    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState)
        try { createInterface(savedInstanceState) }
        catch(error:Exception){showStartupFailure(error)}
        catch(error:LinkageError){showStartupFailure(error)}
    }
    private fun showStartupFailure(error:Throwable){
        startupFailed=true
        val diagnostic=StartupDiagnostics.report(error)
        StartupDiagnostics.save(this,diagnostic)
        android.util.Log.e("AURA-startup",diagnostic)
        val body=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(dp(24),dp(40),dp(24),dp(24));setBackgroundColor(Color.rgb(12,18,25))}
        fun message(value:String,size:Float=15f){body.addView(TextView(this).apply{text=value;textSize=size;setTextColor(Color.WHITE);setPadding(0,dp(8),0,dp(8))})}
        message("A AURA não conseguiu iniciar",23f)
        message("Feche e abra novamente. Se persistir, copie o diagnóstico e envie para corrigirmos. Sua conexão salva foi preservada.")
        message(diagnostic,13f)
        body.addView(Button(this).apply{text="Copiar diagnóstico";isAllCaps=false;setOnClickListener{val clipboard=getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager;clipboard.setPrimaryClip(android.content.ClipData.newPlainText("Diagnóstico AURA",diagnostic));Toast.makeText(this@MainActivity,"Diagnóstico copiado",Toast.LENGTH_SHORT).show()}})
        body.addView(Button(this).apply{text="Tentar novamente";isAllCaps=false;setOnClickListener{recreate()}})
        body.addView(Button(this).apply{text="Fechar";isAllCaps=false;setOnClickListener{finish()}})
        setContentView(ScrollView(this).apply{addView(body)})
    }
    private fun createInterface(savedInstanceState:Bundle?) {
        val shell=vertical().apply{setBackgroundColor(AuraTheme.bg)}
        topSection=vertical();shell.addView(topSection)
        setContentView(shell)
        // PhoneWindow.getInsetsController() dereferences its decor internally.
        // A nullable controller does not protect against a missing decor before
        // setContentView: install the window content before configuring bars.
        configureSystemBars()
        shell.setOnApplyWindowInsetsListener{v,insets->
            if(Build.VERSION.SDK_INT>=30){
                val bars=insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
                v.setPadding(bars.left,bars.top,bars.right,bars.bottom)
                val typing=insets.isVisible(WindowInsets.Type.ime())
                topSection.visibility=if(typing)View.GONE else View.VISIBLE
                if(::bottomNavigation.isInitialized)bottomNavigation.visibility=if(typing)View.GONE else View.VISIBLE
            }else applyLegacyInsets(v,insets)
            insets
        }
        val header=horizontal().apply{setPadding(dp(20),dp(10),dp(12),dp(10))}
        header.addView(text("A U R A",25f),LinearLayout.LayoutParams(0,-2,1f))
        val settings=ImageButton(this).apply{setImageDrawable(AuraIcon("settings"));background=null;contentDescription="Ajustes de conexão";setPadding(dp(12),dp(12),dp(12),dp(12));setOnClickListener{showPage("settings")}}
        header.addView(settings,LinearLayout.LayoutParams(dp(48),dp(48)));topSection.addView(header)
        val connection=horizontal().apply{setPadding(dp(22),dp(12),dp(20),dp(12));background=AuraTheme.surface(this@MainActivity,AuraTheme.bg,0);setOnClickListener{showPage("settings")};isFocusable=true;contentDescription="Estado do PC e conexão"}
        connectionDot=text("●",22f,AuraTheme.muted);connection.addView(connectionDot,LinearLayout.LayoutParams(dp(32),-2))
        summary=text("Nenhum PC conectado",13f,AuraTheme.muted);connection.addView(summary,LinearLayout.LayoutParams(0,-2,1f))
        connection.addView(text("›",26f,AuraTheme.muted));topSection.addView(connection)
        val heading=vertical().apply{setPadding(dp(18),dp(14),dp(18),dp(10))}
        title=text("Visão geral",24f,bold=true);subtitle=text("Seu computador, conectado a você.",12f,AuraTheme.muted)
        heading.addView(title);gap(heading,5);heading.addView(subtitle);topSection.addView(heading)
        val metrics=horizontal().apply{setPadding(dp(16),0,dp(16),dp(12))}
        cpu=MetricView(this,"cpu");ram=MetricView(this,"ram")
        metrics.addView(cpu,LinearLayout.LayoutParams(0,dp(100),1f).apply{rightMargin=dp(6)})
        metrics.addView(ram,LinearLayout.LayoutParams(0,dp(100),1f).apply{leftMargin=dp(6)})
        topSection.addView(metrics)
        page=vertical().apply{setPadding(dp(16),0,dp(16),0)}
        shell.addView(page,LinearLayout.LayoutParams(-1,0,1f))
        progress=ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal).apply{isIndeterminate=true;indeterminateTintList=ColorStateList.valueOf(AuraTheme.teal);visibility=View.GONE}
        shell.addView(progress,LinearLayout.LayoutParams(-1,dp(2)))
        status=text("Conecte o PC para começar.",11f,AuraTheme.muted).apply{setPadding(dp(18),dp(6),dp(18),dp(6));accessibilityLiveRegion=View.ACCESSIBILITY_LIVE_REGION_POLITE;maxLines=3;ellipsize=TextUtils.TruncateAt.END}
        shell.addView(status)
        val nav=horizontal().apply{background=AuraTheme.surface(this@MainActivity,AuraTheme.bg,0);setPadding(dp(4),dp(4),dp(4),dp(4))}
        bottomNavigation=nav
        for((key,label,kind) in listOf(Triple("home","Início","home"),Triple("processes","Processos","processes"),Triple("power","Energia","power"),Triple("settings","Ajustes","settings"))){
            val item=vertical().apply{gravity=Gravity.CENTER;minimumHeight=dp(58);background=RippleDrawable(ColorStateList.valueOf(0x2231D0C3),null,AuraTheme.surface(this@MainActivity));isFocusable=true;contentDescription=label;setOnClickListener{showPage(key)}}
            item.addView(ImageView(this).apply{setImageDrawable(AuraIcon(kind));importantForAccessibility=View.IMPORTANT_FOR_ACCESSIBILITY_NO},LinearLayout.LayoutParams(dp(23),dp(23)))
            item.addView(text(label,11f,AuraTheme.muted).apply{gravity=Gravity.CENTER},LinearLayout.LayoutParams(-1,-2).apply{topMargin=dp(4)})
            nav.addView(item,LinearLayout.LayoutParams(0,-2,1f));navButtons[key]=item
        }
        shell.addView(nav)
        try{
            getSharedPreferences("aura",MODE_PRIVATE).getString("profile",null)?.let{profile=JSONObject(decrypt(it))}
            summary.text=profile?.let{"PC salvo\n"+it.getString("name")}?:"Nenhum PC conectado"
            if(profile!=null)status.text="Estado ainda não consultado."
        }catch(_:Exception){status.text="Conexão salva indisponível. Conecte o PC novamente."}
        query=savedInstanceState?.getString("query")?:""
        showPage(savedInstanceState?.getString("page")?:"home",false)
        if(currentPage=="processes" && profile!=null)processes()
    }
    @Suppress("DEPRECATION")
    private fun configureSystemBars(){
        window.statusBarColor=AuraTheme.bg;window.navigationBarColor=AuraTheme.bg
        if(Build.VERSION.SDK_INT>=30)window.insetsController?.setSystemBarsAppearance(0,WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS)
        else window.decorView.systemUiVisibility=0
    }
    @Suppress("DEPRECATION")
    private fun applyLegacyInsets(view:View,insets:WindowInsets){view.setPadding(insets.systemWindowInsetLeft,insets.systemWindowInsetTop,insets.systemWindowInsetRight,insets.systemWindowInsetBottom)}
    override fun onSaveInstanceState(outState:Bundle){outState.putString("page",currentPage);outState.putString("query",query);super.onSaveInstanceState(outState)}

    private fun showPage(key:String,load:Boolean=true){
        currentPage=key;page.removeAllViews();adapter=null;selectedCard=null;resultCount=null
        val names=mapOf("home" to Pair("Visão geral","Seu computador, conectado a você."),"processes" to Pair("Processos","Veja e gerencie os aplicativos do seu computador."),"power" to Pair("Energia","Controle e agendamentos do computador."),"settings" to Pair("Conexão","Conecte seu Android à AURA do Windows."),"history" to Pair("Histórico","Atividade recente do agente."))
        title.text=names[key]?.first?:"AURA";subtitle.text=names[key]?.second?:""
        navButtons.forEach{(name,item)->val active=name==key || (key=="history" && name=="settings");val color=if(active)AuraTheme.teal else AuraTheme.muted
            (item.getChildAt(0) as ImageView).setImageDrawable(AuraIcon(if(name=="settings")"settings" else name,color));(item.getChildAt(1) as TextView).setTextColor(color);item.isSelected=active}
        if(key=="processes"){buildProcesses();if(load && profile!=null)processes();return}
        val scroll=ScrollView(this).apply{isFillViewport=true;clipToPadding=false}
        val body=vertical();scroll.addView(body);page.addView(scroll,LinearLayout.LayoutParams(-1,-1))
        when(key){
            "home"->{
                val c=card(body);c.addView(text("SEU COMPUTADOR",11f,AuraTheme.muted));gap(c,10)
                c.addView(text(profile?.optString("name")?:"Conecte seu PC",21f,bold=true));gap(c,8)
                c.addView(text(modeDescription(),13f,AuraTheme.muted))
                actionButton(c,"Atualizar estado","refresh",accent=true){refresh()}
                actionButton(c,"Ligar PC • Wake-on-LAN","power"){wake()}
                val voice=card(body);voice.addView(text("Controle por voz • Ok Aura",18f,bold=true))
                voiceStatusText=text(VoiceInbox.message,13f,AuraTheme.muted);voice.addView(voiceStatusText)
                voice.addView(text("Diga “Ok Aura”, aguarde o sinal e fale: “encerrar Discord”, “desligar em trinta minutos” ou “ligar o PC”.",13f))
                voice.addView(text("A escuta é local. Em segundo plano, toque na notificação para conferir o comando. Ações de energia e encerramento pedem confirmação.",12f,AuraTheme.muted))
                actionButton(voice,"Ativar / desativar escuta"){toggleVoice()}
                val schedule=card(body);schedule.addView(text("PRÓXIMO AGENDAMENTO",11f,AuraTheme.muted));gap(schedule,10);schedule.addView(text(scheduleDescription(),14f))
                actionButton(schedule,"Ver energia e agendamentos","calendar"){showPage("power")}
                actionButton(body,"Conectar PC","connection"){importProfile()}
                actionButton(body,"Histórico de atividade","history"){showPage("history")}
            }
            "power"->{
                val c=card(body);c.addView(text("Energia do computador",18f,bold=true));gap(c,8);c.addView(text(modeDescription(),13f,AuraTheme.muted))
                actionButton(c,"Ligar PC • Wake-on-LAN","power",accent=true){wake()}
                actionButton(c,"Desligar PC","power",danger=true){confirm("Desligar o PC? Salve seus arquivos antes."){command("power",JSONObject().put("action","shutdown").put("confirm",true))}}
                actionButton(c,"Reiniciar PC","refresh"){confirm("Reiniciar o PC? Salve seus arquivos antes."){command("power",JSONObject().put("action","restart").put("confirm",true))}}
                val sc=card(body);sc.addView(text("Agendamentos",18f,bold=true));gap(sc,8);sc.addView(text(scheduleDescription(),13f,AuraTheme.muted))
                actionButton(sc,"Agendar desligamento","calendar",accent=true){schedule()}
                actionButton(sc,"Cancelar agendamento"){command("shutdown/cancel",JSONObject())}
                actionButton(body,"Atualizar estado","refresh"){refresh()}
            }
            "settings"->{
                val c=card(body);c.addView(text("Seu computador",18f,bold=true));gap(c,8);c.addView(text(profile?.optString("name")?:"Nenhuma conexão salva",14f,AuraTheme.muted))
                actionButton(c,"Conectar PC","connection",accent=true){importProfile()}
                actionButton(c,"Atualizar estado","refresh"){refresh()}
                actionButton(c,"Esquecer PC","trash",danger=true){forget()}
                val hint=card(body);hint.addView(text("Conexão privada",16f,bold=true));gap(hint,8);hint.addView(text("Gere o código no Windows e cole aqui. O celular e o PC precisam se alcançar pela rede local. O modo real ou simulação é alterado no Windows.",13f,AuraTheme.muted))
                actionButton(body,"Histórico de atividade","history"){showPage("history")}
                val updates=card(body);updates.addView(text("Atualizações • AURA ${AuraVersion.name}",16f,bold=true));gap(updates,8)
                updates.addView(text(updateMessage,12f,AuraTheme.muted))
                actionButton(updates,"Verificar atualizações","refresh"){checkUpdates(true)}
                if(UpdateInstaller.pending(this)!=null)actionButton(updates,"Instalar atualização baixada","refresh"){installDownloadedUpdate()}
                gap(body,14);body.addView(text("AURA ${AuraVersion.name}",11f,AuraTheme.muted))
            }
            "history"->{
                val log=text("Atualize para consultar os eventos.",12f,AuraTheme.muted).apply{typeface=Typeface.MONOSPACE;setTextIsSelectable(true)}
                val c=card(body);c.addView(log)
                fun loadLogs(){work{val lines=JSONObject(api("logs")).getJSONArray("lines");val value=(0 until lines.length()).joinToString("\n"){lines.getString(it)};safeUi{if(currentPage=="history")log.text=value.ifEmpty{"Nenhum evento registrado."}};"Histórico atualizado."}}
                actionButton(body,"Atualizar histórico","refresh"){loadLogs()};if(load && profile!=null)loadLogs()
            }
        }
    }

    private fun modeDescription():String=lastStatus?.let{if(it.getBoolean("dry_run"))"Simulação ativa • ações de energia simuladas" else "Modo real ativo • ações enviadas ao Windows"}?:"Estado ainda não consultado"

    override fun onResume(){
        super.onResume()
        updateForeground=true
        if(!startupFailed){
            updateHandler.post(voicePoll)
            val prefs=getSharedPreferences("aura",MODE_PRIVATE)
            if(prefs.getBoolean("resume_download_install",false)){
                prefs.edit().putBoolean("resume_download_install",false).apply()
                installDownloadedUpdate()
            }
            if(prefs.getBoolean("resume_update_install",false)){
                prefs.edit().putBoolean("resume_update_install",false).apply()
                if(packageManager.canRequestPackageInstalls())installDownloadedUpdate()
                else updateMessage="Autorize a instalação para concluir. O APK já foi baixado."
            }
            updateHandler.postDelayed(updateCheck,2500)
        }
    }
    override fun onPause(){updateForeground=false;updateHandler.removeCallbacks(voicePoll);updateHandler.removeCallbacks(updateCheck);super.onPause()}
    private fun toggleVoice(){
        if(VoiceInbox.active){stopService(android.content.Intent(this,VoiceService::class.java));VoiceInbox.message="Escuta desativada.";return}
        if(checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)!=android.content.pm.PackageManager.PERMISSION_GRANTED){
            val permissions=mutableListOf(android.Manifest.permission.RECORD_AUDIO)
            if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED)permissions.add(android.Manifest.permission.POST_NOTIFICATIONS)
            requestPermissions(permissions.toTypedArray(),130);return
        }
        try{startForegroundService(android.content.Intent(this,VoiceService::class.java))}
        catch(_:Exception){VoiceInbox.message="Não foi possível iniciar a escuta. Verifique as permissões do microfone."}
    }
    override fun onRequestPermissionsResult(requestCode:Int,permissions:Array<out String>,grantResults:IntArray){
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        if(requestCode==130){
            if(updateForeground && checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)==android.content.pm.PackageManager.PERMISSION_GRANTED)toggleVoice()
            else VoiceInbox.message="Autorize o microfone para ativar “Ok Aura”."
        }
    }
    private fun receiveVoice(value:VoiceCommand?){
        if(value==null){VoiceInbox.message="Comando não reconhecido. Diga “Ok Aura” e tente novamente.";return}
        VoiceInbox.message="Diga “Ok Aura” para outro comando."
        when(value.action){
            "status"->refresh()
            "wake"->wake()
            "cancel"->command("shutdown/cancel",JSONObject())
            "shutdown","restart"->confirm(if(value.action=="shutdown")"Desligar o PC? Salve seus arquivos antes." else "Reiniciar o PC? Salve seus arquivos antes."){command("power",JSONObject().put("action",value.action).put("confirm",true))}
            "schedule"->confirm("Confirmar desligamento em ${value.seconds/60} minutos?"){command("shutdown",JSONObject().put("confirm",true).put("delay_seconds",value.seconds))}
            "terminate"->work{
                val data=JSONArray(api("processes"))
                val matches=(0 until data.length()).map{data.getJSONObject(it)}.filter{VoiceCommands.matchesProcess(it,value.argument)}
                safeUi{
                    fun choose(row:JSONObject){confirm("Encerrar ${row.getString("name")} (PID ${row.getInt("pid")})? Alterações não salvas podem ser perdidas."){command("processes/terminate",JSONObject().put("pid",row.getInt("pid")).put("name",row.getString("name")).put("created_at",row.getDouble("created_at")))}}
                    if(matches.size==1)choose(matches[0])
                    else if(matches.isNotEmpty())AlertDialog.Builder(this).setTitle("Selecione o processo").setItems(matches.map{"${it.getString("name")} • PID ${it.getInt("pid")}"}.toTypedArray()){_,index->choose(matches[index])}.setNegativeButton("Cancelar",null).show()
                    else VoiceInbox.message="Programa não encontrado. Confira o nome e o PID na aba Processos."
                }
                "Consulta por voz concluída."
            }
        }
    }
    private fun checkUpdates(manual:Boolean){
        if(checkingUpdates || downloadingUpdate || isDestroyed || startupFailed)return
        checkingUpdates=true
        if(manual){updateMessage="Consultando o GitHub…";if(currentPage=="settings")showPage("settings",false)}
        updateExecutor.execute {
            try {
                val result=UpdateClient.check()
                safeUi {
                    updateMessage=if(result.available)"Nova versão disponível: ${result.version}" else "Você está na versão mais recente publicada."
                    if(currentPage=="settings")showPage("settings",false)
                    if(result.available && (manual || lastNotifiedBuild!=result.build)){
                        lastNotifiedBuild=result.build
                        AlertDialog.Builder(this).setTitle("Atualização disponível").setMessage("AURA ${result.version} está pronta. A AURA vai baixar e verificar o APK. Depois, basta confirmar a instalação no Android.")
                            .setNegativeButton("Depois",null).setPositiveButton("Atualizar agora"){_,_->downloadUpdate(result)}.show()
                    }
                }
            } catch(error:Exception){safeUi{
                updateMessage=when(error){is IllegalStateException,is IllegalArgumentException->error.message?:"Release inválida.";else->"Sem acesso ao GitHub. Tente novamente mais tarde."}
                if(currentPage=="settings")showPage("settings",false)
            }} finally {safeUi{checkingUpdates=false}}
        }
    }
    private fun downloadUpdate(result:UpdateClient.Result){
        if(downloadingUpdate)return
        downloadingUpdate=true;updateMessage="Baixando e verificando a atualização…";status.text=updateMessage
        if(currentPage=="settings")showPage("settings",false)
        updateExecutor.execute{
            try{
                UpdateInstaller.download(this,result)
                safeUi{
                    downloadingUpdate=false;updateMessage="Atualização verificada. Confirme a instalação."
                    if(updateForeground)installDownloadedUpdate()
                    else getSharedPreferences("aura",MODE_PRIVATE).edit().putBoolean("resume_download_install",true).apply()
                }
            }catch(error:Exception){safeUi{
                downloadingUpdate=false;updateMessage=if(error is IllegalArgumentException)error.message?:"Atualização inválida." else "O download falhou. Tente novamente; sua instalação foi preservada."
                status.text=updateMessage;if(currentPage=="settings")showPage("settings",false)
            }}
        }
    }
    private fun installDownloadedUpdate(){
        val result=UpdateInstaller.pending(this)?:return
        updateExecutor.execute {
            try {
                UpdateInstaller.verifyPackage(this,UpdateInstaller.file(this),result)
                safeUi {
                    if(!updateForeground){getSharedPreferences("aura",MODE_PRIVATE).edit().putBoolean("resume_download_install",true).apply();return@safeUi}
                    try{
                        if(!packageManager.canRequestPackageInstalls()){
                            getSharedPreferences("aura",MODE_PRIVATE).edit().putBoolean("resume_update_install",true).apply()
                            AlertDialog.Builder(this).setTitle("Permitir atualização da AURA")
                                .setMessage("Autorize a AURA a instalar esta atualização na próxima tela. Ao voltar, a instalação será retomada.")
                                .setNegativeButton("Depois"){_,_->getSharedPreferences("aura",MODE_PRIVATE).edit().putBoolean("resume_update_install",false).apply()}
                                .setPositiveButton("Continuar"){_,_->
                                    startActivity(android.content.Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,android.net.Uri.parse("package:$packageName")))
                                }.show()
                        }else startActivity(UpdateInstaller.intent(this))
                    }catch(_:android.content.ActivityNotFoundException){status.text="Não foi possível abrir o instalador do Android. Tente novamente em Ajustes."}
                    catch(_:SecurityException){status.text="O Android não permitiu abrir o instalador. Verifique a permissão de instalar atualizações em Ajustes."}
                }
            }catch(error:Exception){safeUi{status.text=error.message?:"O APK não passou na verificação. Baixe a atualização novamente."}}
        }
    }
    private fun scheduleDescription():String=lastStatus?.let{if(it.isNull("shutdown_at"))"Nenhum desligamento agendado." else "Desligamento: "+java.text.DateFormat.getDateTimeInstance().format(java.util.Date((it.getDouble("shutdown_at")*1000).toLong()))}?:"Atualize o estado para consultar o agendamento."
    private fun updateStatus(s:JSONObject){lastStatus=s;connected=true;cpu.update(s);ram.update(s);summary.text="PC conectado\n"+s.getString("hostname");summary.setTextColor(AuraTheme.teal);connectionDot.setTextColor(Color.rgb(55,218,139))}
    private fun disconnected(){connected=false;lastStatus=null;cpu.update(null);ram.update(null);connectionDot.setTextColor(AuraTheme.muted);summary.setTextColor(AuraTheme.muted);summary.text="PC indisponível\n"+(profile?.optString("name")?:"Conecte o PC")}
    private fun confirm(message:String,action:()->Unit){AlertDialog.Builder(this).setTitle("AURA").setMessage(message).setNegativeButton("Cancelar",null).setPositiveButton("Confirmar"){_,_->action()}.show()}
    private fun work(action:()->String){
        if(busy){status.text="Aguarde a ação em andamento.";return}
        busy=true;status.text="Carregando…";progress.visibility=View.VISIBLE
        executor.execute{
            try{val message=action();safeUi{busy=false;progress.visibility=View.GONE;status.text=message}}
            catch(e:Exception){safeUi{busy=false;progress.visibility=View.GONE;status.text="Não foi possível concluir: "+(e.message?:"falha de conexão");if(e is java.io.IOException || e is CertificateException)disconnected()}}
        }
    }
    private fun requireProfile():JSONObject=profile?:throw IllegalStateException("Conecte o PC primeiro.")
    private fun refresh(){work{val data=JSONObject(api("status"));safeUi{updateStatus(data);if(currentPage!="processes")showPage(currentPage,false)};"Conectado ao PC."}}
    private fun command(path:String,body:JSONObject){work{
        val message=JSONObject(api(path,body)).getString("message")
        if(path=="processes/terminate"){
            val data=JSONArray(api("processes"));safeUi{acceptProcesses(data)}
        }else{
            val data=JSONObject(api("status"));safeUi{updateStatus(data);if(currentPage!="processes")showPage(currentPage,false)}
        }
        message
    }}
    private fun schedule(){
        val field=input("Minutos até desligar").apply{inputType=InputType.TYPE_CLASS_NUMBER;setText("30")}
        val dialog=AlertDialog.Builder(this).setTitle("Agendar desligamento").setMessage("De 1 a 10080 minutos.").setView(field).setNegativeButton("Cancelar",null).setPositiveButton("Agendar",null).create()
        dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{val minutes=field.text.toString().toIntOrNull();if(minutes==null || minutes !in 1..10080)field.error="Informe de 1 a 10080 minutos." else{dialog.dismiss();command("shutdown",JSONObject().put("confirm",true).put("delay_seconds",minutes*60))}}};dialog.show()
    }
    private fun importProfile(){
        if(busy){status.text="Aguarde a ação em andamento antes de alterar a conexão.";return}
        val field=input("Cole o código gerado na AURA do Windows").apply{minLines=3;inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE}
        val dialog=AlertDialog.Builder(this).setTitle("Conectar PC").setView(field).setNegativeButton("Cancelar",null).setPositiveButton("Salvar",null).create()
        dialog.setOnShowListener{dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener{
            try{
                val value=String(Base64.decode(field.text.toString().filterNot{it.isWhitespace()},Base64.URL_SAFE),Charsets.UTF_8)
                val p=JSONObject(value);require(p.getInt("version")==1);ipv4(p.getString("host"));ipv4(p.getString("broadcast"))
                require(p.getInt("port") in 1..65535 && p.getInt("wolPort") in 1..65535);require(p.getString("token").length>=32)
                require(p.getString("fingerprint").matches(Regex("[0-9a-fA-F]{64}")));macBytes(p.getString("mac"))
                getSharedPreferences("aura",MODE_PRIVATE).edit().putString("profile",encrypt(value)).apply();profile=p;clearProcessState();disconnected()
                summary.text="PC salvo\n"+p.getString("name");status.text="Conexão salva. Atualize o estado ou ligue o PC.";dialog.dismiss();showPage("settings",false)
            }catch(_:Exception){field.error="Código inválido. Gere novamente no Windows."}
        }};dialog.show()
    }
    private fun clearProcessState(){generation++;icons.evictAll();allRows=emptyList();filteredRows=emptyList();selected=null;query=""}
    private fun forget(){
        if(busy){status.text="Aguarde a ação em andamento.";return}
        confirm("Remover a conexão salva neste celular?"){getSharedPreferences("aura",MODE_PRIVATE).edit().clear().apply();profile=null;clearProcessState();disconnected();summary.text="Nenhum PC conectado";status.text="Conexão removida deste celular.";showPage("settings",false)}
    }

    private fun buildProcesses(){
        val search=input("Buscar aplicativo ou PID").apply{setSingleLine();setText(query);val icon=AuraIcon("search");icon.setBounds(0,0,dp(21),dp(21));setCompoundDrawables(icon,null,null,null);compoundDrawablePadding=dp(12);imeOptions=android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH}
        page.addView(search,LinearLayout.LayoutParams(-1,-2).apply{bottomMargin=dp(12)})
        val columns=horizontal().apply{setPadding(dp(12),dp(10),dp(12),dp(10));background=AuraTheme.surface(this@MainActivity,AuraTheme.panel,8)}
        columns.addView(text("Aplicativo",11f,AuraTheme.muted),LinearLayout.LayoutParams(0,-2,1f))
        columns.addView(text("PID",11f,AuraTheme.muted),LinearLayout.LayoutParams(dp(52),-2))
        columns.addView(text("Memória",11f,AuraTheme.muted),LinearLayout.LayoutParams(dp(74),-2));page.addView(columns)
        val list=ListView(this).apply{divider=android.graphics.drawable.ColorDrawable(AuraTheme.line);dividerHeight=dp(1);setPadding(0,0,0,0);clipToPadding=false;setCacheColorHint(Color.TRANSPARENT)}
        adapter=ProcessAdapter();list.adapter=adapter;page.addView(list,LinearLayout.LayoutParams(-1,0,1f))
        val empty=text("Atualize para carregar os aplicativos.",13f,AuraTheme.muted).apply{gravity=Gravity.CENTER;setPadding(dp(12),dp(24),dp(12),dp(24))}
        page.addView(empty,LinearLayout.LayoutParams(-1,0,1f));list.emptyView=empty
        list.setOnItemClickListener{_,_,position,_->selected=filteredRows[position];adapter?.notifyDataSetChanged();updateSelectedCard()}
        selectedCard=vertical().apply{background=AuraTheme.surface(this@MainActivity);setPadding(dp(12),dp(8),dp(12),dp(8))};page.addView(selectedCard)
        resultCount=text("",10f,AuraTheme.muted);page.addView(resultCount)
        actionButton(page,"Atualizar processos","refresh"){processes()}
        search.addTextChangedListener(object:TextWatcher{override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){};override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int){query=s?.toString()?:"";filterRows();empty.text=if(allRows.isEmpty())"Nenhum processo elegível carregado." else "Nenhum resultado para esta busca."};override fun afterTextChanged(s:Editable?){}})
        filterRows()
    }
    private fun filterRows(){
        val term=query.trim();filteredRows=allRows.filter{it.getString("name").contains(term,true) || it.getInt("pid").toString().contains(term)}
        if(selected!=null && filteredRows.none{sameProcess(it,selected!!)})selected=null
        adapter?.notifyDataSetChanged();resultCount?.text="${filteredRows.size} de ${allRows.size} processos elegíveis • maior memória primeiro";updateSelectedCard()
    }
    private fun sameProcess(a:JSONObject,b:JSONObject)=a.getInt("pid")==b.getInt("pid") && a.getDouble("created_at")==b.getDouble("created_at")
    private fun updateSelectedCard(){
        val c=selectedCard?:return;c.removeAllViews();val r=selected;c.visibility=if(r==null)View.GONE else View.VISIBLE
        if(r!=null){c.addView(text(r.getString("name")+" • PID "+r.getInt("pid"),12f,bold=true));actionButton(c,"Encerrar processo","trash",danger=true){confirm("Encerrar ${r.getString("name")} (PID ${r.getInt("pid")})? Alterações não salvas podem ser perdidas."){command("processes/terminate",JSONObject().put("pid",r.getInt("pid")).put("name",r.getString("name")).put("created_at",r.getDouble("created_at")))}}}
    }
    private fun processes(){work{
        val data=JSONArray(api("processes"));val s=JSONObject(api("status"));safeUi{updateStatus(s);acceptProcesses(data)}
        if(data.length()==0)"Nenhum processo elegível para encerramento." else "Lista atualizada. Selecione pelo nome e PID."
    }}
    private fun acceptProcesses(data:JSONArray){
        allRows=(0 until data.length()).map{data.getJSONObject(it)};selected=selected?.let{old->allRows.firstOrNull{sameProcess(it,old)}};filterRows()
        val current=++generation;val p=profile?:return
        val keys=(filteredRows+allRows).mapNotNull{if(it.isNull("icon_id"))null else it.optString("icon_id").takeIf{key->key.matches(Regex("[0-9a-f]{64}"))}}
            .distinct().filter{icons.get(it)==null}
        keys.chunked(16).forEach { batch -> iconExecutor.execute {
            var remaining=batch
            try {
                for(attempt in 0..7){
                    if(isDestroyed || current!=generation || remaining.isEmpty())return@execute
                    val response=JSONObject(api("process-icons",JSONObject().put("ids",JSONArray(remaining)),target=p)).getJSONObject("icons")
                    val retry=mutableListOf<String>()
                    val decoded=mutableMapOf<String,Bitmap>()
                    for(key in remaining){
                        val value=response.optJSONObject(key)?:continue
                        if(value.optString("state")=="pending")retry.add(key)
                        else ProcessIconDecoder.decode(value)?.let{decoded[key]=it}
                    }
                    safeUi{if(current==generation){decoded.forEach{(key,bitmap)->icons.put(key,bitmap)};adapter?.notifyDataSetChanged()}}
                    remaining=retry
                    if(remaining.isNotEmpty())Thread.sleep(200L*(attempt+1))
                }
            }catch(_:Exception){safeUi{if(current==generation)status.text="Alguns ícones não foram carregados. Atualize também a AURA do Windows para 0.1.3 e tente novamente."}}
        }}
    }
    private inner class ProcessAdapter:BaseAdapter(){
        override fun getCount()=filteredRows.size
        override fun getItem(position:Int)=filteredRows[position]
        override fun getItemId(position:Int)=getItem(position).getInt("pid").toLong()
        override fun getView(position:Int,convertView:View?,parent:ViewGroup):View{
            val row=getItem(position);val active=selected?.let{sameProcess(row,it)}?:false
            val view=horizontal().apply{minimumHeight=dp(68);setPadding(dp(12),dp(12),dp(8),dp(12));setBackgroundColor(if(active)AuraTheme.selected else AuraTheme.bg);contentDescription="${row.getString("name")}, PID ${row.getInt("pid")}, ${row.getDouble("ram_mb")} megabytes"}
            val id=if(row.isNull("icon_id"))"" else row.optString("icon_id");val bitmap=icons.get(id)
            if(bitmap!=null)view.addView(ImageView(this@MainActivity).apply{setImageBitmap(bitmap);importantForAccessibility=View.IMPORTANT_FOR_ACCESSIBILITY_NO},LinearLayout.LayoutParams(dp(34),dp(34)).apply{rightMargin=dp(10)})
            else view.addView(text(row.getString("name").take(1).uppercase(),17f,AuraTheme.muted,true).apply{gravity=Gravity.CENTER;background=AuraTheme.surface(this@MainActivity,Color.rgb(38,55,70),8)},LinearLayout.LayoutParams(dp(34),dp(34)).apply{rightMargin=dp(10)})
            view.addView(text(row.getString("name"),13f).apply{maxLines=2;ellipsize=TextUtils.TruncateAt.END},LinearLayout.LayoutParams(0,-2,1f).apply{rightMargin=dp(6)})
            view.addView(text(row.getInt("pid").toString(),11f,AuraTheme.muted),LinearLayout.LayoutParams(dp(52),-2))
            view.addView(text(java.text.DecimalFormat("0.#").format(row.getDouble("ram_mb"))+" MB",11f,AuraTheme.muted),LinearLayout.LayoutParams(dp(74),-2))
            return view
        }
    }

    private fun ipv4(value: String): InetAddress {
        val parts = value.split('.')
        require(parts.size==4 && parts.all { part -> part.toIntOrNull()?.let { it in 0..255 } == true }) { "IPv4 inválido" }
        return InetAddress.getByAddress(parts.map { it.toInt().toByte() }.toByteArray())
    }
    private fun macBytes(value: String): ByteArray {
        val normalized = value.replace(":", "").replace("-", "")
        require(normalized.matches(Regex("[0-9a-fA-F]{12}"))) { "MAC inválido" }
        val bytes = ByteArray(6) { normalized.substring(it*2,it*2+2).toInt(16).toByte() }
        require(bytes.any { it.toInt()!=0 } && (bytes[0].toInt() and 1) == 0) { "MAC inválido" }
        return bytes
    }
    @Suppress("DEPRECATION") // Keep the existing Wi-Fi-bound WOL behavior on API 26+.
    private fun wake() { work {
        val p = requireProfile()
        val mac = macBytes(p.getString("mac"))
        val packet = ByteArray(102) { if (it<6) 0xff.toByte() else mac[(it-6)%6] }
        val manager = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        val wifi = manager.allNetworks.firstOrNull { manager.getNetworkCapabilities(it)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)==true }
            ?: throw IllegalStateException("Conecte o celular ao Wi-Fi de casa.")
        DatagramSocket().use { socket ->
            wifi.bindSocket(socket)
            socket.broadcast = true
            socket.send(DatagramPacket(packet, packet.size, ipv4(p.getString("broadcast")), p.getInt("wolPort")))
        }
        "Sinal enviado pelo celular. Aguarde o PC iniciar e depois atualize o estado."
    } }

    private fun api(path: String, body: JSONObject? = null, target: JSONObject = requireProfile()): String {
        val p = target
        val expected = p.getString("fingerprint").lowercase()
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<out X509Certificate>?, type: String?) { throw CertificateException("Not a server") }
            override fun checkServerTrusted(chain: Array<out X509Certificate>?, type: String?) {
                val cert = chain?.firstOrNull() ?: throw CertificateException("Certificado ausente")
                cert.checkValidity()
                val hash = MessageDigest.getInstance("SHA-256").digest(cert.encoded).joinToString("") { "%02x".format(it.toInt() and 255) }
                if (!MessageDigest.isEqual(hash.toByteArray(), expected.toByteArray())) throw CertificateException("PC não corresponde ao código de conexão")
            }
        }
        val tls = SSLContext.getInstance("TLS").apply { init(null,arrayOf(trust),SecureRandom()) }
        val host = p.getString("host")
        val connection = URL("https://$host:${p.getInt("port")}/api/$path").openConnection() as HttpsURLConnection
        connection.sslSocketFactory = tls.socketFactory
        // Identity is the exact certificate copied from the local PC, not public DNS.
        connection.hostnameVerifier = HostnameVerifier { hostname, _ -> hostname == host }
        connection.instanceFollowRedirects = false
        connection.connectTimeout = 7000
        connection.readTimeout = 10000
        connection.setRequestProperty("Authorization", "Bearer " + p.getString("token"))
        try {
            if (body != null) {
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type","application/json")
                connection.setRequestProperty("X-Command-ID", UUID.randomUUID().toString())
                connection.doOutput = true
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if(code in 200..299) connection.inputStream else connection.errorStream
            val maxBytes = if(path.startsWith("process-icons/")) 24000 else if(path=="process-icons") 384000 else 2*1024*1024
            val responseBytes = stream?.use { it.readBytesBounded(maxBytes) } ?: ByteArray(0)
            val text = String(responseBytes, Charsets.UTF_8)
            if(code !in 200..299) throw IllegalStateException(try { JSONObject(text).optString("detail","Erro $code") } catch(_:Exception) { "Erro $code" })
            return text
        } finally { connection.disconnect() }
    }

    private fun java.io.InputStream.readBytesBounded(limit:Int):ByteArray {
        val output=java.io.ByteArrayOutputStream()
        val buffer=ByteArray(4096)
        while(true){val count=read(buffer);if(count<0)break;require(output.size()+count<=limit){"Resposta do PC excedeu o limite."};output.write(buffer,0,count)}
        return output.toByteArray()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey("aura-profile",null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder("aura-profile",KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }
    private fun encrypt(text: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE,key())
        val data = cipher.doFinal(text.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(cipher.iv,Base64.NO_WRAP) + ":" + Base64.encodeToString(data,Base64.NO_WRAP)
    }
    private fun decrypt(text: String): String {
        val parts = text.split(':')
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(parts[0],Base64.NO_WRAP)))
        return String(cipher.doFinal(Base64.decode(parts[1],Base64.NO_WRAP)),Charsets.UTF_8)
    }
    override fun onDestroy() { generation++; updateHandler.removeCallbacksAndMessages(null); updateExecutor.shutdownNow(); executor.shutdownNow(); iconExecutor.shutdownNow(); super.onDestroy() }
}
