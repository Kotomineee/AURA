"""Private, per-user identity for the native AURA applications."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
from datetime import datetime, timedelta, timezone

DATA = Path(os.getenv('AURA_DATA_DIR', str(Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'AURA')))
PORT = 8765


def identity():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    DATA.mkdir(parents=True, exist_ok=True)
    mode_file = DATA / 'settings.env'
    if not mode_file.exists():
        mode_file.write_text('DRY_RUN=true\n', encoding='utf-8')
    config = DATA / 'identity.json'
    cert_path, key_path = DATA / 'server.crt', DATA / 'server.key'
    if not config.exists():
        config.write_text(json.dumps({'token': secrets.token_urlsafe(32)}), encoding='utf-8')
    if not cert_path.exists() or not key_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'AURA local')])
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                    x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    result = json.loads(config.read_text(encoding='utf-8'))
    result.update(cert=str(cert_path), key=str(key_path), fingerprint=cert.fingerprint(hashes.SHA256()).hex())
    return result


def pairing(host, mac, broadcast):
    ipaddress.IPv4Address(host)
    ipaddress.IPv4Address(broadcast)
    settings = identity()
    data = dict(version=1, name=socket.gethostname(), host=host, port=PORT,
                token=settings['token'], fingerprint=settings['fingerprint'], mac=mac,
                broadcast=broadcast, wolPort=9)
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
