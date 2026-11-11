# Third-party notices

QSO Map itself (`src/`, `tools/`, `installer/`) is © 2026 Richard A. Hendriksen (PD3RAH) and
released under the MIT License (see `LICENSE`). The program uses only the Python standard
library and tkinter.

| Component | License | Source |
|---|---|---|
| World map (`src/world.json`): country outlines, simplified | Public domain | Natural Earth 1:50m, naturalearthdata.com |
| world-atlas 2.0 (TopoJSON packaging of Natural Earth, used at build time by `tools/make_world.py`) | ISC License, see `licenses/world-atlas/` | github.com/topojson/world-atlas |
| CPython (Python runtime, in the installer) | Python Software Foundation License 2.0 | python.org, via conda-forge |
| Tcl/Tk (tkinter GUI, in the installer) | Tcl/Tk license (BSD-style) | tcl.tk, via conda-forge |
| libffi, zlib, bzip2, xz/liblzma, libexpat (in the installer) | MIT / zlib / bzip2 / 0BSD / MIT | via conda-forge |
| Microsoft Visual C++ runtime (`vcruntime140.dll`, `vcruntime140_1.dll`) | Microsoft Visual C++ Runtime license terms | Microsoft, via conda-forge `vc14_runtime` |
| NSIS (installer framework) | zlib/libpng License | nsis.sourceforge.io |

Notes

* The callsign prefix table (`src/prefixes.py`) and the example log (`docs/voorbeeld.adi`,
  fictitious contacts) were written for this project.
* Fonts (Segoe UI, Bahnschrift, Consolas) are not bundled; the program uses the fonts in Windows.
* The program icon and visual design are original and shared with CW Station (same author).
* QRZ.com is only opened as a web link; no data is retrieved from it.
