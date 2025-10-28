import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/hazard_event.dart';
import '../models/sensor_reading.dart';
import '../services/api.dart';
import 'event_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Timer? _timer;
  List<HazardEvent> warnings = [];
  SensorReading? voc, nh3, co;
  bool loading = false;

  @override
  void initState() {
    super.initState();
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _poll());
  }

  Future<void> _poll() async {
    if (loading) return;
    loading = true;
    try {
      final list = await Api.latestMulti();
      final v = await Api.latestSensor('VOC');
      final n = await Api.latestSensor('NH3');
      final c = await Api.latestSensor('CO');
      if (!mounted) return;
      setState(() {
        warnings = list;
        voc = v;
        nh3 = n;
        co = c;
      });
    } finally {
      loading = false;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Widget _mini(String label, SensorReading? r) {
    final v = r?.value ?? 0;
    final level = v >= 4 ? '매우 위험' : v >= 2 ? '주의' : v > 0 ? '양호' : '정상';
    Color color = switch (level) {
      '매우 위험' => Colors.red,
      '주의' => Colors.orange,
      '양호' => Colors.green,
      _ => Colors.grey,
    };
    final time =
    r == null ? '-' : DateFormat('MM/dd HH:mm:ss').format(r.timestamp);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border(left: BorderSide(color: color, width: 4)),
        color: Colors.black12,
      ),
      child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
              Container(
                padding:
                const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withOpacity(.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(level,
                    style: TextStyle(
                        color: color,
                        fontSize: 12,
                        fontWeight: FontWeight.w600)),
              ),
            ]),
            const SizedBox(height: 4),
            Text('농도: ${v.toStringAsFixed(2)} ppm'),
            Text('시간: $time',
                style:
                const TextStyle(fontSize: 12, color: Colors.white60)),
          ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar:
      AppBar(title: const Text('현장 상황 알림'), actions: [
        IconButton(icon: const Icon(Icons.refresh), onPressed: _poll),
      ]),
      body: Column(children: [
        // 센서 3종
        Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(children: [
            _mini('VOC', voc),
            const SizedBox(height: 8),
            _mini('NH3', nh3),
            const SizedBox(height: 8),
            _mini('CO', co),
          ]),
        ),
        const Divider(height: 1),
        // 경보 리스트
        Expanded(
          child: ListView.separated(
            itemCount: warnings.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final e = warnings[i];
              return ListTile(
                title: Text(
                    '${e.substance}  ${e.concentration.toStringAsFixed(2)} ppm'),
                subtitle: Text(
                    '${e.lat.toStringAsFixed(5)}, ${e.lng.toStringAsFixed(5)} • ${DateFormat('MM/dd HH:mm:ss').format(e.timestamp)}'),
                trailing: Text(e.status),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => EventDetailScreen(eventId: e.id),
                  ),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}
