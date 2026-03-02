"""
Station 2: JWT Validation & Core Access Control
Validates JWT tokens and enforces access policies for core communication.
"""
from __future__ import annotations

from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session

from auth import verify_jwt_with_intent
from models import Plugin
from config import (
    TRUST_MIN_SCORE_FOR_ACCESS,
    INTENT_PERMISSIONS,
    SCOPE_MIN_TRUST
)


class Station2AccessControl:
    """Handles JWT validation and access control decisions"""
    
    def validate_jwt_and_check_access(
        self,
        jwt_token: str,
        requested_method: str,
        requested_path: str,
        db: Session
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Main Station 2 logic: Validate JWT and check access policy.
        Returns: (access_granted, context, error_message)
        """
        # Step 1: Verify JWT signature and decode
        try:
            payload = verify_jwt_with_intent(jwt_token)
        except Exception as e:
            return False, {}, f"Invalid JWT: {str(e)}"
        
        # Step 2: Extract claims
        plugin_id = payload.get("sub")
        intent = payload.get("intent", "read")
        scope = payload.get("scope", "public")
        trust_score = payload.get("trust_score", 0.0)
        cert_serial = payload.get("cert_serial", "")
        
        if not plugin_id:
            return False, {}, "JWT missing plugin_id"
        
        # Step 3: Check if plugin exists in database
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            return False, {}, f"Plugin {plugin_id} not found in database"
        
        # Step 4: Check plugin status
        if plugin.status == "blocked":
            return False, {}, f"Plugin {plugin_id} is blocked"
        
        # Step 5: Check minimum trust score for scope
        min_trust = SCOPE_MIN_TRUST.get(scope, 80.0)
        if trust_score < min_trust:
            return False, {}, f"Trust score {trust_score} below minimum {min_trust} for scope {scope}"
        
        # Step 6: Check intent permissions for requested method
        allowed_methods = INTENT_PERMISSIONS.get(intent, [])
        if requested_method not in allowed_methods:
            return False, {}, f"Method {requested_method} not allowed for intent {intent}"
        
        # Step 7: Check path restrictions for restricted plugins
        if plugin.status == "restricted":
            if not self._is_path_allowed_for_restricted(requested_path):
                return False, {}, f"Restricted plugin cannot access {requested_path}"
        
        # Step 8: Grant access
        access_context = {
            "plugin_id": plugin_id,
            "intent": intent,
            "scope": scope,
            "trust_score": trust_score,
            "cert_serial": cert_serial,
            "allowed": True
        }
        
        return True, access_context, ""
    
    def _is_path_allowed_for_restricted(self, path: str) -> bool:
        """Check if path is allowed for restricted plugins"""
        restricted_deny_prefixes = [
            "/core/upload-folder",
            "/core/save",
            "/core/delete",
            "/core/reset",
            "/core/stop",
            "/core/start",
            "/core/docker",
        ]
        
        for prefix in restricted_deny_prefixes:
            if path.startswith(prefix):
                return False
        
        return True
    
    def extract_plugin_context_from_jwt(self, jwt_token: str) -> Optional[Dict[str, Any]]:
        """
        Extract plugin context from JWT without full validation.
        Useful for logging and tracking.
        """
        try:
            payload = verify_jwt_with_intent(jwt_token)
            return {
                "plugin_id": payload.get("sub"),
                "intent": payload.get("intent"),
                "scope": payload.get("scope"),
                "trust_score": payload.get("trust_score")
            }
        except Exception:
            return None


# Global instance
station2 = Station2AccessControl()
