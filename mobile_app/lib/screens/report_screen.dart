import 'dart:io';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_service.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final TextEditingController _zoneController = TextEditingController();
  final TextEditingController _textController = TextEditingController();
  File? _photo;
  bool _submitting = false;
  bool _sosSubmitting = false;

  @override
  void dispose() {
    _zoneController.dispose();
    _textController.dispose();
    super.dispose();
  }

  /// Requests location permission and returns the current position.
  /// Throws a descriptive exception on any failure rather than silently
  /// returning null -- the caller shows this to the user directly.
  Future<Position> _getCurrentLocation() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw Exception('Location services are turned off on this device.');
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        throw Exception('Location permission was denied.');
      }
    }
    if (permission == LocationPermission.deniedForever) {
      throw Exception(
          'Location permission is permanently denied. Enable it in system settings.');
    }

    return Geolocator.getCurrentPosition();
  }

  Future<void> _pickPhoto(ImageSource source) async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(source: source, imageQuality: 70);
    if (picked != null) {
      setState(() {
        _photo = File(picked.path);
      });
    }
  }

  Future<void> _submitSos() async {
    setState(() => _sosSubmitting = true);
    try {
      final position = await _getCurrentLocation();
      final reportId = await ApiService.submitCitizenReport(
        latitude: position.latitude,
        longitude: position.longitude,
        textReport: 'SOS -- immediate assistance needed',
        zoneId: _zoneController.text.trim().isEmpty
            ? null
            : _zoneController.text.trim(),
      );
      if (!mounted) return;
      _showConfirmation(
          'SOS sent (report #$reportId). Your location has been shared with the control room.');
    } catch (e) {
      if (!mounted) return;
      _showError('Could not send SOS: $e');
    } finally {
      if (mounted) setState(() => _sosSubmitting = false);
    }
  }

  Future<void> _submitFullReport() async {
    if (_textController.text.trim().isEmpty && _photo == null) {
      _showError('Add a description or a photo before submitting.');
      return;
    }

    setState(() => _submitting = true);
    try {
      double? lat, lon;
      try {
        final position = await _getCurrentLocation();
        lat = position.latitude;
        lon = position.longitude;
      } catch (_) {
        // Location is best-effort for the full report -- a report
        // without GPS is still useful, so we don't block submission
        // on it (unlike SOS, where location is the whole point).
      }

      final reportId = await ApiService.submitCitizenReport(
        zoneId: _zoneController.text.trim().isEmpty
            ? null
            : _zoneController.text.trim(),
        latitude: lat,
        longitude: lon,
        textReport: _textController.text.trim().isEmpty
            ? null
            : _textController.text.trim(),
        photoFile: _photo,
      );

      if (!mounted) return;
      _showConfirmation('Report submitted (#$reportId). Thank you.');
      setState(() {
        _photo = null;
        _textController.clear();
        _zoneController.clear();
      });
    } catch (e) {
      if (!mounted) return;
      _showError('Could not submit report: $e');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _showConfirmation(String message) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Submitted'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red[700]),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Report / SOS')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // --- SOS quick action ---
          Card(
            color: Colors.red[50],
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Emergency SOS',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Sends your current location to the control room immediately.',
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _sosSubmitting ? null : _submitSos,
                      icon: const Icon(Icons.sos),
                      label: Text(_sosSubmitting ? 'Sending…' : 'SEND SOS NOW'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red[700],
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 8),

          // --- Full incident report ---
          Text('Incident Report', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          const Text(
            'Not an emergency? Describe what you\'re seeing -- this is reviewed by '
            'the control room alongside sensor data, marked as unverified until confirmed.',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 16),

          TextField(
            controller: _zoneController,
            decoration: const InputDecoration(
              labelText: 'Zone (optional, e.g. Z1)',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _textController,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'What are you seeing?',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),

          if (_photo != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.file(_photo!, height: 180, fit: BoxFit.cover),
              ),
            ),

          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _pickPhoto(ImageSource.camera),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Camera'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _pickPhoto(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Gallery'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _submitting ? null : _submitFullReport,
              child: Text(_submitting ? 'Submitting…' : 'Submit Report'),
            ),
          ),
        ],
      ),
    );
  }
}
