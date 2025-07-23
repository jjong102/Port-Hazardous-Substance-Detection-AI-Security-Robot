import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '진돗개',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        scaffoldBackgroundColor: Colors.grey[100],
        useMaterial3: true,
        fontFamily: 'Pretendard',
      ),
      debugShowCheckedModeBanner: false,
      home: const HomeScreen(),
    );
  }
}

String getRiskLevel(String type, int value) {
  if (type == '정상' || value == 0) return '정상';
  if (value > 100) return '매우 위험';
  if (value > 50) return '주의';
  return '양호';
}

Color getRiskColor(String level) {
  switch (level) {
    case '매우 위험':
      return Colors.red; // 원색 빨강으로 강렬하게 표시
    case '주의':
      return Colors.orange.shade800;
    case '양호':
      return Colors.yellow.shade600;
    default:
      return Colors.green.shade400;
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int? _expandedIndex;
  List<Map<String, dynamic>> alerts = [
    {"type": "VOC", "value": 132, "location": "이서면 북부", "time": "2025-06-18 17:03"},
    {"type": "CO", "value": 55, "location": "남부병설", "time": "2025-06-18 17:10"},
    {"type": "정상", "value": 0, "location": "송천 센터", "time": "2025-06-18 17:20"},
    {"type": "NH3", "value": 87, "location": "인천항 A지구", "time": "2025-06-18 17:25"},
    {"type": "VOC", "value": 145, "location": "인천항 B지구", "time": "2025-06-18 17:32"},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        elevation: 3,
        backgroundColor: Colors.white,
        centerTitle: true,
        title: const Text(
          '진돗개',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: Colors.black87,
          ),
        ),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: alerts.length,
        itemBuilder: (context, index) {
          final alert = alerts[index];
          final level = getRiskLevel(alert['type'], alert['value']);
          final color = getRiskColor(level);
          final isExpanded = _expandedIndex == index;

          return AlertCard(
            type: alert['type'],
            value: alert['value'],
            location: alert['location'],
            time: alert['time'],
            riskLevel: level,
            color: color,
            isExpanded: isExpanded,
            onTap: () {
              setState(() {
                _expandedIndex = isExpanded ? null : index;
              });
            },
            onResolved: () {
              setState(() {
                alerts[index]['type'] = '정상';
                alerts[index]['value'] = 0;
                _expandedIndex = null;
              });
            },
          );
        },
      ),
    );
  }
}

class AlertCard extends StatelessWidget {
  final String type;
  final int value;
  final String location;
  final String time;
  final String riskLevel;
  final Color color;
  final bool isExpanded;
  final VoidCallback onTap;
  final VoidCallback onResolved;

  const AlertCard({
    super.key,
    required this.type,
    required this.value,
    required this.location,
    required this.time,
    required this.riskLevel,
    required this.color,
    required this.isExpanded,
    required this.onTap,
    required this.onResolved,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      color: color.withOpacity(0.5),
      elevation: 3,
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '$type - ${value}ppm',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: Colors.black, // 제목은 항상 검정색
                      ),
                    ),
                  ),
                  Icon(isExpanded ? Icons.expand_less : Icons.expand_more, color: Colors.black),
                ],
              ),
              const SizedBox(height: 6),
              Text('위치: $location'),
              Text('시간: $time'),
              Text('위험도: $riskLevel'),
              if (isExpanded) ...[
                const Divider(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.check, color: Colors.black),
                        label: const Text(
                          '해결 완료',
                          style: TextStyle(color: Colors.black),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          side: const BorderSide(color: Colors.black),
                        ),
                        onPressed: onResolved,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.map, color: Colors.indigo),
                        label: const Text(
                          '지도보기',
                          style: TextStyle(color: Colors.indigo),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.white,
                          side: BorderSide(color: Colors.indigo.shade400),
                        ),
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const MapScreen()),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class MapScreen extends StatelessWidget {
  const MapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    const LatLng exampleLocation = LatLng(37.4472, 126.6155);
    return Scaffold(
      appBar: AppBar(title: const Text('지도 보기')),
      body: GoogleMap(
        initialCameraPosition: const CameraPosition(target: exampleLocation, zoom: 14),
        markers: {
          Marker(
            markerId: const MarkerId('dangerLocation'),
            position: exampleLocation,
            infoWindow: const InfoWindow(title: '감지 위치'),
          ),
        },
      ),
    );
  }
}
