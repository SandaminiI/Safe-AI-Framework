"""
Station 2: JWT Validation & Core Access Control
=================================================
Validates JWT tokens and enforces access policies for core communication.

Integrates with:
  - policy_engine.evaluate()  for route-risk-aware access decisions
  - trust_engine.evaluate_behavior() for recording auth failures
"""
from __future__ import annotations

import logging
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session

from auth import verify_jwt_with_intent
from models import Plugin
from config import (
    TRUST_MIN_SCORE_FOR_ACCESS,
    INTENT_PERMISSIONS,
    SCOPE_MIN_TRUST,
)
from policy_engine import evaluate as policy_evaluate, Decision
from trust_engine import evaluate_behavior

log = logging.getLogger("station2")


class Station2AccessControl:
    """Handles JWT validation and access control decisions."""

    def validate_jwt_and_check_access(
        self,
        jwt_token: str,
        requested_method: str,
        requested_path: str,
        db: Session,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Main Station 2 logic: Validate JWT and check access policy.

        Every denial is fed back into the trust engine via
        ``evaluate_behavior`` so that repeated failures continuously
        degrade the plugin's trust score.

        Returns: (access_granted, context, error_message)
        """
        # Step 1: Verify JWT signature and decode
        try:
            payload = verify_jwt_with_intent(jwt_token)
        except Exception as e:
            # JWT invalid / expired — feed auth failure into trust engine
            # Try to extract plugin_id from the raw token for attribution
            pid = self._safe_extract_plugin_id(jwt_token)
            if pid:
                evaluate_behavior(db, pid, requested_path, {
                    "method": requested_method, "status_code": 401, "latency_ms": 0,
                    "error_flag": True, "cert_valid": True,
                    "auth_failed": True, "policy_violation": False,
                })
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

        # Step 3b: Revoked plugins must re-authenticate via Station 1
        if plugin.status == "revoked":
            evaluate_behavior(db, plugin_id, requested_path, {
                "method": requested_method, "status_code": 403, "latency_ms": 0,
                "error_flag": True, "cert_valid": True,
                "auth_failed": True, "policy_violation": True,
            })
            return (
                False, {},
                f"Plugin {plugin_id} is REVOKED — full re-authentication via Station 1 required"
            )

        # Step 4: Use LIVE trust score from DB (not the JWT snapshot)
        live_trust = plugin.trust_score

        # Step 5: Run policy engine evaluation (considers trust, risk, anomaly)
        policy_result = policy_evaluate(
            plugin,
            requested_path,
            requested_method,
            cert_valid=True,  # cert was verified at Station 1
            anomaly_flag=plugin.anomaly_flag,
        )

        if policy_result.decision in (Decision.HARD_BLOCK, Decision.TEMPORARY_BLOCK):
            # Feed policy denial into trust engine for continuous degradation
            evaluate_behavior(db, plugin_id, requested_path, {
                "method": requested_method, "status_code": 403, "latency_ms": 0,
                "error_flag": True, "cert_valid": True,
                "auth_failed": False, "policy_violation": True,
            })
            log.warning(
                "[STATION 2] DENIED plugin=%s decision=%s reason=%s",
                plugin_id, policy_result.decision.value, policy_result.reason,
            )
            return False, {}, policy_result.reason

        # Step 6: Check minimum trust score for scope
        min_trust = SCOPE_MIN_TRUST.get(scope, 80.0)
        if live_trust < min_trust:
            # Feed scope-trust failure into trust engine
            evaluate_behavior(db, plugin_id, requested_path, {
                "method": requested_method, "status_code": 403, "latency_ms": 0,
                "error_flag": True, "cert_valid": True,
                "auth_failed": True, "policy_violation": False,
            })
            return (
                False, {},
                f"Trust score {live_trust:.1f} below minimum {min_trust} for scope '{scope}'"
            )

        # Step 7: Check intent permissions for requested method
        allowed_methods = INTENT_PERMISSIONS.get(intent, [])
        if requested_method not in allowed_methods:
            # Feed intent permission denial into trust engine
            evaluate_behavior(db, plugin_id, requested_path, {
                "method": requested_method, "status_code": 403, "latency_ms": 0,
                "error_flag": True, "cert_valid": True,
                "auth_failed": False, "policy_violation": True,
            })
            return (
                False, {},
                f"Method {requested_method} not allowed for intent '{intent}'"
            )

        # Step 8: Grant access
        access_context = {
            "plugin_id": plugin_id,
            "intent": intent,
            "scope": scope,
            "trust_score": live_trust,
            "cert_serial": cert_serial,
            "policy_decision": policy_result.decision.value,
            "risk_level": policy_result.risk_level.value,
            "allowed": True,
        }

        log.info(
            "[STATION 2] GRANTED plugin=%s decision=%s risk=%s trust=%.1f",
            plugin_id, policy_result.decision.value,
            policy_result.risk_level.value, live_trust,
        )
        return True, access_context, ""

    def extract_plugin_context_from_jwt(
        self, jwt_token: str,
    ) -> Optional[Dict[str, Any]]:
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
                "trust_score": payload.get("trust_score"),
            }
        except Exception:
            return None

    @staticmethod
    def _safe_extract_plugin_id(jwt_token: str) -> Optional[str]:
        """
        Best-effort extraction of plugin_id from a JWT that may be
        expired or malformed.  Used for attributing auth failures.
        """
        try:
            import jwt as _jwt
            from config import JWT_SECRET, JWT_ALG
            payload = _jwt.decode(
                jwt_token, JWT_SECRET, algorithms=[JWT_ALG],
                options={"verify_exp": False},
            )
            return payload.get("sub")
        except Exception:
            return None


# Global instance
station2 = Station2AccessControl()
