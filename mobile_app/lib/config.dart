/// config.dart — backend connection settings.
///
/// IMPORTANT — READ BEFORE RUNNING (a genuinely common Flutter gotcha,
/// not specific to this app): "localhost" means something different
/// depending on where the app is actually running:
///
///   - Android EMULATOR:  use 10.0.2.2  (a special alias the emulator
///     maps to your host machine's localhost -- "localhost" from INSIDE
///     the emulator refers to the emulator itself, not your PC)
///   - iOS Simulator:     "localhost" / 127.0.0.1 works directly
///   - Physical phone (Android or iOS), connected via USB or same WiFi:
///     use your computer's actual LAN IP address (e.g. 192.168.1.23),
///     find it on Windows via `ipconfig` -> "IPv4 Address"
///   - Flutter Web (`flutter run -d chrome`):
///     "localhost" works directly, same as a normal browser
///
/// Set BASE_HOST below to match whichever of these applies to how
/// you're running the app. Get this wrong and every screen will show
/// a connection error even though the code itself is correct.
library;

class ApiConfig {
  // CHANGE THIS to match your run target -- see the notes above.
  static const String baseHost = "10.0.2.2"; // default: Android emulator

  static const int moduleAPort = 8001; // Blueprint Intelligence
  static const int moduleDPort = 8004; // Live Fusion Detection
  static const int moduleEPort = 8005; // Escalation & Response

  static String get moduleA => "http://$baseHost:$moduleAPort";
  static String get moduleD => "http://$baseHost:$moduleDPort";
  static String get moduleE => "http://$baseHost:$moduleEPort";
}
