"""
test_legacy_behavior.py
=======================
Documents the EXISTING command-generation behaviour of imageconvert_tool.py
AS A PURE PYTHON SPECIFICATION — without importing the tkinter module.

These tests are written BEFORE any refactoring and form the regression baseline.
Every test here must also pass against the new ``ImageMagickAdapter._build_args()``.

The helper ``_legacy_build_command()`` is a verbatim extraction of
``ImageConvertApp.get_command()`` (lines 119-139) as a pure function.
Nothing in imageconvert_tool.py is imported or modified.
"""
from __future__ import annotations

import os

# ── Verbatim extraction of get_command() as a pure function ───────────────────
_VECTOR_DOC_FORMATS = {"PDF", "PS", "EPS"}
_MULTIPAGE_TRIGGER  = {"PDF", "PS", "EPS", "GIF", "TIFF", "TIF", "MNG"}


def _legacy_build_command(
    folder: str,
    name: str,
    src: str,
    dst: str,
    quality: int = 95,
    density: int = 300,
    all_pages: bool = True,
) -> str:
    """
    Pure Python reproduction of ``ImageConvertApp.get_command()``.
    Source: imageconvert_tool.py lines 119-139.  Do NOT change this function —
    it is intentionally frozen to match the original behaviour.
    """
    src = src.upper()
    dst = dst.upper()
    if not name:
        return ""
    source = os.path.join(folder, f"{name}.{src.lower()}")
    density_opt = f"-density {density} " if src in _VECTOR_DOC_FORMATS else ""
    multipage = all_pages and (
        src in _VECTOR_DOC_FORMATS
        or src in {"GIF", "TIFF", "TIF", "PDF", "PS", "EPS", "MNG"}
    )
    if src == dst:
        return (
            f"# Input and output formats are the same. "
            f"Choose a different output format.\n"
            f'magick "{source}" "{os.path.join(folder, name + "." + dst.lower())}"'
        )
    target = (
        os.path.join(folder, f"{name}-%03d.{dst.lower()}")
        if multipage
        else os.path.join(folder, f"{name}.{dst.lower()}")
    )
    if dst in {"JPG", "JPEG"} and src == "PNG":
        return (
            f'magick {density_opt}"{source}" '
            f"-background white -alpha remove -alpha off "
            f'-quality {quality} "{target}"'
        )
    if dst in {"JPG", "JPEG", "WEBP", "AVIF", "HEIC"}:
        return f'magick {density_opt}"{source}" -quality {quality} "{target}"'
    return f'magick {density_opt}"{source}" "{target}"'


# ── Helpers ───────────────────────────────────────────────────────────────────

FOLDER = r"C:\Users\test\Downloads"
NAME   = "testfile"


def cmd(src: str, dst: str, **kw) -> str:
    return _legacy_build_command(FOLDER, NAME, src, dst, **kw)


# ── Tests — empty / invalid inputs ────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_name_returns_empty_string(self):
        assert _legacy_build_command(FOLDER, "", "PNG", "PDF") == ""

    def test_same_format_starts_with_comment(self):
        result = cmd("PNG", "PNG")
        assert result.startswith("#")

    def test_same_format_comment_mentions_same(self):
        result = cmd("PNG", "PNG")
        assert "same" in result.lower()

    def test_same_format_still_contains_magick_command(self):
        # The original emits a warning comment THEN a fallback magick line
        result = cmd("PNG", "PNG")
        assert "magick" in result


# ── Tests — alpha / transparency handling ─────────────────────────────────────

class TestAlphaHandling:
    def test_png_to_jpg_includes_alpha_remove(self):
        assert "-alpha remove" in cmd("PNG", "JPG")

    def test_png_to_jpg_includes_alpha_off(self):
        assert "-alpha off" in cmd("PNG", "JPG")

    def test_png_to_jpg_includes_white_background(self):
        assert "-background white" in cmd("PNG", "JPG")

    def test_png_to_jpeg_also_has_alpha_remove(self):
        assert "-alpha remove" in cmd("PNG", "JPEG")

    def test_webp_to_jpg_does_not_have_alpha_remove(self):
        # Alpha remove only triggers when src==PNG and dst is JPG/JPEG
        assert "-alpha remove" not in cmd("WEBP", "JPG")

    def test_png_to_webp_no_alpha_flags(self):
        assert "-alpha remove" not in cmd("PNG", "WEBP")


