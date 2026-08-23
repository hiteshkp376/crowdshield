import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

import '../config.dart';
import '../models/zone.dart';
import '../models/risk_reading.dart';

/// ApiService — all network calls the mobile app makes, matching the
/// exact backend endpoints already built and tested:
///   GET  {moduleA}/current-blueprint
///   GET  {moduleD}/history
///   GET  {moduleE}/all-events
///   GET  {moduleE}/alert-translations/{template_key}
///   POST {moduleE}/citizen-reports  (multipart: zone_id, latitude,
///        longitude, text_report, photo)
class ApiService {
  static const Duration _timeout = Duration(seconds: 10);

  /// Fetches the current event's venue geometry. Throws a descriptive
  /// exception on failure (caller decides how to show this to the user)
  /// rather than silently returning null -- connection problems should
  /// be visible, not hidden.
  static Future<BlueprintData> getCurrentBlueprint() async {
    final uri = Uri.parse('${ApiConfig.moduleA}/current-blueprint');
    final response = await http.get(uri).timeout(_timeout);

    if (response.statusCode == 404) {
      throw Exception(
          'No event is active yet -- the control room hasn\'t run blueprint analysis.');
    }
    if (response.statusCode != 200) {
      throw Exception('Failed to load venue data (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return BlueprintData.fromJson(body['blueprint'] as Map<String, dynamic>);
  }

  /// Fetches the full fusion-reading history and reduces it to just the
  /// LATEST reading per zone -- what the heatmap actually needs to show
  /// current risk, not the full timeline (that's the dashboard's F2 job).
  static Future<Map<String, RiskReading>> getLatestRiskPerZone() async {
    final uri = Uri.parse('${ApiConfig.moduleD}/history');
    final response = await http.get(uri).timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to load risk data (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final zonesJson = body['zones'] as Map<String, dynamic>;

    final Map<String, RiskReading> latest = {};
    zonesJson.forEach((zoneId, readingsRaw) {
      final readings = readingsRaw as List<dynamic>;
      if (readings.isNotEmpty) {
        final lastReading = readings.last as Map<String, dynamic>;
        latest[zoneId] = RiskReading.fromJson(lastReading);
      }
    });
    return latest;
  }

  static Future<List<EscalationEvent>> getAllEvents() async {
    final uri = Uri.parse('${ApiConfig.moduleE}/all-events');
    final response = await http.get(uri).timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to load alerts (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final eventsJson = body['events'] as List<dynamic>;
    return eventsJson
        .map((e) => EscalationEvent.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Fetches multilingual alert text for a given template key
  /// ("tier1_reroute", "tier2_dispersal", or "tier3_evacuate" -- see
  /// Module E's translation_layer.py). Returns a map of language code
  /// to translated text, e.g. {"en": "...", "hi": "...", "ta": "..."}.
  static Future<Map<String, String>> getAlertTranslations(
      String templateKey) async {
    final uri =
        Uri.parse('${ApiConfig.moduleE}/alert-translations/$templateKey');
    final response = await http.get(uri).timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Failed to load alert translations (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final translations = body['translations'] as Map<String, dynamic>;
    return translations.map((k, v) => MapEntry(k, v as String));
  }

  /// Submits a citizen incident report. photoFile is optional -- a
  /// text-only report (no photo) is still a valid, complete report.
  /// Uses a real multipart upload (not a fake path string) so the
  /// photo's actual bytes reach the server.
  static Future<int> submitCitizenReport({
    String? zoneId,
    double? latitude,
    double? longitude,
    String? textReport,
    File? photoFile,
  }) async {
    final uri = Uri.parse('${ApiConfig.moduleE}/citizen-reports');
    final request = http.MultipartRequest('POST', uri);

    if (zoneId != null) request.fields['zone_id'] = zoneId;
    if (latitude != null) request.fields['latitude'] = latitude.toString();
    if (longitude != null) request.fields['longitude'] = longitude.toString();
    if (textReport != null) request.fields['text_report'] = textReport;

    if (photoFile != null) {
      request.files.add(
        await http.MultipartFile.fromPath('photo', photoFile.path),
      );
    }

    final streamedResponse = await request.send().timeout(_timeout);
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode != 200) {
      throw Exception('Failed to submit report (${response.statusCode}).');
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return body['report_id'] as int;
  }
}
