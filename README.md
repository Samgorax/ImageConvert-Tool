# ImageConvert Tool

A Windows desktop utility for converting images and documents using [ImageMagick](https://imagemagick.org/).

## Features

- Select input and output formats from dropdowns.
- Generate and copy the matching PowerShell command.
- Convert directly from the GUI.
- Choose the input folder and file name.
- Adjust JPEG quality and PDF/PostScript/EPS rendering DPI.
- Convert multipage PDFs and supported animated/multipage formats to numbered output files.
- Display conversion errors to help diagnose missing delegates, unsupported formats, or security restrictions.

## Format choices

The GUI offers PNG, JPG, JPEG, WEBP, GIF, BMP, TIFF, TIF, ICO, SVG, PDF, PS, EPS, AVIF, HEIC, JP2, J2K, PNM, PPM, PGM, PBM, TGA, DDS, HDR, EXR, PCX, XPM, MIFF, MNG, PAM, PGX, RAS, SUN, and WBMP.

**Actual format support depends on your ImageMagick build and installed delegates.** Check available formats in PowerShell:

```powershell
magick -list format
```

PDF/PS/EPS conversion usually requires Ghostscript and may be restricted by ImageMagick's security policy.

## Requirements

- Windows 10/11
- ImageMagick installed and available as `magick` in PATH
- Ghostscript for many PDF/PS/EPS operations
- Python 3.10+ only if running from source or building the EXE

## Run from source

```powershell
python imageconvert_tool.py
```

## Build a Windows EXE

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH**.
2. Double-click `build_exe.bat`.
3. The executable will be created at `dist\ImageConvertTool.exe`.

ImageMagick and delegates such as Ghostscript are external dependencies and must still be installed separately.

## Usage

1. Choose the input and output formats.
2. Enter the input file name **without its extension** (for example, `photo`).
3. Set the folder containing the input file. Enter a folder path only, without quotes.
4. Adjust quality or rendering DPI if required.
5. Click **Convert now** or **Copy command**.

For multipage PDFs and supported animated/multipage inputs, leave the numbered output option checked.

### Notes

- JPG does not support transparency; PNG-to-JPG conversion composites transparent pixels onto a white background.
- Converting JPG to PNG does not restore quality already lost during JPG compression.
- Password-protected PDFs cannot be processed unless access is provided through an authorized workflow.
- No prebuilt EXE is included in this source repository. Build it on Windows with the script above.

## Troubleshooting

- **Input file not found:** enter only the file name without its extension in the file-name field, and only the directory in the folder field.
- **`magick` not found:** install ImageMagick and add its installation directory to PATH, then restart the app.
- **Ghostscript/PDF delegate error:** verify Ghostscript is installed and available; review ImageMagick security policy.
- **Unsupported format:** use `magick -list format` to check whether that format is enabled.

## License

No license has been added yet. Until a license is added, default copyright applies; others do not automatically receive permission to redistribute or modify the project.
