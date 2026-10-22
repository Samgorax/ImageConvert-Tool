"""
permissions/policy.py
=====================
PermissionPolicy defines which capabilities are enabled per session.
All AI-related permissions are OFF by default — they must be explicitly
enabled by the user through the settings UI (Phase 3).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PermissionPolicy:
    """Immutable capability set for the current application session."""

    # ── File system ────────────────────────────────────────────────────────────
    allow_write_output_dir:  bool       = True
    allow_batch_processing:  bool       = True
    # If non-empty, output files MUST be under one of these roots
    allowed_output_roots:    list[str]  = field(default_factory=list)

    # ── AI (Phase 3 — all gated off by default) ────────────────────────────────
    allow_ai_suggestions:         bool = False
    allow_ai_execute_conversions: bool = False
    allow_ai_write_files:         bool = False
    allow_ai_unattended_batch:    bool = False
    allow_agent_tools:            bool = False
    allow_document_access:        bool = False

    # ── Network (Ollama runs locally but is still explicitly gated) ────────────
    allow_network_access: bool = False

    @classmethod
    def default(cls) -> PermissionPolicy:
        """Safe default — local conversion only, no AI."""
        return cls()

    @classmethod
    def ai_suggestions_only(cls) -> PermissionPolicy:
        """Enable AI advice but not autonomous execution."""
        return cls(allow_ai_suggestions=True)
