# CrowdShield — Mobile App (Flutter)

Attendee-facing app: live venue heatmap, SOS, incident reporting (photo
+ text + GPS), and multilingual alert viewing.

## IMPORTANT — read this before anything else

**I could not compile or run this Flutter app.** This sandbox's network
restrictions block downloading the Dart SDK (`storage.googleapis.com`
isn't reachable here), so there was no `flutter analyze` or `flutter
run` possible on my end -- unlike every other part of this project,
which I tested directly.

What I DID do to compensate:
- Manually traced every file's braces/parens/brackets for balance
- Cross-checked every class name, import path, and function signature
  across all 10 files for consistency
- Verified every JSON field name this app reads against the **actual
  tested output** of the real backend (Modules A/D/E), from curl tests
  run earlier in this build -- not guessed field names
- Used only long-stable, well-established Flutter/Dart APIs, avoiding
  anything recently changed (e.g. explicitly used `.withOpacity()`
  instead of the newer `.withValues()`, which would fail on slightly
  older Flutter installs)

**Your first step must be `flutter analyze`** (see below) -- it catches
syntax/type errors without needing an emulator. If it reports anything,
send it to me and we'll fix it immediately, the same way we debugged
everything else in this project together.

## Setup

**1. Install Flutter** (if you haven't): https://docs.flutter.dev/get-started/install/windows
Run `flutter doctor` afterward and resolve anything it flags.

**2. Create the platform scaffolding** (Android/iOS project files this
package doesn't include -- `flutter create` generates these correctly
for whatever Flutter version you have, which is safer than me hand
writing platform-specific Gradle/XML):

```cmd
cd mobile_app
flutter create .
```

This may overwrite `pubspec.yaml` with a fresh template -- **re-paste
the `pubspec.yaml` I gave you back over it afterward** to restore the
actual dependencies this app needs.

**3. Add required permissions** (the app will fail at runtime without
these, even though the Dart code is correct):

**Android** -- open `android/app/src/main/AndroidManifest.xml`, add
these lines inside the `<manifest>` tag, above `<application>`:
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
<uses-permission android:name="android.permission.CAMERA"/>
```

**iOS** -- open `ios/Runner/Info.plist`, add these before the final
`</dict>`:
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>CrowdShield uses your location to send it with SOS and incident reports.</string>
<key>NSCameraUsageDescription</key>
<string>CrowdShield uses the camera to attach photos to incident reports.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>CrowdShield needs photo library access to attach an existing photo to a report.</string>
```

**4. Install dependencies:**
```cmd
flutter pub get
```

**5. Run the syntax check FIRST, before trying to launch the app:**
```cmd
flutter analyze
```
If this reports errors, stop here and send them to me.

## CRITICAL — networking config

Open `lib/config.dart` and set `baseHost` to match how you're running
the app -- this is a genuine, common Flutter gotcha (explained in full
in the file's comments):

- **Android emulator:** `10.0.2.2` (the default already set)
- **iOS Simulator:** `localhost` or `127.0.0.1`
- **Physical phone** (same WiFi as your PC): your computer's LAN IP,
  find it via `ipconfig` on Windows -> "IPv4 Address"

Get this wrong and every screen will show a connection error even
though the code is correct.

## Run

All 6 backend servers need to be running first (same as the dashboard),
plus the dashboard's "RUN FULL ANALYSIS" step needs to have completed
at least once, so `GET /current-blueprint` (Module A) has real data to
serve.

```cmd
flutter run
```

Select your target device/emulator when prompted.

## What's real vs. what needed a backend fix along the way

- **Photo upload is genuinely real** -- while building this, I found
  Module E's `/citizen-reports` endpoint only accepted a text *path*
  string for a photo, not an actual file. Fixed it to accept a real
  multipart upload (tested: confirmed actual photo bytes save to disk
  correctly on the server).
- **`GET /current-blueprint`** is a new Module A endpoint added
  specifically for this app -- previously, blueprint data only lived
  in the dashboard's browser memory, with no way for a separate mobile
  client to fetch "what does the venue look like right now." Tested:
  confirmed 404 before any analysis, 200 with correct data after.
- **Multilingual alerts** reuse Module E's existing curated phrasebook
  (see Module E's own README for the honesty note: Hindi/Tamil entries
  are first-pass, not yet verified by a native speaker).

## Known limitations

- No push notifications -- alerts require opening the Alerts tab and
  refreshing (or waiting for the 15-second auto-refresh on the Venue
  tab). Real push notifications would need a service like Firebase
  Cloud Messaging (per the master brief's stack), not built here.
- Zone selection in the report form is a free-text field (type "Z1"),
  not a dropdown populated from live zone data -- kept simple to avoid
  extra cross-screen state coupling.
- No offline queueing -- if the phone loses connectivity mid-submit,
  the report fails with an error rather than queuing for later retry.

## Files

- `lib/main.dart` -- app entry, bottom navigation shell
- `lib/config.dart` -- backend URLs (edit `baseHost` per the note above)
- `lib/models/` -- data models matching tested backend JSON exactly
- `lib/services/api_service.dart` -- all backend HTTP calls
- `lib/widgets/venue_map_painter.dart` -- heatmap rendering (CustomPainter)
- `lib/widgets/risk_badge.dart` -- reusable tier-colored badge
- `lib/screens/home_screen.dart` -- venue heatmap, auto-refreshing
- `lib/screens/report_screen.dart` -- SOS + full incident report form
- `lib/screens/alerts_screen.dart` -- escalation events + translations
