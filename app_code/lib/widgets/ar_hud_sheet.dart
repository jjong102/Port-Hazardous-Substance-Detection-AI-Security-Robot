import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_compass/flutter_compass.dart';
import 'package:geolocator/geolocator.dart';
import '../utils/geo.dart'; // bearingDegrees, wrapDeg360

class ARHudSheet extends StatefulWidget {
  final double targetLat, targetLng;
  final double perimeterM;
  const ARHudSheet({super.key, required this.targetLat, required this.targetLng, this.perimeterM = 30});
  @override State<ARHudSheet> createState() => _ARHudSheetState();
}

class _ARHudSheetState extends State<ARHudSheet> {
  double heading = 0, distance = 0, bearing = 0;
  StreamSubscription? _compassSub; Timer? _timer;

  @override void initState() { super.initState(); _start(); }
  @override void dispose() { _compassSub?.cancel(); _timer?.cancel(); super.dispose(); }

  Future<void> _start() async {
    if (!await Geolocator.isLocationServiceEnabled()) return;
    var p = await Geolocator.checkPermission();
    if (p == LocationPermission.denied) p = await Geolocator.requestPermission();
    if (p == LocationPermission.denied || p == LocationPermission.deniedForever) return;

    _compassSub = FlutterCompass.events?.listen((e) {
      final h = e.heading ?? 0;
      if (mounted) setState(() => heading = (h.isFinite ? h : 0));
    });

    _timer = Timer.periodic(const Duration(seconds: 1), (_) async {
      try {
        final pos = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
        final d = Geolocator.distanceBetween(pos.latitude, pos.longitude, widget.targetLat, widget.targetLng);
        final b = bearingDegrees(pos.latitude, pos.longitude, widget.targetLat, widget.targetLng);
        if (mounted) setState(() { distance = d; bearing = b; });
      } catch (_) {}
    });
  }

  @override
  Widget build(BuildContext context) {
    final diff = wrapDeg360(bearing - heading);
    final safe = distance >= widget.perimeterM;

    return Container(
      color: Colors.black.withOpacity(0.85),
      padding: const EdgeInsets.all(16),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Text('AR 경계', style: TextStyle(color: Colors.white, fontSize: 16)),
        const SizedBox(height: 8),
        SizedBox(height: 120, child: CustomPaint(painter: _ArrowPainter(angleDeg: diff, safe: safe))),
        const SizedBox(height: 8),
        Text('거리: ${distance.toStringAsFixed(1)} m / 경계: ${widget.perimeterM} m', style: const TextStyle(color: Colors.white70)),
        const SizedBox(height: 12),
      ]),
    );
  }
}

class _ArrowPainter extends CustomPainter {
  final double angleDeg; final bool safe;
  _ArrowPainter({required this.angleDeg, required this.safe});
  @override
  void paint(Canvas c, Size s) {
    final p = Paint()
      ..color = safe ? Colors.greenAccent : Colors.redAccent
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    final center = Offset(s.width/2, s.height/2);
    final len = s.height/2 - 10;
    final rad = angleDeg * math.pi/180.0;
    final tip = Offset(center.dx + len*math.sin(rad), center.dy - len*math.cos(rad));
    c.drawLine(center, tip, p);
    final head = 14.0;
    final left = Offset(tip.dx - head*math.sin(rad - math.pi/6), tip.dy + head*math.cos(rad - math.pi/6));
    final right= Offset(tip.dx - head*math.sin(rad + math.pi/6), tip.dy + head*math.cos(rad + math.pi/6));
    c.drawLine(tip, left, p); c.drawLine(tip, right, p);
  }
  @override bool shouldRepaint(covariant _ArrowPainter o) => o.angleDeg!=angleDeg || o.safe!=safe;
}
