# anchor/cache.py
"""
Anchor cache layer.

Intended for:
- fingerprint → config dict mapping (used by Ledger for run deduplication)
- loaded config memoization for sweep-scale experiments

Not implemented yet — build when Ledger makes the requirement concrete.
"""
