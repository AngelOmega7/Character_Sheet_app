# Build locally: Windows and Android

The root `main.py` and `pyproject.toml` configure Flet 1.0.4, the bundled reference catalogs, existing icons, version 1.0.0/build 1, and application ID `io.github.angelomega7.zoids_character_app`. Packaged dependencies use plain `flet`; desktop development tooling stays in the local virtual environment.

## One-time prerequisites

- Windows build: install Visual Studio 2022 or 2026 with **Desktop development with C++**, including its recommended Windows SDK components. Enable Windows Developer Mode for Flutter plugin symlinks.
- Both targets need Flutter. Flet installs the required version if it is not available.
- Android additionally needs JDK 17 and the Android SDK. Flet can install these automatically on the first Android build, or use an existing Android Studio SDK.
- Initial setup/builds require internet and can download substantial toolchains. The installed app itself remains offline.

## PowerShell commands

```powershell
Set-Location "C:\Zoids\Zoids TTRPG\Repo\zoids-character-app"

# Only needed if the virtual environment does not exist:
if (-not (Test-Path ".\.venv\Scripts\python.exe")) { py -m venv .venv }

.\.venv\Scripts\python -m pip install "flet[cli,desktop]==1.0.4"
.\.venv\Scripts\flet.exe --version

# Build Windows:
.\.venv\Scripts\flet.exe build windows --verbose

# Build an Android APK for direct installation:
.\.venv\Scripts\flet.exe build apk --verbose
```

If Windows reports missing symlink support, open Developer Mode settings:

```powershell
Start-Process "ms-settings:developers"
```

## Outputs and installation

- **Windows:** `build/windows/`. Run the generated `.exe` inside that folder. Distribute the entire folder (for example as a ZIP), including its DLLs and data; this command produces an application bundle, not a setup installer.
- **Android:** `build/apk/`. Copy the generated `.apk` to the phone, open it, and allow installation from that source when Android asks. Alternatively, use `adb install -r <path-to-apk>` with a connected device.
- The APK uses a debug signing key unless a release keystore is configured. This is suitable for local testing. For Play Store distribution, configure a private release/upload keystore and build an AAB with `flet build aab` following Flet's signing guide. Retain the signing key for future updates.

Increase `[tool.flet].build_number` for subsequent Android releases and update `[project].version` as appropriate. Keep the application ID stable across updates.

## Data and checking the packages

Runtime JSON is bundled under `zoids_app/data`; saves are created in the platform application-support directory, never inside the build output. A packaged app can have a different save location from the development app; the editor shows the actual database path. Builds do not automatically transfer development saves or transfer characters between Windows and Android.

After installation, test startup offline, starter purchasing, saving/reopening, and combat actions on each platform. Android OS termination can bypass a desktop-style close prompt, so use **Save character** explicitly before leaving the app. These build configurations have been prepared, but successful platform compilation and device execution still need local verification.

Official references: [Flet packaging](https://docs.flet.dev/publish/), [Windows](https://docs.flet.dev/publish/windows/), [Android and signing](https://docs.flet.dev/publish/android/).
