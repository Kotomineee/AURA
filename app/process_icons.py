"""Bounded, private executable-icon cache. No client supplied filesystem paths."""
import base64
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import secrets
import struct
import threading
import time
import zlib
import xml.etree.ElementTree as ET

import psutil

SIZE = 32
LIMIT = 256
TTL = 300
_salt = secrets.token_bytes(32)
_lock = threading.Lock()
_cache = OrderedDict()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='aura-icons')


def _png(rgba):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    raw = b''.join(b'\0' + rgba[y*SIZE*4:(y+1)*SIZE*4] for y in range(SIZE))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', SIZE, SIZE, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def _package_icon(path):
    """Resolve MSIX identity assets when the package's executable has no PE icon.

    Only a manifest next to an already-verified process executable is inspected.
    No path ever comes from a request or leaves this module.
    """
    from PIL import Image
    executable = Path(path).resolve()
    for package in list(executable.parents)[:4]:
        manifest = package / 'AppxManifest.xml'
        try:
            if not manifest.is_file() or manifest.stat().st_size > 1024*1024:
                continue
            tree = ET.fromstring(manifest.read_bytes())
            for application in tree.iter():
                if application.tag.rsplit('}', 1)[-1] != 'Application':
                    continue
                candidate = application.get('Executable', '').replace('\\', '/')
                if not candidate or (package / candidate).resolve() != executable:
                    continue
                for visual in application:
                    if visual.tag.rsplit('}', 1)[-1] != 'VisualElements':
                        continue
                    asset = visual.get('Square44x44Logo') or visual.get('Square150x150Logo')
                    if not asset:
                        continue
                    logo = (package / asset.replace('\\', '/')).resolve()
                    if not logo.is_relative_to(package) or logo.suffix.lower() != '.png':
                        continue
                    # Prefer a transparent 32px target asset, then larger package variants.
                    variants = sorted(logo.parent.glob(logo.stem + '.*.png'),
                        key=lambda p: (0 if 'targetsize-32' in p.name else 1, 0 if 'altform-unplated' in p.name else 1, p.name))
                    for source in variants + [logo]:
                        if not source.resolve().is_relative_to(package) or not source.is_file() or source.stat().st_size > 1024*1024:
                            continue
                        with Image.open(source) as image:
                            if image.format != 'PNG' or max(image.size) > 2048:
                                continue
                            image = image.convert('RGBA')
                            image.thumbnail((SIZE, SIZE), Image.Resampling.LANCZOS)
                            tile = Image.new('RGBA', (SIZE, SIZE))
                            tile.paste(image, ((SIZE-image.width)//2, (SIZE-image.height)//2))
                            return base64.b64encode(_png(tile.tobytes())).decode('ascii')
        except (OSError, ValueError, ET.ParseError):
            continue
    return None


def _extract_pe(path):
    """Extract actual PE icon, rendering twice to preserve legacy mask transparency."""
    if os.name != 'nt':
        return None
    shell, user, gdi = C.WinDLL('shell32'), C.WinDLL('user32'), C.WinDLL('gdi32')
    shell.ExtractIconExW.argtypes = [W.LPCWSTR, C.c_int, C.POINTER(W.HICON), C.POINTER(W.HICON), W.UINT]
    shell.ExtractIconExW.restype = W.UINT
    user.DestroyIcon.argtypes = [W.HICON]
    user.DrawIconEx.argtypes = [W.HDC, C.c_int, C.c_int, W.HICON, C.c_int, C.c_int, W.UINT, W.HBRUSH, W.UINT]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateDIBSection.argtypes = [W.HDC, C.c_void_p, W.UINT, C.POINTER(C.c_void_p), W.HANDLE, W.DWORD]
    gdi.CreateDIBSection.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HANDLE]
    gdi.SelectObject.restype = W.HANDLE
    gdi.DeleteObject.argtypes = [W.HANDLE]
    gdi.DeleteDC.argtypes = [W.HDC]
    icon = W.HICON()
    if not shell.ExtractIconExW(path, 0, C.byref(icon), None, 1) or not icon:
        return None
    dc, bitmap, previous = None, None, None
    try:
        dc = gdi.CreateCompatibleDC(None)
        bits = C.c_void_p()
        header = C.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, SIZE, -SIZE, 1, 32, 0, SIZE*SIZE*4, 0, 0, 0, 0))
        bitmap = gdi.CreateDIBSection(dc, header, 0, C.byref(bits), None, 0)
        if not dc or not bitmap or not bits.value:
            return None
        previous = gdi.SelectObject(dc, bitmap)
        renders = []
        for background in (0, 255):
            C.memset(bits, background, SIZE*SIZE*4)
            if not user.DrawIconEx(dc, 0, 0, icon, SIZE, SIZE, 0, None, 3):
                return None
            gdi.GdiFlush()
            renders.append(C.string_at(bits, SIZE*SIZE*4))
        black, white = renders
        rgba = bytearray()
        for i in range(0, len(black), 4):
            alpha = 255 - max(0, min(255, white[i] - black[i]))
            rgba.extend([min(255, black[i+j]*255//alpha) if alpha else 0 for j in (2, 1, 0)] + [alpha])
        return base64.b64encode(_png(bytes(rgba))).decode('ascii')
    except (OSError, ValueError):
        return None
    finally:
        if previous:
            gdi.SelectObject(dc, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if dc:
            gdi.DeleteDC(dc)
        user.DestroyIcon(icon)


def _extract(path):
    # MSIX identity takes priority over a host executable's generic PE resource.
    # Traditional Win32 apps resolve directly to their executable's real icon.
    if os.name != 'nt':
        return None
    result = _package_icon(path)
    return result if result else _extract_pe(path)


def register(row):
    """Recheck process creation time before privately resolving its executable."""
    try:
        process = psutil.Process(row['pid'])
        if process.create_time() != row['created_at']:
            return None
        path = process.exe()
        stat = os.stat(path)
        key = hashlib.sha256(_salt + os.path.normcase(path).encode('utf-8') +
                             str((stat.st_mtime_ns, stat.st_size)).encode()).hexdigest()
    except (psutil.Error, OSError, KeyError):
        return None
    now = time.monotonic()
    with _lock:
        for old in list(_cache):
            if now - _cache[old][0] > TTL and _cache[old][1].done():
                del _cache[old]
        if key in _cache:
            future = _cache[key][1]
            # Keep successful icons alive while their process is listed. Failed
            # extractions must retain their expiry so a later refresh can retry.
            if future.done() and future.exception() is None and future.result():
                _cache[key] = (now, future)
            _cache.move_to_end(key)
            return key
        if len(_cache) >= LIMIT:
            victim = next((k for k, (_, f) in _cache.items() if f.done()), None)
            if victim is None:
                return None
            del _cache[victim]
        _cache[key] = (now, _pool.submit(_extract, path))
    return key


def lookup(key):
    with _lock:
        entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] > TTL:
        return {'state': 'unavailable', 'png': None}
    try:
        png = entry[1].result(timeout=0.2)
        return {'state': 'ready' if png else 'unavailable', 'png': png}
    except TimeoutError:
        return {'state': 'pending', 'png': None}
    except Exception:
        return {'state': 'unavailable', 'png': None}
