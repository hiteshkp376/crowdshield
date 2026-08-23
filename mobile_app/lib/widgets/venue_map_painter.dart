import 'package:flutter/material.dart';
import '../models/zone.dart';
import '../models/risk_reading.dart';

const Map<String, Color> tierColors = {
  'Green': Color(0xFF4ADE80),
  'Tier 1 - Yellow': Color(0xFFFBBF24),
  'Tier 2 - Red': Color(0xFFF87171),
  'Tier 3 - Active': Color(0xFFEF4444),
};

Color colorForTier(String? tier) {
  return tierColors[tier] ?? tierColors['Green']!;
}

/// VenueMapPainter — draws each zone's real polygon geometry (from
/// Module A's contour_px, the exact same data the React dashboard's
/// SVG rendering uses), colored by that zone's current risk tier,
/// scaled to fit the available canvas while preserving aspect ratio.
class VenueMapPainter extends CustomPainter {
  final List<Zone> zones;
  final Map<String, RiskReading> riskByZone;
  final int imageWidthPx;
  final int imageHeightPx;

  VenueMapPainter({
    required this.zones,
    required this.riskByZone,
    required this.imageWidthPx,
    required this.imageHeightPx,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (imageWidthPx == 0 || imageHeightPx == 0) return;

    // Fit the venue's native pixel dimensions into the available canvas
    // size while preserving aspect ratio (same "contain" behavior as
    // the dashboard's SVG preserveAspectRatio="xMidYMid meet").
    final scaleX = size.width / imageWidthPx;
    final scaleY = size.height / imageHeightPx;
    final scale = scaleX < scaleY ? scaleX : scaleY;

    final scaledWidth = imageWidthPx * scale;
    final scaledHeight = imageHeightPx * scale;
    final offsetX = (size.width - scaledWidth) / 2;
    final offsetY = (size.height - scaledHeight) / 2;

    Offset toCanvas(double x, double y) {
      return Offset(offsetX + x * scale, offsetY + y * scale);
    }

    for (final zone in zones) {
      if (zone.contourPx.isEmpty) continue;

      final reading = riskByZone[zone.zoneId];
      final color = colorForTier(reading?.tier);

      final path = Path();
      final first = zone.contourPx.first;
      path.moveTo(toCanvas(first[0], first[1]).dx, toCanvas(first[0], first[1]).dy);
      for (int i = 1; i < zone.contourPx.length; i++) {
        final p = zone.contourPx[i];
        final canvasPoint = toCanvas(p[0], p[1]);
        path.lineTo(canvasPoint.dx, canvasPoint.dy);
      }
      path.close();

      final fillPaint = Paint()
        ..color = color.withOpacity(0.28)
        ..style = PaintingStyle.fill;
      canvas.drawPath(path, fillPaint);

      final strokePaint = Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5;
      canvas.drawPath(path, strokePaint);

      // Zone label + score at centroid
      double cx = 0, cy = 0;
      for (final p in zone.contourPx) {
        cx += p[0];
        cy += p[1];
      }
      cx /= zone.contourPx.length;
      cy /= zone.contourPx.length;
      final centroidCanvas = toCanvas(cx, cy);

      final labelText = reading != null
          ? '${zone.zoneId}\n${reading.compositeRiskScore.toStringAsFixed(0)}'
          : zone.zoneId;

      final textPainter = TextPainter(
        text: TextSpan(
          text: labelText,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.w600,
            height: 1.3,
          ),
        ),
        textAlign: TextAlign.center,
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(
        canvas,
        Offset(centroidCanvas.dx - textPainter.width / 2,
            centroidCanvas.dy - textPainter.height / 2),
      );
    }
  }

  @override
  bool shouldRepaint(covariant VenueMapPainter oldDelegate) {
    return oldDelegate.riskByZone != riskByZone || oldDelegate.zones != zones;
  }
}
