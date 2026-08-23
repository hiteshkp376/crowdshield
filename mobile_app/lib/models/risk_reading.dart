/// risk_reading.dart — mirrors Module D's /history response shape and
/// Module E's escalation event shape (both already tested extensively
/// in the backend).

class RiskReading {
  final String tier;
  final double compositeRiskScore;
  final DateTime timestamp;

  RiskReading({
    required this.tier,
    required this.compositeRiskScore,
    required this.timestamp,
  });

  factory RiskReading.fromJson(Map<String, dynamic> json) {
    return RiskReading(
      tier: json['tier'] as String,
      compositeRiskScore: (json['composite_risk_score'] as num).toDouble(),
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}

class EscalationEvent {
  final String eventId;
  final String zoneId;
  final String tier;
  final double compositeRiskScore;
  final String dispatchStatus;
  final DateTime createdAt;

  EscalationEvent({
    required this.eventId,
    required this.zoneId,
    required this.tier,
    required this.compositeRiskScore,
    required this.dispatchStatus,
    required this.createdAt,
  });

  factory EscalationEvent.fromJson(Map<String, dynamic> json) {
    return EscalationEvent(
      eventId: json['event_id'] as String,
      zoneId: json['zone_id'] as String,
      tier: json['tier'] as String,
      compositeRiskScore: (json['composite_risk_score'] as num).toDouble(),
      dispatchStatus: json['dispatch_status'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
