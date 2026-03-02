"""
Trust Engine — Zero Trust Architecture
=======================================

Responsible for trust **scoring only**.  Policy decisions live in policy_engine.

Design Principles (from research proposal):
  1. Trust score starts at 100 for every plugin.
  2. Normal, valid requests NEVER reduce trust.
  3. Trust decreases ONLY for verified anomalies / violations:
       - Policy violations
       - High-frequency abnormal request rate
       - Invalid or expired certificate
       - Repeated access to sensitive routes while anomaly-flagged
       - Failed authentication attempts
  4. Passive recovery: +TRUST_RECOVERY_AMOUNT every
     TRUST_RECOVERY_INTERVAL_SECONDS of clean behaviour, capped at 100.
  5. Maintains per-plugin: last_request_at, request_frequency, anomaly_flag.
  6. Public entry point: evaluate_behavior(…)
  7. Rate-based anomaly detection: >N requests in T seconds -> anomaly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from config import (
    TRUST_MIN,
    TRUST_MAX,
    ACTIVE_THRESHOLD,
    RESTRICTED_THRESHOLD,
    TRUST_WINDOW_SECONDS,
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    TRUST_RECOVERY_INTERVAL_SECONDS,
    TRUST_RECOVERY_AMOUNT,
    TRUST_PENALTY_POLICY_VIOLATION,
    TRUST_PENALTY_RATE_ANOMALY,
    TRUST_PENALTY_INVALID_CERT,
    TRUST_PENALTY_SENSITIVE_ROUTE,
    TRUST_PENALTY_AUTH_FAILURE,
    SENSITIVE_ROUTE_PREFIXES,
)
from models import Plugin, RequestLog, TrustEvent

UTC = timezone.utc
log = logging.getLogger("trust_engine")


# ──────────────────────────────────────────────────────────────────────────── #
#  Internal helpers                                                            #
# ──────────────────────────────────────────────────────────────────────────── #

def _clamp(value: float, lo: float = TRUST_MIN, hi: float = TRUST_MAX) -> float:
    """Clamp *value* between *lo* and *hi*."""
    return max(lo, min(hi, value))


def _status_from_score(score: float) -> str:
    """Derive the plugin status string from a numeric trust score."""
    if score >= ACTIVE_THRESHOLD:
        return "active"
    if score >= RESTRICTED_THRESHOLD:
        return "restricted"
    return "blocked"


# ──────────────────────────────────────────────────────────────────────────── #
#  Trust event audit helper                                                    #
# ──────────────────────────────────────────────────────────────────────────── #

def _record_trust_event(
    db: Session,
    plugin_id: str,
    event_type: str,
    delta: float,
    score_before: float,
    score_after: float,
    detail: str = "",
) -> None:
    """Persist an immutable trust-score change record for auditing."""
    db.add(TrustEvent(
        plugin_id=plugin_id,
        event_type=event_type,
        delta=round(delta, 4),
        score_before=round(score_before, 4),
        score_after=round(score_after, 4),
        detail=detail[:500],
    ))


# ──────────────────────────────────────────────────────────────────────────── #
#  Passive trust recovery                                                      #
# ──────────────────────────────────────────────────────────────────────────── #

def _apply_trust_recovery(plugin: Plugin) -> float:
    """
    Award +TRUST_RECOVERY_AMOUNT for every TRUST_RECOVERY_INTERVAL_SECONDS
    elapsed since the last anomaly, up to TRUST_MAX.

    Recovery is suppressed while the anomaly flag is active.
    If the plugin has never had an anomaly, score stays as-is.
    """
    if plugin.anomaly_flag:
        return plugin.trust_score

    if plugin.last_anomaly_at is None:
        # Never penalised — trust is pristine; nothing to recover.
        return plugin.trust_score

    now = datetime.now(UTC)
    elapsed = (now - plugin.last_anomaly_at).total_seconds()
    intervals = int(elapsed / TRUST_RECOVERY_INTERVAL_SECONDS)
    if intervals <= 0:
        return plugin.trust_score

    recovery = intervals * TRUST_RECOVERY_AMOUNT
    return _clamp(plugin.trust_score + recovery)


# ──────────────────────────────────────────────────────────────────────────── #
#  Rate-based anomaly detection                                                #
# ──────────────────────────────────────────────────────────────────────────── #

def _detect_rate_anomaly(db: Session, plugin_id: str) -> bool:
    """
    Return True when the plugin has exceeded RATE_LIMIT_MAX_REQUESTS
    within the last RATE_LIMIT_WINDOW_SECONDS.
    """
    window_start = datetime.now(UTC) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    count = db.execute(
        select(func.count(RequestLog.id)).where(
            RequestLog.plugin_id == plugin_id,
            RequestLog.created_at >= window_start,
        )
    ).scalar_one()
    return count > RATE_LIMIT_MAX_REQUESTS


def _is_sensitive_route(path: str) -> bool:
    """Return True if *path* matches a sensitive / high-risk route prefix."""
    return any(path.startswith(pfx) for pfx in SENSITIVE_ROUTE_PREFIXES)


# ──────────────────────────────────────────────────────────────────────────── #
#  PUBLIC API — evaluate_behavior                                              #
# ──────────────────────────────────────────────────────────────────────────── #

def evaluate_behavior(
    db: Session,
    plugin_id: str,
    route: str,
    request_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Central behavioural evaluation — called on every proxied request.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    plugin_id : str
        The plugin whose behaviour is being evaluated.
    route : str
        The request path (e.g. ``/core/plugins/run``).
    request_metadata : dict
        Keys consumed:
        - ``method``           (str)  — HTTP verb
        - ``status_code``      (int)  — response status code
        - ``latency_ms``       (float)
        - ``error_flag``       (bool) — True when status_code >= 400
        - ``cert_valid``       (bool) — False -> invalid/expired certificate
        - ``auth_failed``      (bool) — True -> authentication failure
        - ``policy_violation`` (bool) — True -> policy engine denied the request

    Returns
    -------
    dict with ``trust_score``, ``status``, ``anomaly``, ``detail``.
    """
    plugin = db.get(Plugin, plugin_id)
    if plugin is None:
        log.warning("[TRUST] evaluate_behavior called for unknown plugin=%s", plugin_id)
        return {
            "trust_score": 0.0,
            "status": "blocked",
            "anomaly": True,
            "detail": "Unknown plugin",
        }

    now = datetime.now(UTC)
    score_before = plugin.trust_score
    delta = 0.0
    reasons: List[str] = []

    # ── 1. Apply passive trust recovery ──────────────────────────────── #
    recovered = _apply_trust_recovery(plugin)
    if recovered > plugin.trust_score:
        rec_delta = recovered - plugin.trust_score
        _record_trust_event(
            db, plugin_id, "recovery", rec_delta,
            plugin.trust_score, recovered, "Passive trust recovery",
        )
        plugin.trust_score = recovered
        score_before = recovered

    # ── 2. Book-keeping ──────────────────────────────────────────────── #
    plugin.last_request_at = now
    plugin.request_frequency = (plugin.request_frequency or 0) + 1

    # ── 3. Invalid / expired certificate ─────────────────────────────── #
    if request_metadata.get("cert_valid") is False:
        penalty = TRUST_PENALTY_INVALID_CERT
        delta -= penalty
        reasons.append(f"Invalid/expired certificate (-{penalty})")

    # ── 4. Failed authentication ─────────────────────────────────────── #
    if request_metadata.get("auth_failed"):
        penalty = TRUST_PENALTY_AUTH_FAILURE
        delta -= penalty
        reasons.append(f"Authentication failure (-{penalty})")

    # ── 5. Rate-based anomaly detection ──────────────────────────────── #
    if _detect_rate_anomaly(db, plugin_id):
        penalty = TRUST_PENALTY_RATE_ANOMALY
        delta -= penalty
        reasons.append(
            f"Rate anomaly: >{RATE_LIMIT_MAX_REQUESTS} reqs "
            f"in {RATE_LIMIT_WINDOW_SECONDS}s (-{penalty})"
        )
        plugin.anomaly_flag = True
        plugin.last_anomaly_at = now
    else:
        # Auto-clear anomaly after a full cooldown window of normal traffic
        if plugin.anomaly_flag and plugin.last_anomaly_at:
            cooldown_elapsed = (now - plugin.last_anomaly_at).total_seconds()
            if cooldown_elapsed > RATE_LIMIT_WINDOW_SECONDS:
                plugin.anomaly_flag = False
                log.info("[TRUST] plugin=%s anomaly flag cleared after cooldown", plugin_id)

    # ── 6. Sensitive-route abuse ─────────────────────────────────────── #
    if _is_sensitive_route(route):
        error_flag = request_metadata.get("error_flag", False)
        if plugin.anomaly_flag or error_flag:
            penalty = TRUST_PENALTY_SENSITIVE_ROUTE
            delta -= penalty
            reasons.append(f"Sensitive route access while anomaly/error (-{penalty})")

    # ── 7. Policy violation (signalled by policy engine) ─────────────── #
    if request_metadata.get("policy_violation"):
        penalty = TRUST_PENALTY_POLICY_VIOLATION
        delta -= penalty
        reasons.append(f"Policy violation (-{penalty})")
        plugin.anomaly_flag = True
        plugin.last_anomaly_at = now

    # ── 8. Apply accumulated delta ───────────────────────────────────── #
    if delta != 0.0:
        new_score = _clamp(plugin.trust_score + delta)
        _record_trust_event(
            db, plugin_id, "penalty", delta,
            plugin.trust_score, new_score,
            "; ".join(reasons),
        )
        plugin.trust_score = new_score
        if delta < 0.0:
            plugin.last_anomaly_at = now

    plugin.status = _status_from_score(plugin.trust_score)
    db.commit()

    log.info(
        "[TRUST] plugin=%s score=%.1f->%.1f delta=%.1f status=%s anomaly=%s | %s",
        plugin_id,
        score_before,
        plugin.trust_score,
        delta,
        plugin.status,
        plugin.anomaly_flag,
        " | ".join(reasons) if reasons else "clean",
    )

    return {
        "trust_score": plugin.trust_score,
        "status": plugin.status,
        "anomaly": plugin.anomaly_flag,
        "detail": "; ".join(reasons) if reasons else "Normal behaviour — no penalty",
    }


