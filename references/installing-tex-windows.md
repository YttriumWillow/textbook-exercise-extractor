# Installing TeX on Windows (no admin rights)

Goal: a working `pdflatex` / `xelatex` + `tlmgr` for re-typesetting textbook problems —
at the OS default location, and as small as practical.

## Step 0 — pick the location (user rule)

Default is the OS standard directory: `C:/Program Files/texlive/<year>`.
Other drives only when the user explicitly asks (e.g. "install on D:").

**Check free space first** and allow **>= 4 GB** for `scheme-small`:

```powershell
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in @('C','D') } |
  Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}}
```

If the target drive is short on space, **stop and ask the user where to install** —
do not silently fall back to another drive.

> Current machine: TeX Live 2026 is installed at `D:\Program Files\texlive\2026`
> because the user asked for D: at the time. New installs should default to C:.

## What works (and what does not)

| Source | Status |
|---|---|
| `https://yihui.org/tinytex/TinyTeX-1.zip` | dead (404) |
| `https://github.com/rstudio/tinytex-releases/releases/latest/download/TinyTeX-1.zip` | dead (9-byte 404 body) |
| `https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet/install-tl-windows.exe` | **works** (≈20 MB, bundles perl) |
| `.../tlnet/install-tl.zip` | works, but has **no perl** — drive `install-tl` with the `tlpkg\tlperl\bin\perl.exe` inside it |

## Steps

```powershell
# 1. download the self-contained installer (bundles perl + tcl/tk)
curl.exe -L --retry 3 -o "$env:TEMP\install-tl-windows.exe" `
  "https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet/install-tl-windows.exe"

# 2. write a profile (see below), then install unattended
& "$env:TEMP\install-tl-windows.exe" -no-interaction -profile "<path>\texlive.profile" `
  -repository "https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet"

# 3. if the .exe self-extractor silently returns nothing, use the zip + TeX Live's own perl
#    Expand-Archive install-tl.zip -DestinationPath D:\tmp\tl
#    & "D:\tmp\tl\install-tl-*\tlpkg\tlperl\bin\perl.exe" `
#        "D:\tmp\tl\install-tl-*\install-tl" -no-interaction -profile <prof> -repository <mirror>
```

`texlive.profile` (paths may contain spaces; set `TEXDIR` to the location from step 0):

```
selected_scheme scheme-small
TEXDIR C:/Program Files/texlive/2026
TEXMFLOCAL C:/Program Files/texlive/texmf-local
TEXMFSYSCONFIG C:/Program Files/texlive/2026/texmf-config
TEXMFSYSVAR C:/Program Files/texlive/2026/texmf-var
TEXMFVAR ~/.texlive2026/texmf-var
TEXMFHOME ~/texmf
TEXMFCONFIG ~/.texlive2026/texmf-config
instopt_adjustpath 0
instopt_adjustrepo 1
instopt_letter 0
instopt_portable 0
instopt_write18_restricted 1
tlpdbopt_autobackup 0
tlpdbopt_install_docfiles 0
tlpdbopt_install_srcfiles 0
```

Expect ~7 minutes and ~420 packages for `scheme-small`.

### Keeping it small

- `scheme-small` (~1.5 GB) is the sweet spot: full LaTeX + maths + the usual packages.
- `scheme-basic` (~1 GB) works if you then `tlmgr install` `geometry enumitem xcolor
  fancyhdr titlesec parskip hyperref needspace` — it saves little and costs manual work.
- `scheme-minimal` (~200 MB) has **no LaTeX at all**; only use it for plain TeX.
- Always set `tlpdbopt_install_docfiles 0` and `tlpdbopt_install_srcfiles 0`
  (documentation and sources are more than half of a full install).
- Delete the installer: `Remove-Item "$env:TEMP\install-tl-windows.exe"`.

### Space safety net

If the install aborts on space, recover before retrying:

```powershell
Remove-Item "<target>\texlive\<year>" -Recurse -Force -ErrorAction SilentlyContinue
```
then ask the user for a different location.

## Post-install fixes

```powershell
$tl = "D:\Program Files\texlive\2026"
New-Item -ItemType Directory -Force -Path "$tl\texmf-var\fonts\cache" | Out-Null
& "$tl\bin\windows\mktexlsr.exe"

# packages missing from scheme-small
& "$tl\bin\windows\tlmgr.bat" -repository "https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet" `
  install titlesec parskip hyperref needspace enumitem mathtools
```

Without `texmf-var/fonts/cache`, `xelatex` dies with `Kpathsea is not working`
(`xelatex.exe : Fontconfig error: Cannot load default config file`).

## Engine choice

- **English + math only → use `pdflatex`.** It bypasses the xetex/fontconfig setup entirely
  and is faster. This covers essentially all English textbook material.
- Use `xelatex` only when CJK or raw Unicode is needed (then also `ctex`/`xeCJK` + a system font).

Compile twice so headers/refs settle:

```powershell
Push-Location <build dir>
& "$tl\bin\windows\pdflatex.exe" -interaction=nonstopmode hw.tex *> log1.txt
& "$tl\bin\windows\pdflatex.exe" -interaction=nonstopmode hw.tex *> log2.txt
Pop-Location
```

Logs written with PowerShell `*>` are **UTF-16** — read them with
`[System.IO.File]::ReadAllText(...)` before grepping.

## Missing-package diagnosis

`! LaTeX Error: File 'titlesec.sty' not found.` → `tlmgr install titlesec`.
Find every missing `.sty` in one pass by grepping the log for `^!` and `not found`.
