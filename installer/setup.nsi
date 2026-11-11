; QSO Map - Windows installer (NSIS 3)
; Copyright (c) 2026 Richard A. Hendriksen (PD3RAH) - MIT License
; Build via installer/build_installer.py (defines VERSION, STAGE, OUTFILE)
Unicode true
!include "MUI2.nsh"

Name "QSO Map ${VERSION}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\QSOMap"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\QSOMap" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=0 "ProductName" "QSO Map"
VIAddVersionKey /LANG=0 "FileDescription" "QSO Map - ADIF log on the world map - setup"
VIAddVersionKey /LANG=0 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=0 "LegalCopyright" "(c) 2026 Richard A. Hendriksen (PD3RAH) - MIT License"

!define MUI_ICON "${STAGE}\qsomap.ico"
!define MUI_UNICON "${STAGE}\qsomap.ico"
!define MUI_ABORTWARNING
!define MUI_LANGDLL_ALLLANGUAGES
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "$(RunText)"
!define MUI_FINISHPAGE_RUN_FUNCTION StartApp

!insertmacro MUI_PAGE_WELCOME
!define MUI_LICENSEPAGE_CHECKBOX
!insertmacro MUI_PAGE_LICENSE "${STAGE}\DISCLAIMER.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Dutch"

LangString RunText ${LANG_ENGLISH} "Start QSO Map now"
LangString RunText ${LANG_DUTCH} "QSO Map nu starten"
LangString Manual ${LANG_ENGLISH} "Manual"
LangString Manual ${LANG_DUTCH} "Handleiding"
LangString ManualFile ${LANG_ENGLISH} "MANUAL.html"
LangString ManualFile ${LANG_DUTCH} "HANDLEIDING.html"
LangString Uninst ${LANG_ENGLISH} "Uninstall"
LangString Uninst ${LANG_DUTCH} "Verwijderen"
LangString OpenWith ${LANG_ENGLISH} "Show on QSO Map"
LangString OpenWith ${LANG_DUTCH} "Tonen in QSO Map"

!define UK "Software\Microsoft\Windows\CurrentVersion\Uninstall\QSOMap"

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

Section "Install"
  IfSilent 0 +2
    Sleep 1500            ; automatic update: let QSO Map close first
  SetOutPath "$INSTDIR"
  RMDir /r "$INSTDIR\python"
  File /r "${STAGE}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\QSO Map.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\start.pyw"' "$INSTDIR\qsomap.ico"
  CreateDirectory "$SMPROGRAMS\QSO Map"
  CreateShortCut "$SMPROGRAMS\QSO Map\QSO Map.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\start.pyw"' "$INSTDIR\qsomap.ico"
  CreateShortCut "$SMPROGRAMS\QSO Map\$(Manual).lnk" "$INSTDIR\docs\$(ManualFile)"
  CreateShortCut "$SMPROGRAMS\QSO Map\$(Uninst).lnk" "$INSTDIR\Uninstall.exe"
  ; right-click on an .adi / .adif file -> "Show on QSO Map" (does not change the default program)
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adi\shell\QSOMap" "" "$(OpenWith)"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adi\shell\QSOMap" "Icon" "$INSTDIR\qsomap.ico"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adi\shell\QSOMap\command" "" '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw" "%1"'
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adif\shell\QSOMap" "" "$(OpenWith)"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adif\shell\QSOMap" "Icon" "$INSTDIR\qsomap.ico"
  WriteRegStr HKCU "Software\Classes\SystemFileAssociations\.adif\shell\QSOMap\command" "" '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw" "%1"'
  WriteRegStr HKCU "${UK}" "DisplayName" "QSO Map"
  WriteRegStr HKCU "${UK}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UK}" "Publisher" "PD3RAH"
  WriteRegStr HKCU "${UK}" "DisplayIcon" "$INSTDIR\qsomap.ico"
  WriteRegStr HKCU "${UK}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UK}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UK}" "NoModify" 1
  WriteRegDWORD HKCU "${UK}" "NoRepair" 1
  IfSilent 0 +3
    SetOutPath "$INSTDIR"
    Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw"'
SectionEnd

Function StartApp
  SetOutPath "$INSTDIR"
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\start.pyw"'
FunctionEnd

Function un.onInit
  !insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Section "Uninstall"
  Delete "$DESKTOP\QSO Map.lnk"
  RMDir /r "$SMPROGRAMS\QSO Map"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.adi\shell\QSOMap"
  DeleteRegKey HKCU "Software\Classes\SystemFileAssociations\.adif\shell\QSOMap"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\licenses"
  RMDir /r "$INSTDIR\docs"
  RMDir /r "$INSTDIR\__pycache__"
  Delete "$INSTDIR\qso_map.py"
  Delete "$INSTDIR\prefixes.py"
  Delete "$INSTDIR\world.json"
  Delete "$INSTDIR\start.pyw"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\DISCLAIMER.txt"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\qsomap.ico"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UK}"
  ; settings in %APPDATA%\QSOMap are kept on purpose
SectionEnd
