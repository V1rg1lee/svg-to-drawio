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
  #define MyAppSourceExe ""
#endif

#ifndef MyAppSourceDir
  #define MyAppSourceDir ""
#endif

#ifndef MyOutputDir
  #error MyOutputDir define is required.
#endif

#ifndef MyPackageArchitecture
  #define MyPackageArchitecture "x64"
#endif

#ifndef MyArchitecturesAllowed
  #define MyArchitecturesAllowed "x64compatible"
#endif

#ifndef MyArchitecturesInstallIn64BitMode
  #define MyArchitecturesInstallIn64BitMode "x64compatible"
#endif

#if MyAppSourceExe == "" && MyAppSourceDir == ""
  #error One of MyAppSourceExe or MyAppSourceDir must be defined.
#endif

#if MyAppSourceExe != "" && MyAppSourceDir != ""
  #error Define only one of MyAppSourceExe or MyAppSourceDir.
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
ArchitecturesAllowed={#MyArchitecturesAllowed}
ArchitecturesInstallIn64BitMode={#MyArchitecturesInstallIn64BitMode}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
OutputDir={#MyOutputDir}
OutputBaseFilename=svg-to-drawio-{#MyAppVersion}-windows-{#MyPackageArchitecture}-setup
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
#if MyAppSourceDir != ""
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "{#MyAppSourceExe}"; DestDir: "{app}"; Flags: ignoreversion
#endif

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

  // Only check HKLM (machine-wide) registry for security reasons.
  // Since this installer requires admin privileges (PrivilegesRequired=admin),
  // we should only trust machine-wide uninstall entries from HKLM.
  // HKCU is writable by the current user without elevation and could be
  // manipulated to execute arbitrary code with elevated privileges.

  if RegQueryStringValue(HKLM, uninstallKey, 'UninstallString', Result) then
    exit;

  Result := '';
end;

function IsValidUninstallerPath(const path: string): Boolean;
var
  cleanPath: string;
begin
  Result := False;
  cleanPath := Trim(path);
  
  // Reject empty paths
  if cleanPath = '' then
    exit;
  
  // Verify the path ends with unins000.exe or unins001.exe etc. (Inno Setup uninstallers)
  // This prevents execution of arbitrary executables
  if (Pos('unins', LowerCase(ExtractFileName(cleanPath))) = 1) and 
     (LowerCase(ExtractFileExt(cleanPath)) = '.exe') then
  begin
    // Verify the file actually exists
    if FileExists(cleanPath) then
      Result := True;
  end;
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
  
  // Validate the uninstaller path before executing with elevated privileges
  if not IsValidUninstallerPath(uninstallCommand) then
  begin
    Log('Invalid or untrusted uninstaller path detected: ' + uninstallCommand);
    // Silently skip uninstallation if path validation fails
    // This prevents privilege escalation while allowing fresh installations
    exit;
  end;
  
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
