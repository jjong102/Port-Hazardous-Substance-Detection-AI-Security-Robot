class HazardEvent {
  final int id;
  final String substance; // VOC/NH3/CO
  final double concentration;
  final double lat;
  final double lng;
  final DateTime timestamp;
  final String status; // new/pending/approved

  HazardEvent({
    required this.id,
    required this.substance,
    required this.concentration,
    required this.lat,
    required this.lng,
    required this.timestamp,
    required this.status,
  });

  factory HazardEvent.fromJson(Map<String, dynamic> j) {
    return HazardEvent(
      id: (j['id'] as num).toInt(),
      substance: (j['substance'] ?? '').toString(),
      concentration: (j['concentration'] as num).toDouble(),
      lat: (j['lat'] as num).toDouble(),
      lng: (j['lng'] as num).toDouble(),
      timestamp: DateTime.tryParse(j['timestamp'] ?? '') ?? DateTime.now(),
      status: (j['status'] ?? 'new').toString(),
    );
  }
}
