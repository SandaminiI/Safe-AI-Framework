"""
Station 1: Certificate Verification & JWT Issuance

ARCHITECTURE:
- Certificate verification is done LOCALLY at Station 1 using CA's public key
- CA Service is only called to check revocation status
- JWT issuance happens here after successful verification

This follows proper PKI architecture where:
- CA issues certificates (offline/secure)
- Gateway verifies certificates locally (online/fast)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple, Dict, Any
import httpx
from cryptography import x509
from sqlalchemy.orm import Session

from config import CA_SERVICE_URL, JWT_SECRET, JWT_ALG, JWT_TTL_SECONDS, ROOT_CA_CACHE_PATH
from auth import issue_jwt_with_intent, verify_plugin_cert, load_root_ca_cert
from models import Plugin
from trust_engine import calculate_trust_score

UTC = timezone.utc


class Station1CertVerification:
    """
    Handles certificate verification and JWT issuance.
    
    Station 1 responsibilities:
    1. Verify certificate signature locally using CA's public key
    2. Check certificate validity (expiry, CN match)
    3. Check revocation status with CA service
    4. Issue intent-bound JWT to valid plugins
    """
    
    def __init__(self):
        self.ca_service_url = CA_SERVICE_URL
        self._root_ca_cert = None
    
    def _get_root_ca_cert(self) -> x509.Certificate:
        """Load and cache the root CA certificate"""
        if self._root_ca_cert is None:
            if ROOT_CA_CACHE_PATH.exists():
                self._root_ca_cert = load_root_ca_cert(ROOT_CA_CACHE_PATH)
            else:
                raise ValueError("Root CA certificate not found. Gateway not initialized.")
        return self._root_ca_cert
    
    def _extract_cert_details(self, cert_pem: str) -> Dict[str, Any]:
        """Extract details from certificate (serial number, plugin_id, etc.)"""
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        cn = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value
        serial_number = format(cert.serial_number, 'x')
        return {
            "plugin_id": cn,
            "serial_number": serial_number,
            "not_valid_after": cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after.replace(tzinfo=UTC)
        }
    
    def verify_certificate_locally(self, cert_pem: str, plugin_id: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Verify certificate LOCALLY using CA's public key.
        This is the correct approach - no need to call CA service for verification.
        
        Checks:
        1. Certificate signature (signed by CA)
        2. Certificate expiry
        3. CN matches plugin_id
        
        Returns: (is_valid, cert_details, error_message)
        """
        try:
            root_ca_cert = self._get_root_ca_cert()
            
            # Use existing verify_plugin_cert function from auth.py
            # This verifies: signature, expiry, issuer, CN match
            verify_plugin_cert(cert_pem, root_ca_cert, plugin_id)
            
            # Extract certificate details
            cert_details = self._extract_cert_details(cert_pem)
            
            print(f"[STATION 1] ✓ Certificate verified locally")
            print(f"[STATION 1] Plugin ID: {cert_details['plugin_id']}")
            print(f"[STATION 1] Serial: {cert_details['serial_number']}")
            
            return True, cert_details, ""
            
        except ValueError as e:
            print(f"[STATION 1] ✗ Certificate verification failed: {str(e)}")
            return False, {}, str(e)
        except Exception as e:
            print(f"[STATION 1] ✗ Certificate verification error: {str(e)}")
            return False, {}, f"Verification error: {str(e)}"
    
    async def check_revocation_with_ca(self, serial_number: str) -> Tuple[bool, str]:
        """
        Check if certificate is revoked by calling CA service.
        This is the ONLY thing we need to call CA for.
        
        Returns: (is_revoked, reason)
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.ca_service_url}/check-revocation/{serial_number}"
                )
                
                if response.status_code == 404:
                    # Certificate not found in revocation list = not revoked
                    return False, ""
                
                if response.status_code != 200:
                    # If CA is unreachable, we can choose to allow or deny
                    # For security, we'll allow but log warning
                    print(f"[STATION 1] ⚠ CA revocation check unavailable, proceeding with caution")
                    return False, ""
                
                data = response.json()
                return data.get("revoked", False), data.get("reason", "")
                
        except httpx.TimeoutException:
            print(f"[STATION 1] ⚠ CA revocation check timeout, proceeding with caution")
            return False, ""
        except Exception as e:
            print(f"[STATION 1] ⚠ CA revocation check error: {str(e)}")
            return False, ""
    
    def process_certificate_and_issue_jwt(
        self,
        plugin_id: str,
        certificate_pem: str,
        intent: str,
        scope: str,
        db: Session
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Main Station 1 logic: Verify certificate and issue JWT.
        Returns: (success, response_data, error_message)
        """
        # This will be called asynchronously from app.py
        # For now, return structure for sync version
        return False, {}, "Use async version"
    
    async def async_process_certificate_and_issue_jwt(
        self,
        plugin_id: str,
        certificate_pem: str,
        intent: str,
        scope: str,
        db: Session
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Async version: Verify certificate locally and issue JWT.
        
        Flow:
        1. Verify certificate LOCALLY (signature, expiry, CN match)
        2. Check revocation status with CA service
        3. Calculate trust score
        4. Issue intent-bound JWT
        """
        print(f"\n{'='*60}")
        print(f"[STATION 1] Processing certificate for plugin: {plugin_id}")
        print(f"[STATION 1] Requested intent: {intent}, scope: {scope}")
        print(f"{'='*60}")
        
        # Step 1: Verify certificate LOCALLY using CA's public key
        is_valid, cert_details, error = self.verify_certificate_locally(
            certificate_pem,
            plugin_id
        )
        
        if not is_valid:
            print(f"[STATION 1] ✗ Rejected: {error}")
            return False, {}, f"Certificate verification failed: {error}"
        
        # Step 2: Check revocation status with CA service
        is_revoked, revoke_reason = await self.check_revocation_with_ca(
            cert_details.get("serial_number", "")
        )
        
        if is_revoked:
            print(f"[STATION 1] ✗ Certificate revoked: {revoke_reason}")
            return False, {}, f"Certificate has been revoked: {revoke_reason}"
        
        print(f"[STATION 1] ✓ Certificate not revoked")
        
        # Step 3: Get or create plugin in database
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            # Create new plugin with initial trust score
            from config import INITIAL_TRUST_SCORE
            plugin = Plugin(
                plugin_id=plugin_id,
                name=plugin_id,
                role="plugin",
                declared_intent=intent,
                trust_score=INITIAL_TRUST_SCORE,
                status="active",
                service_base_url=""
            )
            db.add(plugin)
            db.commit()
            db.refresh(plugin)
            print(f"[STATION 1] New plugin registered: {plugin_id}")
        else:
            print(f"[STATION 1] Existing plugin: {plugin_id}")
        
        # Step 4: Calculate trust score based on history
        trust_score = calculate_trust_score(db, plugin_id, plugin.trust_score)
        
        # Step 5: Update plugin trust score
        plugin.trust_score = trust_score
        plugin.declared_intent = intent
        db.commit()
        
        print(f"[STATION 1] Trust score: {trust_score}")
        
        # Step 6: Issue JWT with intent-bound claims
        jwt_token = issue_jwt_with_intent(
            plugin_id=plugin_id,
            intent=intent,
            scope=scope,
            trust_score=trust_score,
            cert_serial=cert_details.get("serial_number", "")
        )
        
        print(f"[STATION 1] ✓ JWT issued successfully")
        print(f"[STATION 1] Next: Station 2 (Access Control)")
        print(f"{'='*60}\n")
        
        return True, {
            "jwt_token": jwt_token,
            "trust_score": trust_score,
            "plugin_id": plugin_id,
            "expires_in": JWT_TTL_SECONDS,
            "next_station": "station2"
        }, ""


# Global instance
station1 = Station1CertVerification()
