# Build: Windows, macOS, Linux, and Android

The root `main.py` and `pyproject.toml` configure Flet 1.0.4, the bundled reference catalogs, existing icons, version 1.0.0/build 1, and application ID `io.github.angelomega7.zoids_character_app`. Packaged dependencies use plain `flet`; desktop development tooling stays in the local virtual environment.

## Windows builds with GitHub Actions

The workflow in `.github/workflows/build-windows.yml` builds the Windows x64 app on GitHub's `windows-2022` runner using Python 3.12 and Flet 1.0.4. The runner provides Visual Studio; Flet downloads its required Flutter SDK automatically.

1. Commit and push the workflow to GitHub. Builds run for pushes to the default branch (`main`), except pushes that change only the root `README.txt`.
2. To build manually, open the repository's **Actions** tab, select **Build Windows**, and choose **Run workflow**. The workflow must first be present on the default branch for this button to appear.
3. Open a successful run and download `zoids-character-app-windows-x64-<run number>` under **Artifacts**. Artifacts are retained for 30 days.
4. Extract the entire downloaded ZIP on Windows and launch the `.exe` inside. Keep all bundled DLLs and data alongside it.

This produces a portable app bundle, not a setup installer. Successful builds on `main` also replace `zoids-character-app-windows-x64.zip` in the existing `windows` release. No repository secrets are needed: publishing uses the automatic `GITHUB_TOKEN` with `contents: write`. Check the **Build Windows app** step's log if compilation fails.

## macOS builds with GitHub Actions

The workflow in `.github/workflows/build-macos.yml` uses GitHub's `macos-15` runner, Python 3.12, and Flet 1.0.4 to build a universal `.app` for Apple Silicon and Intel Macs. It uses the same push and manual triggers as the Windows workflow. Successful builds on `main` replace `zoids-character-app-macos-universal.zip` in the existing `macOS` release; release downloads need only one extraction.

The workflow selects Xcode 26.3 using `DEVELOPER_DIR` and logs the selected Xcode and SDK versions. The `connectivity_plus` dependency requires the macOS 26 SDK for `NWPath.isUltraConstrained`; the runner's default Xcode 16.4/macOS 15.5 SDK cannot compile it. This selects the build SDK, not the app's minimum supported macOS version.

1. Commit and push the workflow. For a manual build, select **Actions → Build macOS → Run workflow** once it is on the default branch.
2. Download `zoids-character-app-macos-universal-<run number>` from a successful run's **Artifacts** (retained for 30 days).
3. Extract the artifact ZIP, then open the enclosed `zoids-character-app-macos-universal.zip` on a Mac to extract the `.app`. The inner archive preserves executable permissions and bundle symlinks.
4. Move the `.app` to **Applications** and launch it.

No repository secrets are required. The app uses the default ad-hoc signing and is not notarized; macOS may block downloaded builds. For a trusted test build, use **System Settings → Privacy & Security → Open Anyway** if offered. Public distribution with normal Gatekeeper approval requires an Apple Developer ID certificate and notarization credentials, which are not configured by this workflow. Successful compilation and launch still need verification on macOS.

## Linux builds with GitHub Actions

The workflow in `.github/workflows/build-linux.yml` builds a portable x64 bundle on `ubuntu-22.04` using Python 3.12 and Flet 1.0.4. It installs the Linux native build dependencies and uses the same push and manual triggers as Windows and macOS.

Successful builds on `main` replace `zoids-character-app-linux-x64.tar.gz` in the existing `linux` release. Download it, extract it into a folder with `tar -xzf zoids-character-app-linux-x64.tar.gz -C <folder>`, and run the executable inside while keeping all bundled files together. The tar archive preserves executable permissions and symlinks. The target Linux system needs compatible GTK 3 and libsecret runtime libraries; this is not a `.deb` installer. A copy is retained in Actions artifacts for 30 days.

## Automatic release updates

All three workflows publish only from `main`, including manual runs. Each uploads its new fixed-name asset before removing the old run-numbered Windows/macOS assets or original `linux.zip`. Future runs replace the fixed-name asset. Existing release titles, notes, and tags are preserved; source-code archives still refer to the original tagged commit. Release tags must already exist (`windows`, `macOS`, and `linux`).

A push containing both `README.txt` and another changed file still builds. New pushes cancel older in-progress builds for the same platform and branch. If the default branch is renamed, update the branch filters and publishing conditions in all three workflows.

## One-time local prerequisites (Windows and Android)

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
