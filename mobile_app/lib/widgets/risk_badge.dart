import 'package:flutter/material.dart';
import 'venue_map_painter.dart';

class RiskBadge extends StatelessWidget {
  final String tier;
  final double? score;

  const RiskBadge({super.key, required this.tier, this.score});

  @override
  Widget build(BuildContext context) {
    final color = colorForTier(tier);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.18),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color, width: 1),
      ),
      child: Text(
        score != null ? '$tier · ${score!.toStringAsFixed(0)}' : tier,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
