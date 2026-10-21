package io.aura.personal

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import java.io.FileNotFoundException

/** A read-only URI for one private APK; never accepts a filesystem path. */
class UpdateApkProvider:ContentProvider(){
    override fun onCreate()=true
    private fun allowed(uri:Uri):Boolean=uri==UpdateInstaller.uri(requireNotNull(context))
    override fun getType(uri:Uri):String?=if(allowed(uri))"application/vnd.android.package-archive" else null
    override fun openFile(uri:Uri,mode:String):ParcelFileDescriptor {
        if(!allowed(uri) || mode!="r")throw FileNotFoundException("Arquivo indisponível")
        return ParcelFileDescriptor.open(UpdateInstaller.file(requireNotNull(context)),ParcelFileDescriptor.MODE_READ_ONLY)
    }
    override fun query(uri:Uri,projection:Array<out String>?,selection:String?,selectionArgs:Array<out String>?,sortOrder:String?):Cursor? {
        if(!allowed(uri))return null
        val file=UpdateInstaller.file(requireNotNull(context))
        val columns=(projection?:arrayOf(OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE)).filter{it==OpenableColumns.DISPLAY_NAME || it==OpenableColumns.SIZE}.toTypedArray()
        return MatrixCursor(columns).apply{addRow(columns.map{if(it==OpenableColumns.DISPLAY_NAME)"AURA-update.apk" else file.length()}.toTypedArray())}
    }
    override fun insert(uri:Uri,values:ContentValues?):Uri?=throw UnsupportedOperationException()
    override fun delete(uri:Uri,selection:String?,selectionArgs:Array<out String>?):Int=throw UnsupportedOperationException()
    override fun update(uri:Uri,values:ContentValues?,selection:String?,selectionArgs:Array<out String>?):Int=throw UnsupportedOperationException()
}
