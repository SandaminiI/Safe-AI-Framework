"""
Policy Engine — Zero Trust Architecture
========================================

Responsible for access **decisions only**.  Trust scoring lives in trust_engine.

Decisions:
  - ALLOW           — proceed normally
  - RATE_LIMIT      — allow but throttle
  - TEMPORARY_BLOCK — deny this request; plugin can retry later
  - HARD_BLOCK      — deny and require re-onboarding / cert renewal

Inputs considered for every decision:
  1. Plugin trust_score
  2. Route risk level (LOW / MEDIUM / HIGH)
  3. Certificate validity
  4. Anomaly flag from trust engine

Route risk classification:
  LOW    — public / read-only routes (health, about, list, status)
  MEDIUM — normal operational API routes (plugin run, config)
  HIGH   — admin / core-mutation routes (upload, delete, docker, reset)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from config import (
    ACTIVE_THRESHOLD,
    RESTRICTED_THRESHOLD,
    ROUTE_RISK_HIGH_PREFIXES,
    ROUTE_RISK_MEDIUM_PREFIXES,
)
from models import Plugin

log = logging.getLogger("policy_engine")


# ──────────────────────────────────────────────────────────────────────────── #
#  Enums & result type                                                         #
# ──────────────────────────────────────────────────────────────────────────── #

class Decision(str, Enum):
    """Access-control decision returned by the policy engine."""
    ALLOW = "ALLOW"
    RATE_LIMIT = "RATE_LIMIT"
    TEMPORARY_BLOCK = "TEMPORARY_BLOCK"
    HARD_BLOCK = "HARD_BLOCK"


class RiskLevel(str, Enum):
    """Route risk classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class PolicyResult:
    """Immutable result of a policy evaluation."""
    decision: Decision
    risk_level: RiskLevel
    reason: str
    trust_score: float


# ──────────────────────────────────────────────────────────────────────────── #
#  Route classification                                                        #
# ──────────────────────────────────────────────────────────────────────────── #

def classify_route(path: str) -> RiskLevel:
    """
    Classify a request path into a risk level.

    HIGH:   admin / core-mutation routes (upload, delete, docker, reset, …)
    MEDIUM: normal operational API routes (plugin run, config, project, …)
    LOW:    everything else (health, about, list, status, public pages)
    """
    for prefix in ROUTE_RISK_HIGH_PREFIXES:
        if path.startswith(prefix):
            return RiskLevel.HIGH

    for prefix in ROUTE_RISK_MEDIUM_PREFIXES:
        if path.startswith(prefix):
            return RiskLevel.MEDIUM

    return RiskLevel.LOW


# ──────────────────────────────────────────────────────────────────────────── #
#  Main policy evaluation                                                      #
# ──────────────────────────────────────────────────────────────────────────── #

