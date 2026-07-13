class ExtractionUnavailable(Exception):
    """Raised when strategy extraction can't run (no ANTHROPIC_API_KEY, or
    the API call itself failed). Unlike narration (an optional paragraph
    that degrades to a placeholder), extraction produces canonical_logic —
    a strategy has no honest "unknown" stand-in for its entire rule set, so
    this is a hard failure the caller must surface, not paper over.
    """
