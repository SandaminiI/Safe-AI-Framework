"""
Station 1: Certificate Verification & JWT Issuance
Verifies plugin certificates with CA and issues JWT tokens with intent-bound claims.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple, Dict, Any
import httpx
from sqlalchemy.orm import Session

from config import CA_SERVICE_URL, JWT_SECRET, JWT_ALG, JWT_TTL_SECONDS
from auth import issue_jwt_with_intent
from models import Plugin
from trust_engine import calculate_trust_score

UTC = timezone.utc


class Station1CertVerification:
    """Handles certificate verification and JWT issuance"""
    
    def __init__(self):
        self.ca_service_url = CA_SERVICE_URL
    
    async def verify_certificate_with_ca(self, cert_pem: str, plugin_id: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Verify certificate with CA Service.
        Returns: (is_valid, cert_details, error_message)
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.ca_service_url}/verify-cert",
                    json={
                        "certificate_pem": cert_pem,
                        "plugin_id": plugin_id
                    }
                )
                
                if response.status_code != 200:
                    return False, {}, f"CA service returned {response.status_code}"
                
                data = response.json()
                
                if not data.get("valid", False):
                    return False, {}, data.get("error", "Unknown error")
                
                return True, {
                    "plugin_id": data.get("plugin_id"),
                    "serial_number": data.get("serial_number")
                }, ""
        
        except httpx.TimeoutException:
            return False, {}, "CA service timeout"
        except Exception as e:
            return False, {}, f"CA verification failed: {str(e)}"
    
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
        Async version: Verify certificate with CA and issue JWT
        """
        # Step 1: Verify certificate with CA
        is_valid, cert_details, error = await self.verify_certificate_with_ca(
            certificate_pem,
            plugin_id
        )
        
        if not is_valid:
            return False, {}, f"Certificate verification failed: {error}"
        
        # Step 2: Get or create plugin in database
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
        
        # Step 3: Calculate trust score based on history
        trust_score = calculate_trust_score(db, plugin_id, plugin.trust_score)
        
        # Step 4: Update plugin trust score
        plugin.trust_score = trust_score
        plugin.declared_intent = intent
        db.commit()
        
        # Step 5: Issue JWT with intent-bound claims
        jwt_token = issue_jwt_with_intent(
            plugin_id=plugin_id,
            intent=intent,
            scope=scope,
            trust_score=trust_score,
            cert_serial=cert_details.get("serial_number", "")
        )
        
        return True, {
            "jwt_token": jwt_token,
            "trust_score": trust_score,
            "plugin_id": plugin_id,
            "expires_in": JWT_TTL_SECONDS,
            "next_station": "station2"
        }, ""


# Global instance
station1 = Station1CertVerification()
