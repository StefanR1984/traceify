; Inno-Setup-Skript für Traceify (Windows x64)
; Aufruf aus dem Projektordner, nach dem PyInstaller-Build:
;   iscc /DAppVersion=0.3.0 packaging\windows\traceify.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E0B6A57-4C1C-4F5E-9F31-2B7C1D8A9E42}
AppName=Traceify
AppVersion={#AppVersion}
AppVerName=Traceify {#AppVersion}
AppPublisher=Traceify-Projekt
AppPublisherURL=https://github.com/StefanR1984/traceify
AppSupportURL=https://github.com/StefanR1984/traceify/issues
AppUpdatesURL=https://github.com/StefanR1984/traceify/releases
DefaultDirName={autopf}\Traceify
DefaultGroupName=Traceify
DisableProgramGroupPage=yes
; Standard: Installation nur für den aktuellen Benutzer (ohne Administratorrechte),
; im Dialog wählbar: für alle Benutzer
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\..\LICENSE
SetupIconFile=..\..\traceify\assets\traceify.ico
UninstallDisplayIcon={app}\Traceify.exe
OutputDir=..\..\dist
OutputBaseFilename=Traceify-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ChangesAssociations=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\Traceify\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Traceify"; Filename: "{app}\Traceify.exe"
Name: "{autodesktop}\Traceify"; Filename: "{app}\Traceify.exe"; Tasks: desktopicon

[Registry]
; „Öffnen mit → Traceify“ für Bilder und PDFs
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "Traceify"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Traceify.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".png"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".jpg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".jpeg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".tif"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".tiff"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".bmp"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\Traceify.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""

[Run]
Filename: "{app}\Traceify.exe"; Description: "{cm:LaunchProgram,Traceify}"; Flags: nowait postinstall skipifsilent
