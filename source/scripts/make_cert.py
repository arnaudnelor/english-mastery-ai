"""Create a self-signed HTTPS certificate and a LAN PIN for start-lan.bat.

Phones only allow the microphone on HTTPS pages, so LAN mode needs a certificate.
Prints three lines for the batch file: PIN, comma-separated LAN IPs, data dir.
"""
import datetime
import ipaddress
import os
import secrets
import socket
import sys
from pathlib import Path


def lan_ips() -> list[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def main():
    data = Path(os.environ.get("APPDATA", Path.home())) / "EnglishMasteryAI"
    data.mkdir(parents=True, exist_ok=True)
    pin_file = data / "lan_pin.txt"
    if not pin_file.exists():
        pin_file.write_text(f"{secrets.randbelow(10**6):06d}", encoding="utf-8")
    pin = pin_file.read_text(encoding="utf-8").strip()

    ips = lan_ips()
    cert, key = data / "lan_cert.pem", data / "lan_key.pem"
    ip_stamp = data / "lan_cert_ips.txt"
    stamp = ip_stamp.read_text() if ip_stamp.exists() else None
    if not cert.exists() or stamp != ",".join(ips):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "English Mastery AI (local)")])
        san = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname()), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        san += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]
        now = datetime.datetime.now(datetime.timezone.utc)
        c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
             .not_valid_after(now + datetime.timedelta(days=825))
             .add_extension(x509.SubjectAlternativeName(san), critical=False).sign(k, hashes.SHA256()))
        cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
        key.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                        serialization.NoEncryption()))
        ip_stamp.write_text(",".join(ips))
    print(pin)
    print(",".join(ips) or "none")
    print(data)


if __name__ == "__main__":
    sys.exit(main())
