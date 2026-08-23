import 'package:flutter/material.dart';

import '../models/risk_reading.dart';
import '../services/api_service.dart';
import '../widgets/risk_badge.dart';

/// Maps an escalation tier to Module E's phrasebook template key --
/// same mapping the dashboard uses (see module_e/main.py's
/// _TIER_TO_TEMPLATE). Green has no dispatch template.
String? _templateKeyForTier(String tier) {
  switch (tier) {
    case 'Tier 1 - Yellow':
      return 'tier1_reroute';
    case 'Tier 2 - Red':
      return 'tier2_dispersal';
    case 'Tier 3 - Active':
      return 'tier3_evacuate';
    default:
      return null;
  }
}

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<EscalationEvent> _events = [];
  bool _loading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final events = await ApiService.getAllEvents();
      events.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      if (!mounted) return;
      setState(() {
        _events = events;
        _loading = false;
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
        title: const Text('Alerts'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadEvents),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadEvents,
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _events.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _events.isEmpty) {
      return ListView(
        children: [
          const SizedBox(height: 100),
          Icon(Icons.wifi_off, size: 48, color: Colors.grey[500]),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(_errorMessage!,
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600])),
          ),
        ],
      );
    }

    if (_events.isEmpty) {
      return ListView(
        children: const [
          SizedBox(height: 100),
          Center(child: Text('No alerts yet.')),
        ],
      );
    }

    return ListView.builder(
      itemCount: _events.length,
      itemBuilder: (context, index) {
        final event = _events[index];
        final templateKey = _templateKeyForTier(event.tier);

        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: ExpansionTile(
            title: Row(
              children: [
                Expanded(child: Text('Zone ${event.zoneId}')),
                RiskBadge(tier: event.tier, score: event.compositeRiskScore),
              ],
            ),
            subtitle: Text(
              '${event.createdAt.toLocal()} · ${event.dispatchStatus}',
              style: const TextStyle(fontSize: 12),
            ),
            children: [
              if (templateKey != null)
                _AlertTranslations(templateKey: templateKey)
              else
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No dispatch alert for this tier.'),
                ),
            ],
          ),
        );
      },
    );
  }
}

/// Loads and displays multilingual alert text for a tier's template --
/// only fetched when the ExpansionTile is actually opened, not upfront
/// for every event in the list.
class _AlertTranslations extends StatefulWidget {
  final String templateKey;
  const _AlertTranslations({required this.templateKey});

  @override
  State<_AlertTranslations> createState() => _AlertTranslationsState();
}

class _AlertTranslationsState extends State<_AlertTranslations> {
  Map<String, String>? _translations;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final result = await ApiService.getAlertTranslations(widget.templateKey);
      if (!mounted) return;
      setState(() => _translations = result);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Text(_error!, style: const TextStyle(color: Colors.red)),
      );
    }
    if (_translations == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: _translations!.entries.map((entry) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(entry.key.toUpperCase(),
                    style: const TextStyle(
                        fontSize: 11, fontWeight: FontWeight.bold, color: Colors.grey)),
                Text(entry.value),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}
