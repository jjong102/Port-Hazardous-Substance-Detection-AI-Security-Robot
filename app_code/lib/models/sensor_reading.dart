class SensorReading {
  final String type;    // VOC/NH3/CO/GPS ...
  final double? value;  // 텍스트일 수도 있어 null 허용
  final String? textValue;
  final DateTime timestamp;

  SensorReading({
    required this.type,
    this.value,
    this.textValue,
    required this.timestamp,
  });

  factory SensorReading.fromJson(Map<String, dynamic> j) {
    return SensorReading(
      type: (j['sensor_type'] ?? '').toString(),
      value: j['value'] == null ? null : (j['value'] as num).toDouble(),
      textValue: j['text_value']?.toString(),
      timestamp: DateTime.tryParse(j['timestamp'] ?? '') ?? DateTime.now(),
    );
  }
}
