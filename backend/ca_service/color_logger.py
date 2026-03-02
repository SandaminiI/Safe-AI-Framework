"""
Colorful terminal logging utilities for CA Service
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
    def success(label, message=None):
        """Print success message with checkmark"""
        if message:
            print(f"[{label}] {ColorLogger.SUCCESS}✓{ColorLogger.RESET} {message}")
        else:
            print(f"{ColorLogger.SUCCESS}{label}{ColorLogger.RESET}")
    
    @staticmethod
    def error(label, message=None):
        """Print error message with X mark"""
        if message:
            print(f"[{label}] {ColorLogger.ERROR}✗{ColorLogger.RESET} {message}")
        else:
            print(f"{ColorLogger.ERROR}{label}{ColorLogger.RESET}")
    
    @staticmethod
    def warning(label, message=None):
        """Print warning message with warning symbol"""
        if message:
            print(f"[{label}] {ColorLogger.WARNING}⚠{ColorLogger.RESET} {message}")
        else:
            print(f"{ColorLogger.WARNING}{label}{ColorLogger.RESET}")
    
    @staticmethod
    def info(label, message=None):
        """Print info message"""
        if message:
            print(f"[{label}] {message}")
        else:
            print(f"[{label}]")
    
    @staticmethod
    def field(label, value, color=None):
        """Print a labeled field with value"""
        print(f"[CA SERVICE] {label}: {value}")
    
    @staticmethod
    def section(title):
        """Print a section title"""
        print(f"\n{ColorLogger.HEADER}{ColorLogger.BRIGHT}{title}{ColorLogger.RESET}")


# Convenience functions for CA Service
def log_startup():
    """Log CA service startup"""
    print()
    ColorLogger.divider()
    print(f"{ColorLogger.INFO}{ColorLogger.BRIGHT}[CA SERVICE] Certificate Authority Service Started{ColorLogger.RESET}")
    print("[CA SERVICE] Database: ca_service.db")
    ColorLogger.divider()
    print()


def log_cert_request(plugin_id, ttl_hours, client_ip):
    """Log certificate issuance request"""
    print()
    ColorLogger.divider()
    print(f"{ColorLogger.INFO}{ColorLogger.BRIGHT}[CA SERVICE] Certificate Request Received{ColorLogger.RESET}")
    print(f"[CA SERVICE] Plugin ID: {plugin_id}")
    print(f"[CA SERVICE] TTL Hours: {ttl_hours}")
    print(f"[CA SERVICE] Client IP: {client_ip}")
    ColorLogger.divider()
    print()


def log_cert_issued(serial_number, expires_at):
    """Log successful certificate issuance"""
    ColorLogger.success("CA SERVICE", "Certificate Issued Successfully")
    print(f"[CA SERVICE] Serial Number: {serial_number}")
    print(f"[CA SERVICE] Expires At: {expires_at}")
    print("[CA SERVICE] Stored in database: ca_service.db")
    print("[CA SERVICE] Plugin should now go to Station 1 with this certificate")
    print()


def log_cert_verify_request(plugin_id, client_ip):
    """Log certificate verification request"""
    print()
    print(f"{ColorLogger.INFO}{ColorLogger.BRIGHT}[CA SERVICE] Certificate Verification Request{ColorLogger.RESET}")
    if plugin_id:
        print(f"[CA SERVICE] Plugin ID: {plugin_id}")
    else:
        print("[CA SERVICE] Plugin ID: Not specified")
    print(f"[CA SERVICE] Client IP: {client_ip}")


def log_cert_verify_failed(reason):
    """Log certificate verification failure"""
    ColorLogger.error("CA SERVICE", f"Certificate Verification FAILED: {reason}")
    print()


def log_cert_verify_success(plugin_id, serial_number):
    """Log certificate verification success"""
    ColorLogger.success("CA SERVICE", "Certificate Verification SUCCESS")
    print(f"[CA SERVICE] Plugin ID: {plugin_id}")
    print(f"[CA SERVICE] Serial: {serial_number}")
    print("[CA SERVICE] Plugin should proceed to Station 1")
    print()


def log_cert_revoked_check(reason):
    """Log certificate revoked during verification"""
    ColorLogger.error("CA SERVICE", f"Certificate REVOKED: {reason}")
    print()


def log_revoke_request(serial_number, reason):
    """Log certificate revocation request"""
    print()
    print(f"{ColorLogger.WARNING}{ColorLogger.BRIGHT}[CA SERVICE] Certificate Revocation Request{ColorLogger.RESET}")
    print(f"[CA SERVICE] Serial Number: {serial_number}")
    print(f"[CA SERVICE] Reason: {reason}")


def log_revoke_success(plugin_id):
    """Log successful certificate revocation"""
    ColorLogger.success("CA SERVICE", "Certificate Revoked Successfully")
    print(f"[CA SERVICE] Plugin ID: {plugin_id}")
    print()


def log_revocation_check(serial_number, is_revoked):
    """Log revocation status check"""
    if is_revoked:
        print(f"[CA SERVICE] {ColorLogger.WARNING}⚠{ColorLogger.RESET} Revocation check: {serial_number} - REVOKED")
    else:
        print(f"[CA SERVICE] Revocation check: {serial_number} - Not revoked")
