class Substance {
  final String substance;  // NH3 | VOC | CO
  final double max;
  final String? lastAt;
  const Substance({required this.substance, required this.max, this.lastAt});

  factory Substance.fromJson(Map<String, dynamic> j) => Substance(
    substance: (j['substance'] ?? '').toString(),
    max: (j['max'] ?? 0).toDouble(),
    lastAt: j['last_at']?.toString(),
  );
}

class Incident {
  final int id;
  final String status; // pending | resolved | approved
  final double lat;
  final double lng;
  final String vehicleId;
  final String createdAt;
  final String? approvedAt;
  final String? resolvedAt;
  final List<Substance> substances;

  const Incident({
    required this.id,
    required this.status,
    required this.lat,
    required this.lng,
    required this.vehicleId,
    required this.createdAt,
    this.approvedAt,
    this.resolvedAt,
    required this.substances,
  });

  factory Incident.fromJson(Map<String, dynamic> j) => Incident(
    id: j['id'] as int,
    status: (j['status'] ?? '').toString(),
    lat: (j['lat'] ?? 0).toDouble(),
    lng: (j['lng'] ?? 0).toDouble(),
    vehicleId: (j['vehicle_id'] ?? '').toString(),
    createdAt: (j['created_at'] ?? '').toString(),
    approvedAt: j['approved_at']?.toString(),
    resolvedAt: j['resolved_at']?.toString(),
    substances: ((j['substances'] as List?) ?? [])
        .map((e) => Substance.fromJson(e as Map<String, dynamic>))
        .toList(),
  );
}
