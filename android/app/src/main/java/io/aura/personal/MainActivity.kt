package io.aura.personal

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.text.InputType
import android.util.Base64
import android.view.View
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
    private lateinit var content: LinearLayout
    private lateinit var status: TextView
    private lateinit var summary: TextView
    private lateinit var detail: TextView
    private val executor = Executors.newSingleThreadExecutor()
    private var profile: JSONObject? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(16,24,39)
        window.navigationBarColor = Color.rgb(16,24,39)
        val scroll = ScrollView(this)
        content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32,48,32,48)
            setBackgroundColor(Color.rgb(16,24,39))
        }
        scroll.addView(content)
        setContentView(scroll)
        scroll.setOnApplyWindowInsetsListener { view, insets ->
            view.setPadding(0, insets.systemWindowInsetTop, 0, insets.systemWindowInsetBottom)
            insets
        }
        label("AURA", 32f)
        label("Seu computador, conectado ao seu celular", 16f)
        summary = label("Nenhum PC conectado", 18f)
        status = label("Conecte o PC para começar.", 14f)
        button("Conectar PC") { importProfile() }
        button("Atualizar estado") { refresh() }
        button("Ligar PC • Wake-on-LAN") { wake() }
        button("Desligar PC") {
            confirm("Desligar o PC? Salve seus arquivos antes.") { command("power", JSONObject().put("action","shutdown").put("confirm",true)) }
        }
        button("Reiniciar PC") { command("power", JSONObject().put("action","restart")) }
        button("Agendar desligamento") { schedule() }
        button("Cancelar agendamento") { command("shutdown/cancel", JSONObject()) }
        button("Processos") { processes() }
        button("Histórico") { work {
            val lines = JSONObject(api("logs")).getJSONArray("lines")
            val text = (0 until lines.length()).joinToString("\n") { lines.getString(it) }
            runOnUiThread { detail.text = text.ifEmpty { "Nenhum evento registrado." } }
            "Histórico atualizado."
        } }
        button("Esquecer PC") {
            confirm("Remover a conexão salva neste celular?") {
                getSharedPreferences("aura", Context.MODE_PRIVATE).edit().clear().apply()
                profile = null
                summary.text = "Nenhum PC conectado"
                detail.text = ""
                status.text = "Conexão removida deste celular."
            }
        }
        detail = label("O botão Ligar PC envia o sinal pelo Wi-Fi deste celular. As demais ações precisam do agente Windows ligado.", 14f)
        try {
            val saved = getSharedPreferences("aura", MODE_PRIVATE).getString("profile", null)
            if (saved != null) {
                profile = JSONObject(decrypt(saved))
                summary.text = "PC salvo: " + profile!!.getString("name")
                status.text = "Estado ainda não consultado."
            }
        } catch (_: Exception) { status.text = "Conexão salva indisponível. Conecte o PC novamente." }
    }

    private fun label(text: String, size: Float): TextView = TextView(this).apply {
        this.text = text; textSize = size; setTextColor(Color.rgb(230,237,248)); setPadding(0,12,0,12)
        content.addView(this)
    }
    private fun button(text: String, action: () -> Unit) {
        content.addView(Button(this).apply { this.text = text; isAllCaps = false; setOnClickListener { action() } })
    }
    private fun confirm(text: String, action: () -> Unit) {
        AlertDialog.Builder(this).setTitle("AURA").setMessage(text)
            .setNegativeButton("Cancelar", null).setPositiveButton("Confirmar") { _, _ -> action() }.show()
    }
    private fun work(action: () -> String) {
        status.text = "Executando…"
        executor.execute {
            try { val result = action(); runOnUiThread { status.text = result } }
            catch (e: Exception) { runOnUiThread { status.text = "Não foi possível concluir: " + (e.message ?: "falha de conexão") } }
        }
    }
    private fun requireProfile(): JSONObject = profile ?: throw IllegalStateException("Conecte o PC primeiro.")
    private fun importProfile() {
        val input = EditText(this).apply { hint = "Cole o código gerado na AURA do Windows"; minLines = 3; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE }
        AlertDialog.Builder(this).setTitle("Conectar PC").setView(input)
            .setNegativeButton("Cancelar", null).setPositiveButton("Salvar") { _, _ ->
                try {
                    val text = String(Base64.decode(input.text.toString().filterNot { it.isWhitespace() }, Base64.URL_SAFE), Charsets.UTF_8)
                    val p = JSONObject(text)
                    require(p.getInt("version") == 1) { "Formato incompatível" }
                    ipv4(p.getString("host")); ipv4(p.getString("broadcast"))
                    require(p.getInt("port") in 1..65535 && p.getInt("wolPort") in 1..65535)
                    require(p.getString("token").length >= 32)
                    require(p.getString("fingerprint").matches(Regex("[0-9a-fA-F]{64}")))
                    macBytes(p.getString("mac"))
                    getSharedPreferences("aura", MODE_PRIVATE).edit().putString("profile", encrypt(text)).apply()
                    profile = p
                    summary.text = p.getString("name") + " • " + p.getString("host")
                    status.text = "Conexão salva. Use Atualizar estado ou Ligar PC."
                } catch (_: Exception) { status.text = "Código inválido. Gere novamente no aplicativo Windows, selecionando a placa Ethernet." }
            }.show()
    }
    private fun refresh() { work {
        val s = JSONObject(api("status"))
        val mode = if (s.getBoolean("dry_run")) "SIMULAÇÃO" else "MODO REAL"
        val schedule = if (s.isNull("shutdown_at")) "Nenhum desligamento agendado." else
            "Desligamento: " + java.text.DateFormat.getDateTimeInstance().format(java.util.Date((s.getDouble("shutdown_at")*1000).toLong()))
        runOnUiThread {
            summary.text = s.getString("hostname") + " • CPU " + s.get("cpu") + "% • RAM " + s.get("ram") + "%\n" + mode
            detail.text = schedule
        }
        "Conectado ao PC."
    } }
    private fun command(path: String, body: JSONObject) { work { JSONObject(api(path, body)).getString("message") } }
    private fun schedule() {
        val input = EditText(this).apply { inputType = InputType.TYPE_CLASS_NUMBER; setText("30") }
        AlertDialog.Builder(this).setTitle("Desligar em quantos minutos?").setView(input)
            .setNegativeButton("Cancelar",null).setPositiveButton("Confirmar agendamento") { _, _ ->
                val minutes = input.text.toString().toIntOrNull()
                if (minutes == null || minutes !in 1..10080) status.text = "Informe de 1 a 10080 minutos."
                else command("shutdown", JSONObject().put("confirm",true).put("delay_seconds",minutes*60))
            }.show()
    }
    private fun processes() { work {
        val rows = JSONArray(api("processes"))
        val labels = Array(rows.length()) { i -> val r=rows.getJSONObject(i); "${r.getString("name")} • PID ${r.getInt("pid")} • ${r.get("ram_mb")} MB" }
        runOnUiThread {
            AlertDialog.Builder(this).setTitle("Processos • toque para selecionar")
                .setItems(labels) { _, index ->
                    val r = rows.getJSONObject(index)
                    AlertDialog.Builder(this).setTitle(r.getString("name"))
                        .setMessage("PID ${r.getInt("pid")}. Alterações não salvas podem ser perdidas.")
                        .setNegativeButton("Voltar",null).setPositiveButton("Encerrar processo") { _, _ -> command("processes/terminate",r) }.show()
                }.setNegativeButton("Fechar",null).show()
        }
        if (rows.length()==0) "Nenhum processo elegível." else "Selecione o alvo pelo nome e PID."
    } }

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

    private fun api(path: String, body: JSONObject? = null): String {
        val p = requireProfile()
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
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if(code !in 200..299) throw IllegalStateException(try { JSONObject(text).optString("detail","Erro $code") } catch(_:Exception) { "Erro $code" })
            return text
        } finally { connection.disconnect() }
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
    override fun onDestroy() { executor.shutdownNow(); super.onDestroy() }
}
