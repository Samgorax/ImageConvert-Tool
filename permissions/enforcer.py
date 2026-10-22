"""
permissions/enforcer.py
========================
PermissionEnforcer — the single gatekeeper for all privileged operations.

RULE: every privileged operation in the application MUST call the appropriate
``require_*`` method here before proceeding.  No exceptions.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.exceptions import PathTraversalError, PermissionDeniedError
from permissions.policy import PermissionPolicy

_log = logging.getLogger(__name__)


class PermissionEnforcer:
    def __init__(self, policy: PermissionPolicy) -> None:
        self._policy = policy

    @property
    def policy(self) -> PermissionPolicy:
        return self._policy

    def require_write_output(self, path: Path) -> None:
        """Assert that writing *path* is permitted by the current policy."""
        if not self._policy.allow_write_output_dir:
            raise PermissionDeniedError(
                "File system writes are disabled by the current permission policy."
            )
        if self._policy.allowed_output_roots:
            resolved = path.resolve()
            for root in self._policy.allowed_output_roots:
                try:
                    resolved.relative_to(Path(root).resolve())
                    return   # within an approved root — ok
                except ValueError:
                    continue
            raise PathTraversalError(
                f"Output path '{path}' is not within any allowed output directory."
            )

    def require_batch(self) -> None:
        if not self._policy.allow_batch_processing:
            raise PermissionDeniedError("Batch processing is disabled by policy.")

    def require_ai_suggestions(self) -> None:
        if not self._policy.allow_ai_suggestions:
            raise PermissionDeniedError(
                "Local AI suggestions are disabled. Enable them for the current session."
            )

    def require_ai_execute(self) -> None:
        if not self._policy.allow_ai_execute_conversions:
            raise PermissionDeniedError(
                "AI autonomous execution is disabled. The user must approve each action."
            )

    def require_agent_tools(self) -> None:
        if not self._policy.allow_agent_tools:
            raise PermissionDeniedError(
                "Workflow tools are disabled by policy. Enable approved local tools for this session."
            )

    def require_document_access(self) -> None:
        if not self._policy.allow_document_access:
            raise PermissionDeniedError(
                "Local document access is disabled. Grant document access for this session first."
            )

    def require_ai_write_files(self) -> None:
        if not self._policy.allow_ai_write_files:
            raise PermissionDeniedError(
                "AI-assisted file creation is disabled by policy."
            )
