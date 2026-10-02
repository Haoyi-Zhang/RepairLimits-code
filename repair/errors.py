"""Typed failures used to keep resource exhaustion distinct from rejection."""


class ResourceExhausted(RuntimeError):
    """A bounded semantic search or checker exhausted a declared resource cap."""