def evaluate(
    plugin: Plugin,
    path: str,
    method: str,
    *,
    cert_valid: bool = True,
    anomaly_flag: bool = False,
) -> PolicyResult:
    """
    Evaluate access policy for a single plugin request.

    Parameters
    ----------
    plugin : Plugin
        ORM object with at least ``trust_score`` and ``status``.
    path : str
        The request path.
    method : str
        The HTTP method (GET, POST, …).
    cert_valid : bool
        Whether the plugin's certificate is currently valid / not expired.
    anomaly_flag : bool
        Whether the trust engine has flagged this plugin as anomalous.

    Returns
    -------
    PolicyResult
        Contains ``decision``, ``risk_level``, ``reason``, ``trust_score``.
    """
    score = plugin.trust_score
    risk = classify_route(path)

    # ── Rule 1: Invalid certificate → immediate hard block ────────────── #
    if not cert_valid:
        result = PolicyResult(
            Decision.HARD_BLOCK, risk,
            "Invalid or expired certificate — immediate hard block",
            score,
        )
        _log_decision(plugin.plugin_id, result, path, method)
        return result

    # ── Rule 2: Plugin already hard-blocked by trust score ───────────── #
    if plugin.status == "blocked":
        result = PolicyResult(
            Decision.HARD_BLOCK, risk,
            "Plugin is hard-blocked (trust score below threshold)",
            score,
        )
        _log_decision(plugin.plugin_id, result, path, method)
        return result

    # ── Rule 3: Anomaly + high-risk route → temporary block ──────────── #
    if anomaly_flag and risk == RiskLevel.HIGH:
        result = PolicyResult(
            Decision.TEMPORARY_BLOCK, risk,
            "Anomaly detected — high-risk route temporarily blocked",
            score,
        )
        _log_decision(plugin.plugin_id, result, path, method)
        return result

    # ── Rule 4: Score-based decisions ────────────────────────────────── #
    if score >= ACTIVE_THRESHOLD:  # >= 70
        # Fully trusted — allow everything
        result = PolicyResult(
            Decision.ALLOW, risk,
            "Trusted plugin — full access granted",
            score,
        )

    elif score >= RESTRICTED_THRESHOLD:  # 40–69
        if risk == RiskLevel.HIGH:
            result = PolicyResult(
                Decision.TEMPORARY_BLOCK, risk,
                "Restricted trust — high-risk route temporarily blocked",
                score,
            )
        elif risk == RiskLevel.MEDIUM:
            result = PolicyResult(
                Decision.RATE_LIMIT, risk,
                "Restricted trust — medium-risk route rate-limited",
                score,
            )
        else:
            result = PolicyResult(
                Decision.ALLOW, risk,
                "Restricted trust — low-risk route allowed",
                score,
            )

    else:  # < 40
        if risk == RiskLevel.HIGH:
            result = PolicyResult(
                Decision.HARD_BLOCK, risk,
                "Low trust — high-risk route hard-blocked",
                score,
            )
        elif risk == RiskLevel.MEDIUM:
            result = PolicyResult(
                Decision.TEMPORARY_BLOCK, risk,
                "Low trust — medium-risk route temporarily blocked",
                score,
            )
        else:
            result = PolicyResult(
                Decision.RATE_LIMIT, risk,
                "Low trust — low-risk route rate-limited",
                score,
            )

    # ── Rule 5: Anomaly escalation ───────────────────────────────────── #
    if anomaly_flag:
        result = _escalate_for_anomaly(result)

    _log_decision(plugin.plugin_id, result, path, method)
    return result


# ──────────────────────────────────────────────────────────────────────────── #
#  Anomaly escalation helper                                                   #
# ──────────────────────────────────────────────────────────────────────────── #

def _escalate_for_anomaly(result: PolicyResult) -> PolicyResult:
    """Tighten the decision by one level when an anomaly is active."""
    if result.decision == Decision.ALLOW:
        return PolicyResult(
            Decision.RATE_LIMIT, result.risk_level,
            f"{result.reason} (rate-limited due to anomaly)",
            result.trust_score,
        )
    if result.decision == Decision.RATE_LIMIT:
        return PolicyResult(
            Decision.TEMPORARY_BLOCK, result.risk_level,
            f"{result.reason} (escalated due to anomaly)",
            result.trust_score,
        )
    # TEMPORARY_BLOCK and HARD_BLOCK stay as-is
    return result


# ──────────────────────────────────────────────────────────────────────────── #
#  Logging                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #

def _log_decision(
    plugin_id: str,
    result: PolicyResult,
    path: str,
    method: str,
) -> None:
    log.info(
        "[POLICY] plugin=%s decision=%s risk=%s score=%.1f path=%s method=%s | %s",
        plugin_id,
        result.decision.value,
        result.risk_level.value,
        result.trust_score,
        path,
        method,
        result.reason,
    )


# ──────────────────────────────────────────────────────────────────────────── #
#  Legacy-compatible wrapper                                                   #
# ──────────────────────────────────────────────────────────────────────────── #

def is_allowed(plugin: Plugin, path: str, method: str) -> tuple[bool, str]:
    """
    Backward-compatible shim.  Returns ``(allowed, reason)``.

    Maps ALLOW and RATE_LIMIT to ``True``, everything else to ``False``.
    """
    result = evaluate(
        plugin, path, method,
        cert_valid=True,
        anomaly_flag=getattr(plugin, "anomaly_flag", False),
    )
    allowed = result.decision in (Decision.ALLOW, Decision.RATE_LIMIT)
    return allowed, result.reason