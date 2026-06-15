#define MyAppName "SVG to draw.io"
#define MyAppPublisher "V1rg1lee"
#define MyAppURL "https://github.com/V1rg1lee/svg-to-drawio"
#define MyAppExeName "svg-to-drawio.exe"
#define MyAppId "{{A93E1B2F-7F09-4FE5-A3B7-0A9390D8D0D5}}"
#define MyAppRegistryId "{A93E1B2F-7F09-4FE5-A3B7-0A9390D8D0D5}"

#ifndef MyAppVersion
  #error MyAppVersion define is required.
#endif

#ifndef MyAppSourceExe
  #error MyAppSourceExe define is required.
#endif

#ifndef MyOutputDir
  #error MyOutputDir define is required.
#endif

#ifndef MyLicenseFile
  #define MyLicenseFile ""
#endif

#ifndef MySetupIconFile
  #define MySetupIconFile ""
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\SVG to draw.io
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyOutputDir}
OutputBaseFilename=svg-to-drawio-{#MyAppVersion}-setup
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
#if MyLicenseFile != ""
LicenseFile={#MyLicenseFile}
#endif
#if MySetupIconFile != ""
SetupIconFile={#MySetupIconFile}
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#MyAppSourceExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function GetPreviousUninstallString(): string;
var
  uninstallKey: string;
begin
  uninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppRegistryId}_is1';

  if RegQueryStringValue(HKLM, uninstallKey, 'UninstallString', Result) then
    exit;

  if RegQueryStringValue(HKCU, uninstallKey, 'UninstallString', Result) then
    exit;

  Result := '';
end;

function UninstallPreviousVersion(): Boolean;
var
  uninstallCommand: string;
  resultCode: Integer;
begin
  Result := True;
  uninstallCommand := GetPreviousUninstallString();

  if uninstallCommand = '' then
    exit;

  uninstallCommand := RemoveQuotes(uninstallCommand);
  Log('Removing previous version with command: ' + uninstallCommand);

  if not Exec(
    uninstallCommand,
    '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    resultCode
  ) then
  begin
    SuppressibleMsgBox(
      'Setup could not remove the previous installed version automatically.' + #13#10 +
      'Please uninstall it manually and run this installer again.',
      mbCriticalError,
      MB_OK,
      IDOK
    );
    Result := False;
    exit;
  end;

  if resultCode <> 0 then
  begin
    SuppressibleMsgBox(
      'The previous installed version did not uninstall cleanly.' + #13#10 +
      'Please uninstall it manually and run this installer again.',
      mbCriticalError,
      MB_OK,
      IDOK
    );
    Result := False;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := UninstallPreviousVersion();
end;