# ── Tests — quality flag ──────────────────────────────────────────────────────

class TestQuality:
    def test_png_to_jpg_quality_default(self):
        assert "-quality 95" in cmd("PNG", "JPG")

    def test_png_to_jpg_custom_quality(self):
        assert "-quality 80" in cmd("PNG", "JPG", quality=80)

    def test_png_to_webp_has_quality(self):
        assert "-quality 75" in cmd("PNG", "WEBP", quality=75)

    def test_png_to_avif_has_quality(self):
        assert "-quality 60" in cmd("PNG", "AVIF", quality=60)

    def test_png_to_heic_has_quality(self):
        assert "-quality 50" in cmd("PNG", "HEIC", quality=50)

    def test_png_to_tiff_no_quality_flag(self):
        assert "-quality" not in cmd("PNG", "TIFF")

    def test_png_to_bmp_no_quality_flag(self):
        assert "-quality" not in cmd("PNG", "BMP")

    def test_jpg_to_png_no_quality_flag(self):
        assert "-quality" not in cmd("JPG", "PNG")


# ── Tests — density / DPI ─────────────────────────────────────────────────────

class TestDensity:
    def test_pdf_source_includes_density(self):
        assert "-density 300" in cmd("PDF", "PNG")

    def test_ps_source_includes_density(self):
        assert "-density" in cmd("PS", "PNG")

    def test_eps_source_includes_density(self):
        assert "-density" in cmd("EPS", "PNG")

    def test_pdf_custom_density(self):
        assert "-density 150" in cmd("PDF", "PNG", density=150)

    def test_png_source_no_density(self):
        assert "-density" not in cmd("PNG", "JPG")

    def test_jpg_source_no_density(self):
        assert "-density" not in cmd("JPG", "PNG")

    def test_density_appears_before_source_file(self):
        result = cmd("PDF", "PNG", density=200)
        density_pos = result.index("-density")
        source_pos  = result.index(f"{NAME}.pdf")
        assert density_pos < source_pos


# ── Tests — multipage / numbered output ───────────────────────────────────────

class TestMultipage:
    def test_pdf_multipage_on_has_numbered_pattern(self):
        assert "%03d" in cmd("PDF", "PNG", all_pages=True)

    def test_gif_multipage_on_has_numbered_pattern(self):
        assert "%03d" in cmd("GIF", "PNG", all_pages=True)

    def test_tiff_multipage_on_has_numbered_pattern(self):
        assert "%03d" in cmd("TIFF", "PNG", all_pages=True)

    def test_mng_multipage_on_has_numbered_pattern(self):
        assert "%03d" in cmd("MNG", "PNG", all_pages=True)

    def test_multipage_off_no_numbered_pattern(self):
        assert "%03d" not in cmd("PDF", "PNG", all_pages=False)

    def test_png_source_no_numbered_pattern(self):
        assert "%03d" not in cmd("PNG", "JPG", all_pages=True)

    def test_jpg_source_no_numbered_pattern(self):
        assert "%03d" not in cmd("JPG", "PNG", all_pages=True)


# ── Tests — output path structure ────────────────────────────────────────────

class TestOutputPath:
    def test_simple_output_has_correct_extension(self):
        result = cmd("PNG", "BMP")
        assert result.endswith(f'{NAME}.bmp"')

    def test_multipage_output_uses_lowercase_extension(self):
        result = cmd("PDF", "PNG")
        assert ".png" in result.lower()

    def test_source_path_contains_input_extension(self):
        result = cmd("PNG", "JPG")
        assert f"{NAME}.png" in result

    def test_output_stays_in_same_folder(self):
        result = cmd("PNG", "JPG")
        assert FOLDER in result

    def test_case_insensitive_format_input(self):
        lower_result = _legacy_build_command(FOLDER, NAME, "png", "jpg")
        upper_result = _legacy_build_command(FOLDER, NAME, "PNG", "JPG")
        assert lower_result == upper_result
