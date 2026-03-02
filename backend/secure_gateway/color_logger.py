"""
Colorful terminal logging utilities for Secure Gateway
"""
from colorama import Fore, Back, Style, init

# Initialize colorama for Windows compatibility
init(autoreset=True)


class ColorLogger:
    """Provides colorful logging methods for terminal output"""
    
    # Color constants
    SUCCESS = Fore.GREEN
    ERROR = Fore.RED
    WARNING = Fore.YELLOW
    INFO = Fore.CYAN
    HEADER = Fore.MAGENTA
    STATION1 = Fore.BLUE
    STATION2 = Fore.GREEN
    FLOW = Fore.CYAN
    MIDDLEWARE = Fore.YELLOW
    BRIGHT = Style.BRIGHT
    RESET = Style.RESET_ALL
    
    @staticmethod
    def divider(char='=', length=80, color=None):
        """Print a colored divider line"""
        color = color or ColorLogger.HEADER
        print(f"{color}{char * length}{ColorLogger.RESET}")
    
    @staticmethod
    def header(text, color=None):
        """Print a header with dividers"""
        color = color or ColorLogger.INFO
        ColorLogger.divider()
        print(f"{color}{ColorLogger.BRIGHT}{text}{ColorLogger.RESET}")
        ColorLogger.divider()
    
    @staticmethod
    def success(label, message):
        """Print success message with checkmark"""
        print(f"[{label}] {ColorLogger.SUCCESS}✓{ColorLogger.RESET} {message}")
    
    @staticmethod
    def error(label, message):
        """Print error message with X mark"""
        print(f"[{label}] {ColorLogger.ERROR}✗{ColorLogger.RESET} {message}")
    
    @staticmethod
    def warning(label, message):
        """Print warning message with warning symbol"""
        print(f"[{label}] {ColorLogger.WARNING}⚠{ColorLogger.RESET} {message}")
    
    @staticmethod
    def info(label, message, color=None):
        """Print info message"""
        if color:
            print(f"{color}[{label}] {message}{ColorLogger.RESET}")
        else:
            print(f"[{label}] {message}")
    
    @staticmethod
    def field(label, key, value, color=None):
        """Print a labeled field with value"""
        print(f"[{label}] {key}: {value}")


# Station 1 logging functions
def log_station1_request(plugin_id, intent, scope):
    """Log Station 1 certificate verification request"""
    print()
    ColorLogger.divider(color=ColorLogger.STATION1)
    print(f"{ColorLogger.STATION1}{ColorLogger.BRIGHT}[STATION 1] Certificate Verification Request{ColorLogger.RESET}")
    print(f"[STATION 1] Plugin ID: {plugin_id}")
    print(f"[STATION 1] Intent: {intent}")
    print(f"[STATION 1] Scope: {scope}")
    ColorLogger.divider(color=ColorLogger.STATION1)
    print()


def log_station1_no_cert():
    """Log Station 1 no certificate provided"""
    ColorLogger.error("STATION 1", "No certificate provided - redirecting to CA")
    print()


def log_station1_cert_failed(error):
    """Log Station 1 certificate verification failure"""
    ColorLogger.error("STATION 1", f"Certificate verification failed: {error}")
    print()


def log_station1_success(trust_score):
    """Log Station 1 success"""
    ColorLogger.success("STATION 1", "Certificate verified successfully")
    ColorLogger.success("STATION 1", "JWT issued with intent-bound claims")
    print(f"[STATION 1] Trust Score: {trust_score}")
    print("[STATION 1] Plugin should now proceed to Station 2")
    print()


def log_station1_processing(plugin_id, intent, scope):
    """Log Station 1 certificate processing"""
    print()
    ColorLogger.divider(char='=', length=60, color=ColorLogger.STATION1)
    print(f"{ColorLogger.STATION1}{ColorLogger.BRIGHT}[STATION 1] Processing certificate for plugin: {plugin_id}{ColorLogger.RESET}")
    print(f"[STATION 1] Requested intent: {intent}, scope: {scope}")
    ColorLogger.divider(char='=', length=60, color=ColorLogger.STATION1)


