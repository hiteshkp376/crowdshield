/// zone.dart — mirrors Module A's per-zone output fields exactly
/// (see module_a/blueprint_pipeline.py's analyze_blueprint() return
/// shape, already tested extensively in the backend).
class Zone {
  final String zoneId;
  final double areaM2;
  final List<List<double>> contourPx; // list of [x, y] points
  final bool isChokepoint;
  final bool isVipCorridor;
  final List<String> symbolsPresent;

  Zone({
    required this.zoneId,
    required this.areaM2,
    required this.contourPx,
    required this.isChokepoint,
    required this.isVipCorridor,
    required this.symbolsPresent,
  });

  factory Zone.fromJson(Map<String, dynamic> json) {
    final rawContour = json['contour_px'] as List<dynamic>;
    final points = rawContour.map<List<double>>((p) {
      final pair = p as List<dynamic>;
      return [(pair[0] as num).toDouble(), (pair[1] as num).toDouble()];
    }).toList();

    final rawSymbols = json['symbols_present'] as List<dynamic>? ?? [];

    return Zone(
      zoneId: json['zone_id'] as String,
      areaM2: (json['area_m2'] as num).toDouble(),
      contourPx: points,
      isChokepoint: json['is_chokepoint'] as bool? ?? false,
      isVipCorridor: json['is_vip_corridor'] as bool? ?? false,
      symbolsPresent: rawSymbols.map((s) => s as String).toList(),
    );
  }
}

/// BlueprintData — the full venue geometry payload from
/// GET /current-blueprint (Module A).
class BlueprintData {
  final int imageWidthPx;
  final int imageHeightPx;
  final double scaleMPerPx;
  final double totalAreaM2;
  final double readinessScorePct;
  final String riskLevel;
  final List<Zone> zones;

  BlueprintData({
    required this.imageWidthPx,
    required this.imageHeightPx,
    required this.scaleMPerPx,
    required this.totalAreaM2,
    required this.readinessScorePct,
    required this.riskLevel,
    required this.zones,
  });

  factory BlueprintData.fromJson(Map<String, dynamic> json) {
    final rawZones = json['zones'] as List<dynamic>;
    return BlueprintData(
      imageWidthPx: json['image_width_px'] as int,
      imageHeightPx: json['image_height_px'] as int,
      scaleMPerPx: (json['scale_m_per_px'] as num).toDouble(),
      totalAreaM2: (json['total_area_m2'] as num).toDouble(),
      readinessScorePct: (json['readiness_score_pct'] as num).toDouble(),
      riskLevel: json['risk_level'] as String,
      zones: rawZones
          .map((z) => Zone.fromJson(z as Map<String, dynamic>))
          .toList(),
    );
  }
}
