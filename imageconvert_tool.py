import os
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "ImageConvert Tool"
# Available formats depend on the ImageMagick build and its delegates.
FORMATS = [
    "PNG", "JPG", "JPEG", "WEBP", "GIF", "BMP", "TIFF", "TIF", "ICO",
    "SVG", "PDF", "PS", "EPS", "AVIF", "HEIC", "JP2", "J2K", "PNM",
    "PPM", "PGM", "PBM", "TGA", "DDS", "HDR", "EXR", "PCX", "XPM",
    "MIFF", "MNG", "PAM", "PGX", "RAS", "SUN", "WBMP"
]
RASTER_FORMATS = {"PNG", "JPG", "JPEG", "WEBP", "GIF", "BMP", "TIFF", "TIF", "ICO",
                  "AVIF", "HEIC", "JP2", "J2K", "PNM", "PPM", "PGM", "PBM", "TGA",
                  "DDS", "HDR", "EXR", "PCX", "XPM", "MIFF", "MNG", "PAM", "PGX",
                  "RAS", "SUN", "WBMP"}
VECTOR_DOC_FORMATS = {"PDF", "PS", "EPS"}

class ImageConvertApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x650")
        self.root.minsize(680, 590)

        self.input_format = tk.StringVar(value="PNG")
        self.output_format = tk.StringVar(value="PDF")
        self.filename = tk.StringVar(value="phase 3")
        self.folder = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.quality = tk.IntVar(value=95)
        self.density = tk.IntVar(value=300)
        self.all_pages = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready. Formats available depend on your ImageMagick installation.")

        self._build_ui()
        self.update_command()

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="ImageConvert Tool", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Convert images and documents with ImageMagick.").pack(anchor="w", pady=(2, 12))

        formats = ttk.Frame(outer)
        formats.pack(fill="x")
        left = ttk.LabelFrame(formats, text="Input format", padding=10)
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(formats, text="Output format", padding=10)
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.input_combo = ttk.Combobox(left, textvariable=self.input_format, values=FORMATS, state="readonly")
        self.input_combo.pack(fill="x")
        self.input_combo.bind("<<ComboboxSelected>>", lambda _e: self.update_command())
        self.output_combo = ttk.Combobox(right, textvariable=self.output_format, values=FORMATS, state="readonly")
        self.output_combo.pack(fill="x")
        self.output_combo.bind("<<ComboboxSelected>>", lambda _e: self.update_command())

        ttk.Label(outer, text="File name (without extension)").pack(anchor="w", pady=(12, 3))
        ttk.Entry(outer, textvariable=self.filename).pack(fill="x")
        self.filename.trace_add("write", lambda *_: self.update_command())

        ttk.Label(outer, text="Folder path").pack(anchor="w", pady=(10, 3))
        folder_row = ttk.Frame(outer)
        folder_row.pack(fill="x")
        ttk.Entry(folder_row, textvariable=self.folder).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="Browse…", command=self.browse_folder).pack(side="left", padx=(8, 0))
        self.folder.trace_add("write", lambda *_: self.update_command())

        options = ttk.LabelFrame(outer, text="Conversion options", padding=8)
        options.pack(fill="x", pady=(10, 0))
        ttk.Label(options, text="JPG quality").grid(row=0, column=0, sticky="w")
        self.quality_scale = ttk.Scale(options, from_=60, to=100, command=self.on_quality)
        self.quality_scale.set(95)
        self.quality_scale.grid(row=0, column=1, sticky="ew", padx=8)
        self.quality_label = ttk.Label(options, text="95%")
        self.quality_label.grid(row=0, column=2, sticky="e")
        ttk.Label(options, text="PDF/PS/EPS render DPI").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.density_scale = ttk.Scale(options, from_=72, to=600, command=self.on_density)
        self.density_scale.set(300)
        self.density_scale.grid(row=1, column=1, sticky="ew", padx=8, pady=(6, 0))
        self.density_label = ttk.Label(options, text="300 DPI")
        self.density_label.grid(row=1, column=2, sticky="e", pady=(6, 0))
        options.columnconfigure(1, weight=1)

        ttk.Checkbutton(options, text="Convert every page/frame to numbered output files (recommended for multipage PDFs/GIFs)", variable=self.all_pages, command=self.update_command).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(outer, text="Generated command").pack(anchor="w", pady=(12, 3))
        self.command_box = tk.Text(outer, height=4, wrap="word", font=("Consolas", 9))
        self.command_box.pack(fill="x")
        self.command_box.configure(state="disabled")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Copy command", command=self.copy_command).pack(side="left")
        ttk.Button(buttons, text="Convert now", command=self.convert_now).pack(side="left", padx=8)
        ttk.Button(buttons, text="Open output folder", command=self.open_folder).pack(side="left")

        ttk.Label(outer, textvariable=self.status, wraplength=710).pack(anchor="w", pady=(12, 0))
        ttk.Label(outer, text="Note: some formats need extra ImageMagick delegates. PDF/PS/EPS conversion may need Ghostscript and may be restricted by ImageMagick security policy.", wraplength=710, foreground="#666666").pack(anchor="w", pady=(6, 0))

    def on_quality(self, value):
        self.quality.set(int(float(value)))
        self.quality_label.configure(text=f"{self.quality.get()}%")
        self.update_command()

    def on_density(self, value):
        self.density.set(int(float(value)))
        self.density_label.configure(text=f"{self.density.get()} DPI")
        self.update_command()

    def browse_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder.get() or os.path.expanduser("~"))
        if chosen:
            self.folder.set(chosen)

    def get_command(self):
        src = self.input_format.get().upper()
        dst = self.output_format.get().upper()
        folder = self.folder.get().strip()
        name = self.filename.get().strip()
        if not name:
            return ""
        source = os.path.join(folder, f"{name}.{src.lower()}")
        density_opt = f"-density {self.density.get()} " if src in VECTOR_DOC_FORMATS else ""
        multipage = self.all_pages.get() and (src in VECTOR_DOC_FORMATS or src in {"GIF", "TIFF", "TIF", "PDF", "PS", "EPS", "MNG"})
        if src == dst:
            return f'# Input and output formats are the same. Choose a different output format.\nmagick "{source}" "{os.path.join(folder, name + "." + dst.lower())}"'
        if multipage:
            target = os.path.join(folder, f"{name}-%03d.{dst.lower()}")
        else:
            target = os.path.join(folder, f"{name}.{dst.lower()}")
        if dst in {"JPG", "JPEG"} and src == "PNG":
            return f'magick {density_opt}"{source}" -background white -alpha remove -alpha off -quality {self.quality.get()} "{target}"'
        if dst in {"JPG", "JPEG", "WEBP", "AVIF", "HEIC"}:
            return f'magick {density_opt}"{source}" -quality {self.quality.get()} "{target}"'
        return f'magick {density_opt}"{source}" "{target}"'

    def update_command(self):
        if not hasattr(self, "command_box"):
            return
        cmd = self.get_command()
        self.command_box.configure(state="normal")
        self.command_box.delete("1.0", "end")
        self.command_box.insert("1.0", cmd)
        self.command_box.configure(state="disabled")

    def copy_command(self):
        cmd = self.get_command()
        if not cmd:
            messagebox.showwarning(APP_TITLE, "Please enter a file name.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        self.status.set("Command copied to clipboard.")

    def convert_now(self):
        magick = shutil.which("magick")
        if not magick:
            # Known default path from common Windows ImageMagick installations
            candidate = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
            if os.path.isfile(candidate):
                magick = candidate
        if not magick:
            messagebox.showerror(APP_TITLE, "ImageMagick command 'magick' was not found.\nInstall ImageMagick and add its folder to PATH, then restart this app.")
            return
        src_fmt, dst_fmt = self.input_format.get().upper(), self.output_format.get().upper()
        folder, name = self.folder.get().strip(), self.filename.get().strip()
        if not name:
            messagebox.showwarning(APP_TITLE, "Please enter a file name.")
            return
        if src_fmt == dst_fmt:
            messagebox.showwarning(APP_TITLE, "Choose different input and output formats.")
            return
        source = os.path.join(folder, f"{name}.{src_fmt.lower()}")
        if not os.path.isfile(source):
            messagebox.showerror(APP_TITLE, f"Input file not found:\n{source}\n\nMake sure the file name and extension match exactly.")
            return
        # Use argument list instead of shell to safely handle spaces in paths.
        args = [magick]
        if src_fmt in VECTOR_DOC_FORMATS:
            args += ["-density", str(self.density.get())]
        args.append(source)
        if self.all_pages.get() and (src_fmt in VECTOR_DOC_FORMATS or src_fmt in {"GIF", "TIFF", "TIF", "PDF", "PS", "EPS", "MNG"}):
            target = os.path.join(folder, f"{name}-%03d.{dst_fmt.lower()}")
        else:
            target = os.path.join(folder, f"{name}.{dst_fmt.lower()}")
        if dst_fmt in {"JPG", "JPEG"} and src_fmt == "PNG":
            args += ["-background", "white", "-alpha", "remove", "-alpha", "off", "-quality", str(self.quality.get())]
        elif dst_fmt in {"JPG", "JPEG", "WEBP", "AVIF", "HEIC"}:
            args += ["-quality", str(self.quality.get())]
        args.append(target)
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                self.status.set("Conversion completed. Check the selected folder for output file(s).")
                messagebox.showinfo(APP_TITLE, "Conversion completed successfully.")
            else:
                details = (result.stderr or result.stdout or "Unknown conversion error").strip()
                self.status.set("Conversion failed. See error details.")
                messagebox.showerror(APP_TITLE, "Conversion failed:\n\n" + details[:4500] + "\n\nTip: run `magick -list format` in PowerShell to check format support.")
        except subprocess.TimeoutExpired:
            messagebox.showerror(APP_TITLE, "Conversion timed out after 10 minutes.")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Could not run conversion:\n{exc}")

    def open_folder(self):
        folder = self.folder.get().strip()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning(APP_TITLE, "The selected folder does not exist.")

if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    ImageConvertApp(root)
    root.mainloop()
