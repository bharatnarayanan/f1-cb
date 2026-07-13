class AlertDeliveryError(Exception):
    """Raised when an alert channel can't deliver — missing config, or the
    send itself failed. Callers (src/alerts/dispatcher.py) catch this and
    record dispatch_status="failed" rather than letting it crash the
    recommendation-creation flow that triggered the alert.
    """
