# Sovereign Workstation

A local-first Windows desktop workstation built with PySide6. Image conversion remains available alongside an incrementally implemented document intelligence workflow. The application does not use cloud AI services.

## Features

- Workbench navigation for Dashboard, AI Workspace, Documents, Model Manager, Task History, Settings, and Conversion.
- Dashboard status comes from the actual ImageMagick/Ghostscript health check, saved conversion history, default permission policy, and asynchronous local-runtime discovery.
- Model Manager detects Ollama and llama.cpp command-line runtimes on `PATH`; it reads Ollama's model list only when `OLLAMA_HOST` is unset or loopback-local. It does not query a remote Ollama endpoint, download, or load models.
- Task History and conversion preferences use the local SQLite database under the platform application-data directory.
- Documents locally extracts text from PDF, DOCX, TXT, and Markdown, stores metadata and chunks in SQLite, and preserves the original source when an index is removed. Scanned PDF OCR is not implemented.
- Ollama embedding and chat integrations are separate, loopback-only capabilities. A document is marked indexed only after a separately installed embedding model successfully creates and stores vectors. Runtime discovery alone does not configure either model.
- AI Workspace performs document-scoped local retrieval and sends bounded evidence to an explicitly configured local chat model. Citations are built from retrieved source chunks. Insufficient retrieval evidence is reported without calling the chat model.
- Model download, OCR installation, cloud AI, and automatic cloud fallback are not implemented. No model or external tool is downloaded by the application.
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
- Python 3.11+ only if running from source or building the EXE
- Ollama is optional for document Q&A and must be installed and configured locally by the user. A separate local embedding-capable model and local chat model are required; the same chat model is not assumed to provide embeddings.

## Run from source

```powershell
python -m pip install -r requirements.txt
python main.py
```

The modular PySide6 application is launched by `main.py`. The original Tkinter utility remains available with `python imageconvert_tool.py` for backward compatibility.

## Build a Windows EXE

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH**.
2. Double-click `build_exe.bat`.
3. The executable will be created at `dist\SovereignWorkstation.exe`.

ImageMagick and delegates such as Ghostscript are external dependencies and must still be installed separately.

## Usage

1. Choose the input and output formats.
2. Enter the input file name **without its extension** (for example, `photo`).
3. Set the folder containing the input file. Enter a folder path only, without quotes.
4. Adjust quality or rendering DPI if required.
5. Click **Convert now** or **Copy command**.

For multipage PDFs and supported animated/multipage inputs, leave the numbered output option checked.

### Local document Q&A

1. Start a local Ollama runtime and install an embedding model and a chat model yourself. The application never pulls models.
2. On Documents, grant local document access for the current session, then import PDF, DOCX, TXT, or Markdown files. Source files stay in their original locations.
3. Enter the installed embedding model name and choose **Index selected**. Until embedding succeeds, the document remains unavailable to semantic search.
4. Enter the installed chat model name in AI Workspace, select an indexed document, and enable the separate document-retrieval and local-answer session controls before asking a question.

PDF text extraction uses the PySide6 QtPdf module. Text-only extraction is supported; scanned pages require a separately configured local OCR workflow, which is not currently implemented. Imported content is treated as untrusted evidence and is not allowed to invoke tools. Removing a document index deletes its stored text and vectors but keeps the original file.

### Local workflows and reports

The Workflows page can ask the configured local Ollama chat model for a structured plan. Only the built-in document retrieval and evidence-report tools are allowlisted. Planning and tool use are disabled by default in each session, and every step must be approved individually. Runs and step results are persisted locally; pending approvals can be selected after restart. A local TXT workflow (planning, retrieval, and individually approved execution) was exercised end to end with installed Ollama models; PDF, DOCX, and Markdown RAG remain unverified end to end.

Approved evidence reports can be created as TXT, Markdown, or JSON in an existing user-selected directory. File creation requires separate session consent and a matching approved output root. Reports are created atomically and existing files are never overwritten. PDF/DOCX generation, general-purpose agents, shell execution, and arbitrary filesystem tools are not implemented.

SQLite currently stores imported document text, embedding vectors, workflow state, preferences, and audit events without encryption at rest. Protect the operating-system account and application data directory accordingly; the application does not claim database encryption.

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
