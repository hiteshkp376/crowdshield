import 'dart:async';
import 'package:flutter/material.dart';

import '../models/zone.dart';
import '../models/risk_reading.dart';
import '../services/api_service.dart';
import '../widgets/venue_map_painter.dart';
import '../widgets/risk_badge.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  BlueprintData? _blueprint;
  Map<String, RiskReading> _riskByZone = {};
  bool _loading = true;
  String? _errorMessage;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadData();
    // Auto-refresh every 15 seconds so attendees see updated risk
    // without needing to manually pull-to-refresh constantly.
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      _loadData(silent: true);
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadData({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _errorMessage = null;
      });
    }
    try {
      final results = await Future.wait([
        ApiService.getCurrentBlueprint(),
        ApiService.getLatestRiskPerZone(),
      ]);
      final blueprint = results[0] as BlueprintData;
      final risk = results[1] as Map<String, RiskReading>;
      if (!mounted) return;
      setState(() {
        _blueprint = blueprint;
        _riskByZone = risk;
        _loading = false;
        _errorMessage = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _errorMessage = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CrowdShield'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadData(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _loadData(),
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _blueprint == null) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _blueprint == null) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Icon(Icons.wifi_off, size: 48, color: Colors.grey[500]),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              _errorMessage!,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey[600]),
            ),
          ),
          const SizedBox(height: 16),
          Center(
            child: ElevatedButton(
              onPressed: () => _loadData(),
              child: const Text('Retry'),
            ),
          ),
        ],
      );
    }

    final blueprint = _blueprint!;

    return ListView(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${blueprint.totalAreaM2.toStringAsFixed(0)} m² venue',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              RiskBadge(tier: blueprint.riskLevel),
            ],
          ),
        ),
        AspectRatio(
          aspectRatio: blueprint.imageWidthPx / blueprint.imageHeightPx,
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: const Color(0xFF0F1E2E),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF24435C)),
            ),
            child: CustomPaint(
              painter: VenueMapPainter(
                zones: blueprint.zones,
                riskByZone: _riskByZone,
                imageWidthPx: blueprint.imageWidthPx,
                imageHeightPx: blueprint.imageHeightPx,
              ),
              child: Container(),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            'Zones',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        ...blueprint.zones.map((zone) {
          final reading = _riskByZone[zone.zoneId];
          return ListTile(
            title: Text(zone.zoneId),
            subtitle: Text(
              zone.symbolsPresent.isNotEmpty
                  ? zone.symbolsPresent.join(', ')
                  : '${zone.areaM2.toStringAsFixed(0)} m²',
            ),
            trailing: RiskBadge(
              tier: reading?.tier ?? 'Green',
              score: reading?.compositeRiskScore,
            ),
          );
        }),
        const SizedBox(height: 32),
      ],
    );
  }
}
