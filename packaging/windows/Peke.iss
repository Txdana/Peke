#define AppName "Peke"
#define AppPublisher "Txdana"
#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif
#define AppExeName "Peke.exe"

[Setup]
AppId={{F3B87F4B-5D6A-4A42-9F0C-3E7E1B2C8A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Peke
DefaultGroupName=Peke
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist-installer
OutputBaseFilename=Peke-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\Peke.exe
CloseApplications=yes
CloseApplicationsFilter=*.exe,*.dll
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\Peke\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\..\NOTICE"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Peke"; Filename: "{app}\Peke.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Peke"; Filename: "{app}\Peke.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Peke.exe"; Description: "Launch Peke"; Flags: postinstall nowait skipifsilent
