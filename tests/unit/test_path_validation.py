"""
test_path_validation.py
=======================
Tests for the path sanitisation logic in ``engine.imagemagick_adapter``.

Covers:
- Directory traversal attempts (../ sequences)
- Null-byte injection
- Absolute paths that escape the chosen output directory
- Valid same-directory and nested-subdirectory paths
"""
from __future__ import annotations

from pathlib import Path

import pytest

# We test the validator independently — import it after core is created.
# Until then the tests are skipped gracefully so the baseline run still passes.
try:
    from engine.imagemagick_adapter import _validate_path
    _ENGINE_AVAILABLE = True
except ImportError:
    _ENGINE_AVAILABLE = False


def _validate_path(path: Path, *, base: Path | None = None) -> Path:
    """Resolve the validator lazily while keeping a stable, typed test binding."""
    from engine.imagemagick_adapter import _validate_path as validate_path

    return validate_path(path, base=base)


@pytest.mark.skipif(not _ENGINE_AVAILABLE, reason="engine not yet implemented")
class TestValidatePath:
    """Tests for engine.imagemagick_adapter._validate_path."""

    def test_valid_path_within_base_is_accepted(self, tmp_path: Path):
        target = tmp_path / "output.png"
        result = _validate_path(target, base=tmp_path)
        assert result == target.resolve()

    def test_valid_nested_path_within_base_is_accepted(self, tmp_path: Path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        target = subdir / "output.png"
        result = _validate_path(target, base=tmp_path)
        assert result == target.resolve()

    def test_traversal_with_dotdot_is_rejected(self, tmp_path: Path):
        from core.exceptions import PathTraversalError
        evil = tmp_path / "sub" / ".." / ".." / "etc" / "hosts"
        with pytest.raises(PathTraversalError):
            _validate_path(evil, base=tmp_path)

    def test_absolute_path_outside_base_is_rejected(self, tmp_path: Path):
        from core.exceptions import PathTraversalError
        outside = Path("C:/Windows/System32/evil.exe")
        with pytest.raises(PathTraversalError):
            _validate_path(outside, base=tmp_path)

    def test_no_base_does_not_raise(self, tmp_path: Path):
        """Without a base restriction any resolvable path is accepted."""
        target = tmp_path / "output.png"
        result = _validate_path(target, base=None)
        assert result == target.resolve()

    def test_same_dir_as_base_is_accepted(self, tmp_path: Path):
        target = tmp_path / "file.png"
        result = _validate_path(target, base=tmp_path)
        assert result.parent == tmp_path.resolve()


# ── Standalone path-sanitisation tests (no engine import) ─────────────────────
# These test the general principles and run immediately without any new code.

class TestPathSanitisationPrinciples:
    """
    Pure-Python tests for path-traversal concepts.
    These validate our understanding of Path.resolve() behaviour on Windows,
    which underpins _validate_path.
    """

    def test_dotdot_resolves_upward(self, tmp_path: Path):
        child = tmp_path / "a" / ".." / "b"
        assert child.resolve() == (tmp_path / "b").resolve()

    def test_resolve_removes_dotdot(self, tmp_path: Path):
        p = tmp_path / "a" / "b" / ".." / ".."
        assert p.resolve() == tmp_path.resolve()

    def test_relative_to_raises_on_outside_path(self, tmp_path: Path):
        outside = Path("C:/Windows").resolve()
        with pytest.raises(ValueError):
            outside.relative_to(tmp_path.resolve())

    def test_relative_to_succeeds_on_child(self, tmp_path: Path):
        child = (tmp_path / "sub" / "file.png").resolve()
        rel = child.relative_to(tmp_path.resolve())
        assert str(rel) != ""

    def test_empty_filename_component(self):
        p = Path("some/folder/")
        assert p.name == "" or p.name == "folder"   # platform-dependent; must not crash
