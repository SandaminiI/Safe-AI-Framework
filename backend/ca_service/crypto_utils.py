from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

UTC = timezone.utc


@dataclass
class RootCA:
    key_pem: str
    cert_pem: str


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_or_create_root_ca(keys_dir: Path) -> RootCA:
    key_path = keys_dir / "root_ca_key.pem"
    cert_path = keys_dir / "root_ca_cert.pem"

    if key_path.exists() and cert_path.exists():
        return RootCA(key_pem=_read_text(key_path), cert_pem=_read_text(cert_path))

    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "LK"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Vibe Secure AI Framework"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Vibe Root CA"),
        ]
    )

    now = datetime.now(UTC)
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=365 * 5))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key=root_key, algorithm=hashes.SHA256())
    )

    key_pem = root_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    cert_pem = root_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    _write_text(key_path, key_pem)
    _write_text(cert_path, cert_pem)

    return RootCA(key_pem=key_pem, cert_pem=cert_pem)


def issue_plugin_cert(
    root_key_pem: str,
    root_cert_pem: str,
    plugin_id: str,
    ttl_hours: int = 3,
) -> Tuple[str, str, str, str]:
    root_key = serialization.load_pem_private_key(root_key_pem.encode("utf-8"), password=None)
    root_cert = x509.load_pem_x509_certificate(root_cert_pem.encode("utf-8"))

    plugin_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Vibe Secure AI Framework"),
            x509.NameAttribute(NameOID.COMMON_NAME, plugin_id),
        ]
    )

    now = datetime.now(UTC)
    expires = now + timedelta(hours=ttl_hours)

    serial = x509.random_serial_number()

    plugin_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(root_cert.subject)
        .public_key(plugin_key.public_key())
        .serial_number(serial)
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(expires)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(plugin_id)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key=root_key, algorithm=hashes.SHA256())
    )

    plugin_key_pem = plugin_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    plugin_cert_pem = plugin_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    return plugin_key_pem, plugin_cert_pem, expires.isoformat(), str(serial)


def verify_certificate(
    cert_pem: str,
    root_ca_cert_pem: str,
    expected_plugin_id: Optional[str] = None
) -> Tuple[bool, Any]:
    """
    Verify a certificate against the root CA.
    Returns (True, details_dict) on success or (False, error_message) on failure.
    """
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        root_ca_cert = x509.load_pem_x509_certificate(root_ca_cert_pem.encode("utf-8"))
        
        # Extract plugin_id from CN
        cn_attr = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if not cn_attr:
            return False, "Certificate missing CN"
        
        plugin_id = cn_attr[0].value
        
        # Check if plugin_id matches expected (if provided)
        if expected_plugin_id and plugin_id != expected_plugin_id:
            return False, f"Plugin ID mismatch: expected {expected_plugin_id}, got {plugin_id}"
        
        # Check expiration
        now = datetime.now(UTC)
        if now < cert.not_valid_before.replace(tzinfo=UTC):
            return False, "Certificate not yet valid"
        if now > cert.not_valid_after.replace(tzinfo=UTC):
            return False, "Certificate expired"
        
        # Check issuer matches root CA subject
        if cert.issuer != root_ca_cert.subject:
            return False, "Certificate issuer mismatch"
        
        # Verify signature
        try:
            from cryptography.hazmat.primitives.asymmetric import padding
            root_ca_cert.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
        except Exception as e:
            return False, f"Signature verification failed: {str(e)}"
        
        # Check if revoked (this would be called separately in app.py)
        serial_number = str(cert.serial_number)
        
        return True, {
            "plugin_id": plugin_id,
            "serial_number": serial_number,
            "expires_at": cert.not_valid_after.isoformat()
        }
    
    except Exception as e:
        return False, f"Certificate verification error: {str(e)}"


def is_certificate_revoked(serial_number: str, crl_path: Path) -> bool:
    """Check if a certificate is in the CRL"""
    if not crl_path.exists():
        return False
    
    try:
        with open(crl_path, "r") as f:
            crl = json.load(f)
        
        return any(entry["serial_number"] == serial_number for entry in crl)
    except Exception:
        return False


def revoke_certificate_in_crl(serial_number: str, crl_path: Path, reason: str = "unspecified") -> Tuple[bool, str]:
    """Add a certificate to the CRL"""
    try:
        # Load existing CRL
        if crl_path.exists():
            with open(crl_path, "r") as f:
                crl = json.load(f)
        else:
            crl = []
        
        # Check if already revoked
        if any(entry["serial_number"] == serial_number for entry in crl):
            return False, "Certificate already revoked"
        
        # Add to CRL
        crl.append({
            "serial_number": serial_number,
            "revoked_at": datetime.now(UTC).isoformat(),
            "reason": reason
        })
        
        # Save CRL
        crl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(crl_path, "w") as f:
            json.dump(crl, f, indent=2)
        
        return True, "Certificate revoked successfully"
    
    except Exception as e:
        return False, f"Failed to revoke certificate: {str(e)}"