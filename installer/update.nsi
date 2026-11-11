; QSO Map - small update (program files only, keeps the bundled Python)
; Used by the automatic update in QSO Map: started with /S (silent), then QSO Map restarts by itself.
; Copyright (c) 2026 Richard A. Hendriksen (PD3RAH) - MIT License
Unicode true
!include "MUI2.nsh"

Name "QSO Map ${VERSION} update"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\QSOMap"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QSOMap" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=0 "ProductName" "QSO Map"
VIAddVersionKey /LANG=0 "FileDescription" "QSO Map update"
VIAddVersionKey /LANG=0 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=0 "LegalCopyright" "(c) 2026 Richard A. Hendriksen (PD3RAH) - MIT License"
!define MUI_ICON "${STAGE}\qsomap.ico"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_FUNCTION StartApp
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Dutch"

Function .onVerifyInstDir
  IfFileExists "$INSTDIR\python\pythonw.exe" +2
    Abort
FunctionEnd

Function .onInit
  ; an update needs an existing installation
  IfFileExists "$INSTDIR\python\pythonw.exe" +3
    MessageBox MB_ICONSTOP "QSO Map is not installed. Please use QSOMap-Setup-${VERSION}.exe." /SD IDOK
    Abort
FunctionEnd

Section "Update"
  IfSilent 0 +2
    Sleep 1500            ; let QSO Map close first
  SetOutPath "$INSTDIR"
  File "${STAGE}\qso_map.py"
  File "${STAGE}\prefixes.py"
  File "${STAGE}\world.json"
  File "${STAGE}\start.pyw"
  File "${STAGE}\qsomap.ico"
  File "${STAGE}\README.md"
  File "${STAGE}\LICENSE"
  File "${STAGE}\DISCLAIMER.txt"
  File "${STAGE}\THIRD_PARTY_NOTICES.md"
  SetOutPath "$INSTDIR\docs"
  File "${STAGE}\docs\*.*"
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\__pycache__"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QSOMap" "DisplayVersion" "${VERSION}"
  IfSilent 0 +2
    Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw"'
SectionEnd

Function StartApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw"'
FunctionEnd