def log_station1_cert_verified(plugin_id, serial):
    """Log Station 1 certificate verified"""
    ColorLogger.success("STATION 1", "Certificate verified locally")
    print(f"[STATION 1] Plugin ID: {plugin_id}")
    print(f"[STATION 1] Serial: {serial}")


def log_station1_cert_verify_error(error):
    """Log Station 1 certificate verification error"""
    ColorLogger.error("STATION 1", f"Certificate verification error: {error}")


def log_station1_revoked(reason):
    """Log Station 1 certificate revoked"""
    ColorLogger.error("STATION 1", f"Certificate revoked: {reason}")


def log_station1_not_revoked():
    """Log Station 1 certificate not revoked"""
    ColorLogger.success("STATION 1", "Certificate not revoked")


def log_station1_jwt_issued():
    """Log Station 1 JWT issued"""
    ColorLogger.success("STATION 1", "JWT issued successfully")
    ColorLogger.info("STATION 1", "Next: Station 2 (Access Control)", ColorLogger.STATION1)
    ColorLogger.divider(char='=', length=60, color=ColorLogger.STATION1)
    print()


def log_station1_warning(message):
    """Log Station 1 warning"""
    ColorLogger.warning("STATION 1", message)


# Station 2 logging functions
def log_station2_request(method, path):
    """Log Station 2 access validation request"""
    print()
    ColorLogger.divider(color=ColorLogger.STATION2)
    print(f"{ColorLogger.STATION2}{ColorLogger.BRIGHT}[STATION 2] Access Validation Request{ColorLogger.RESET}")
    print(f"[STATION 2] Method: {method}")
    print(f"[STATION 2] Path: {path}")
    ColorLogger.divider(color=ColorLogger.STATION2)
    print()


def log_station2_no_auth():
    """Log Station 2 no authorization header"""
    ColorLogger.error("STATION 2", "No Authorization header provided")
    print()


def log_station2_denied(error):
    """Log Station 2 access denied"""
    ColorLogger.error("STATION 2", f"Access DENIED: {error}")
    print()


def log_station2_granted(plugin_id, trust_score, intent, scope):
    """Log Station 2 access granted"""
    ColorLogger.success("STATION 2", "JWT validated successfully")
    ColorLogger.success("STATION 2", "Access GRANTED to core communication")
    print(f"[STATION 2] Plugin ID: {plugin_id}")
    print(f"[STATION 2] Trust Score: {trust_score}")
    print(f"[STATION 2] Intent: {intent}")
    print(f"[STATION 2] Scope: {scope}")
    print()


# Flow logging functions
def log_flow_header(plugin_id):
    """Log flow header"""
    print()
    ColorLogger.divider(color=ColorLogger.FLOW)
    print(f"{ColorLogger.FLOW}{ColorLogger.BRIGHT}[SECURE GATEWAY] New Plugin Detected: {plugin_id}{ColorLogger.RESET}")
    print(f"{ColorLogger.FLOW}{ColorLogger.BRIGHT}[SECURE GATEWAY] Starting Two-Station Authentication Flow...{ColorLogger.RESET}")
    ColorLogger.divider(color=ColorLogger.FLOW)
    print()


def log_flow_step(step_num, message, color=None):
    """Log flow step"""
    print(f"{ColorLogger.FLOW}{ColorLogger.BRIGHT}[FLOW] Step {step_num}:{ColorLogger.RESET} {message}")


def log_flow_step_success(step_num, message, details=None):
    """Log flow step success"""
    print(f"[FLOW] {ColorLogger.SUCCESS}✓{ColorLogger.RESET} Step {step_num} Complete: {message}")
    if details:
        for key, value in details.items():
            print(f"[FLOW]   {key}: {value}")


def log_flow_step_failed(step_num, error):
    """Log flow step failure"""
    print(f"[FLOW] {ColorLogger.ERROR}✗{ColorLogger.RESET} Step {step_num} FAILED: {error}")


