; Inno Setup script — CalcoliImmobile
; Richiede Inno Setup 6+: https://jrsoftware.org/isinfo.php

[Setup]
AppName=Calcoli Immobile
AppVersion=1.0
AppPublisher=Giuseppe
DefaultDirName={autopf}\CalcoliImmobile
DefaultGroupName=Calcoli Immobile
OutputDir=installer_out
OutputBaseFilename=Setup_CalcoliImmobile
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
; UninstallDisplayIcon={app}\CalcoliImmobile.exe

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un'icona sul {cm:DesktopName}"; GroupDescription: "Icone aggiuntive:"

[Files]
Source: "dist\CalcoliImmobile.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Calcoli Immobile";    DestPath: "{app}\CalcoliImmobile.exe"
Name: "{autodesktop}\Calcoli Immobile"; DestPath: "{app}\CalcoliImmobile.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CalcoliImmobile.exe"; Description: "Avvia Calcoli Immobile"; Flags: nowait postinstall skipifsilent