# ──────────────────────────────────────────────────────────────────────────── #
#  Station 1 helper — lightweight scoring for JWT issuance                     #
# ──────────────────────────────────────────────────────────────────────────── #

def calculate_trust_score(db: Session, plugin_id: str, current_score: float) -> float:
    """
    Lightweight trust calculation used by Station 1 during JWT issuance.

    Applies passive recovery only — penalties are applied later during
    actual request evaluation via ``evaluate_behavior``.
    """
    plugin = db.get(Plugin, plugin_id)
    if plugin is None:
        return current_score
    return _apply_trust_recovery(plugin)


# ──────────────────────────────────────────────────────────────────────────── #
#  Legacy-compatible wrapper                                                   #
# ──────────────────────────────────────────────────────────────────────────── #

def update_plugin_trust(db: Session, plugin_id: str) -> Optional[Plugin]:
    """
    Backward-compatible entry point called after proxy requests in app.py.

    Applies **recovery only** — no penalty is assessed without explicit
    request metadata.  Callers should migrate to ``evaluate_behavior()``.
    """
    plugin = db.get(Plugin, plugin_id)
    if plugin is None:
        return None

    recovered = _apply_trust_recovery(plugin)
    if recovered != plugin.trust_score:
        _record_trust_event(
            db, plugin_id, "recovery",
            recovered - plugin.trust_score,
            plugin.trust_score, recovered,
            "Periodic recovery via update_plugin_trust",
        )
        plugin.trust_score = recovered

    plugin.status = _status_from_score(plugin.trust_score)
    db.commit()
    return plugin


# ──────────────────────────────────────────────────────────────────────────── #
#  Read-only status query                                                      #
# ──────────────────────────────────────────────────────────────────────────── #

def get_trust_status(db: Session, plugin_id: str) -> Dict[str, Any]:
    """Return current trust state for a plugin (read-only query)."""
    plugin = db.get(Plugin, plugin_id)
    if plugin is None:
        return {"error": "Plugin not found"}
    return {
        "plugin_id": plugin_id,
        "trust_score": plugin.trust_score,
        "status": plugin.status,
        "anomaly_flag": plugin.anomaly_flag,
        "last_request_at": (
            plugin.last_request_at.isoformat() if plugin.last_request_at else None
        ),
        "last_anomaly_at": (
            plugin.last_anomaly_at.isoformat() if plugin.last_anomaly_at else None
        ),
        "request_frequency": plugin.request_frequency,
    }