def log_flow_complete(plugin_id):
    """Log flow completion"""
    print()
    ColorLogger.divider(color=ColorLogger.SUCCESS)
    print(f"{ColorLogger.SUCCESS}{ColorLogger.BRIGHT}[SECURE GATEWAY] ✓ Two-Station Flow Complete for plugin '{plugin_id}'{ColorLogger.RESET}")
    print("[SECURE GATEWAY] Plugin can now communicate with core system")
    ColorLogger.divider(color=ColorLogger.SUCCESS)
    print()


def log_flow_error(error):
    """Log flow error"""
    print(f"[FLOW] {ColorLogger.ERROR}✗{ColorLogger.RESET} Authentication flow error: {error}")


def log_flow_cached_jwt(plugin_id):
    """Log using cached JWT"""
    ColorLogger.info("AUTH", f"Plugin {plugin_id} using cached JWT", ColorLogger.INFO)


# Middleware logging
def log_middleware_auth(plugin_id, flow_type="two-station"):
    """Log middleware authentication"""
    print(f"[MIDDLEWARE] {ColorLogger.SUCCESS}✓{ColorLogger.RESET} Plugin {plugin_id} authenticated via {flow_type} flow")


def log_middleware_legacy(plugin_id):
    """Log middleware legacy authentication"""
    print(f"[MIDDLEWARE] {ColorLogger.WARNING}⚠{ColorLogger.RESET} Plugin {plugin_id} authenticated via legacy JWT")


# ──────────────────────────────────────────────────────────────────────────── #
#  Trust Engine logging                                                        #
# ──────────────────────────────────────────────────────────────────────────── #

TRUST_COLOR = Fore.MAGENTA


def log_trust_evaluation(plugin_id, score_before, score_after, delta, status, anomaly, reasons):
    """Log a complete trust evaluation result"""
    arrow = "→"
    prefix = f"{TRUST_COLOR}[TRUST]{ColorLogger.RESET}"
    if delta < 0:
        delta_str = f"{ColorLogger.ERROR}{delta:+.1f}{ColorLogger.RESET}"
    elif delta > 0:
        delta_str = f"{ColorLogger.SUCCESS}{delta:+.1f}{ColorLogger.RESET}"
    else:
        delta_str = f"{delta:+.1f}"
    print(
        f"{prefix} plugin={plugin_id} score={score_before:.1f}{arrow}{score_after:.1f} "
        f"delta={delta_str} status={status} anomaly={anomaly}"
    )
    if reasons:
        for r in reasons:
            print(f"{prefix}   • {r}")


def log_trust_recovery(plugin_id, amount, new_score):
    """Log passive trust recovery"""
    print(
        f"{TRUST_COLOR}[TRUST]{ColorLogger.RESET} "
        f"{ColorLogger.SUCCESS}↑{ColorLogger.RESET} "
        f"plugin={plugin_id} recovered +{amount:.1f} → {new_score:.1f}"
    )


def log_trust_anomaly_cleared(plugin_id):
    """Log anomaly flag cleared"""
    print(
        f"{TRUST_COLOR}[TRUST]{ColorLogger.RESET} "
        f"{ColorLogger.SUCCESS}✓{ColorLogger.RESET} "
        f"plugin={plugin_id} anomaly flag cleared"
    )


# ──────────────────────────────────────────────────────────────────────────── #
#  Policy Engine logging                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

POLICY_COLOR = Fore.YELLOW


def log_policy_decision(plugin_id, decision, risk_level, score, path, method, reason):
    """Log a policy decision"""
    prefix = f"{POLICY_COLOR}[POLICY]{ColorLogger.RESET}"
    if decision in ("ALLOW",):
        dec_str = f"{ColorLogger.SUCCESS}{decision}{ColorLogger.RESET}"
    elif decision in ("RATE_LIMIT",):
        dec_str = f"{ColorLogger.WARNING}{decision}{ColorLogger.RESET}"
    else:
        dec_str = f"{ColorLogger.ERROR}{decision}{ColorLogger.RESET}"
    print(
        f"{prefix} plugin={plugin_id} decision={dec_str} risk={risk_level} "
        f"score={score:.1f} {method} {path}"
    )
    print(f"{prefix}   reason: {reason}")
