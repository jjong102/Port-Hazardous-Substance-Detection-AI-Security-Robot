// lib/screens/incident_screen.dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import '../api_client.dart';
import '../config.dart';
import '../models.dart';
import '../widgets/ar_hud_sheet.dart';
import '../widgets/evidence_sheet.dart';
import '../widgets/sop_wizard_sheet.dart';

class IncidentScreen extends StatefulWidget {
  const IncidentScreen({super.key});
  @override
  State<IncidentScreen> createState() => _IncidentScreenState();
}

class _IncidentScreenState extends State<IncidentScreen> {
  Incident? incident;
  bool loading = true;
  bool busy = false;
  Timer? timer;

  @override
  void initState() {
    super.initState();
    _load();
    timer = Timer.periodic(pollInterval, (_) => _load());
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    await Api.flushQueue();
    final data = await Api.getActiveIncident();
    if (!mounted) return;
    setState(() {
      incident = data;
      loading = false;
    });
  }

  Future<void> _sendResolve() async {
    final inc = incident;
    if (inc == null) return;
    setState(() => busy = true);

    final code = await Api.resolveIncident(inc.id);
    String msg;
    if (code == 200) {
      msg = '해결완료 전송됨';
    } else if (code == 403) {
      msg = '토큰 불일치(403): ADMIN_TOKEN/APPROVAL_TOKEN 확인';
    } else if (code == -2) {
      msg = '타임아웃. 네트워크 확인';
      await Api.enqueue(inc.id);
    } else if (code == -1) {
      msg = '네트워크 불가. 오프라인 큐 저장';
      await Api.enqueue(inc.id);
    } else {
      msg = '오류: HTTP $code';
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    }
    setState(() => busy = false);
    if (code == 200) await _load();
  }

  void _showMap(double lat, double lng) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => SizedBox(
        height: MediaQuery.of(context).size.height * 0.9,
        child: GoogleMap(
          initialCameraPosition: CameraPosition(target: LatLng(lat, lng), zoom: 15),
          markers: {
            Marker(
              markerId: const MarkerId('event'),
              position: LatLng(lat, lng),
              infoWindow: const InfoWindow(title: '이벤트 위치'),
            ),
          },
          myLocationEnabled: false,
          zoomControlsEnabled: true,
        ),
      ),
    );
  }

  void _openARHud(double lat, double lng) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => ARHudSheet(targetLat: lat, targetLng: lng, perimeterM: 30),
    );
  }

  void _openEvidence(int eventId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => EvidenceSheet(eventId: eventId),
    );
  }

  void _openSopWizard(Incident inc) {
    final kinds = inc.substances.map((s) => s.substance).toSet().toList();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => SopWizardSheet(substances: kinds),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('현장 처리'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: loading ? null : _load,
            tooltip: '새로고침',
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: loading
            ? const Center(child: CircularProgressIndicator())
            : incident == null
            ? Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border.all(color: Colors.black12),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Center(
            child: Text('승인 전 인시던트 없음',
                style: TextStyle(color: Colors.black54)),
          ),
        )
            : _IncidentCard(
          incident: incident!,
          busy: busy,
          onResolve: _sendResolve,
          onShowMap: () => _showMap(incident!.lat, incident!.lng),
          onShowAR: () => _openARHud(incident!.lat, incident!.lng),
          onShowEvidence: () => _openEvidence(incident!.id),
          onShowSop: () => _openSopWizard(incident!),
        ),
      ),
    );
  }
}

class _IncidentCard extends StatelessWidget {
  final Incident incident;
  final bool busy;
  final VoidCallback onResolve;
  final VoidCallback onShowMap;
  final VoidCallback onShowAR;
  final VoidCallback onShowEvidence;
  final VoidCallback onShowSop;

  const _IncidentCard({
    required this.incident,
    required this.busy,
    required this.onResolve,
    required this.onShowMap,
    required this.onShowAR,
    required this.onShowEvidence,
    required this.onShowSop,
  });

  // 값 기준 색상: 주의≥2.0, 위험≥4.0
  Color _valueColor(double v) {
    if (v >= 4.0) return const Color(0xFFDC2626); // red-600
    if (v >= 2.0) return const Color(0xFFF59E0B); // amber-500
    return const Color(0xFF0EA5E9); // sky-500
  }

  @override
  Widget build(BuildContext context) {
    final subs = [...incident.substances]..sort((a, b) => b.max.compareTo(a.max));
    final awaitingApprove = incident.status != 'approved';

    final maxAny = subs.isEmpty ? 0.0 : subs.map((e) => e.max).reduce((a, b) => a > b ? a : b);
    final levelText = maxAny >= 4.0 ? '위험' : maxAny >= 2.0 ? '주의' : '정상';
    final levelColor = maxAny >= 4.0
        ? const Color(0xFFDC2626)
        : maxAny >= 2.0
        ? const Color(0xFFF59E0B)
        : Colors.grey;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.black12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Text('이상이벤트 발생',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          Chip(
            label: Text(levelText, style: const TextStyle(color: Colors.white)),
            backgroundColor: levelColor,
          ),
          const SizedBox(width: 8),
          if (awaitingApprove)
            const Chip(
              label: Text('이중 승인 대기', style: TextStyle(color: Colors.white)),
              backgroundColor: Color(0xFF111827),
            ),
        ]),
        const SizedBox(height: 4),
        Text(
          '${incident.lat.toStringAsFixed(5)}, ${incident.lng.toStringAsFixed(5)} · 상태 ${incident.status}',
          style: const TextStyle(color: Colors.black54, fontSize: 12),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: subs.take(3).map((s) {
            final c = _valueColor(s.max);
            return Chip(
              side: BorderSide(color: c),
              backgroundColor: Colors.grey.shade100,
              label: Text('${s.substance} ${s.max.toStringAsFixed(2)}',
                  style: TextStyle(color: c, fontWeight: FontWeight.w700)),
            );
          }).toList(),
        ),
        const SizedBox(height: 12),
        Wrap(
          alignment: WrapAlignment.start,
          spacing: 8,
          runSpacing: 8,
          children: [
            OutlinedButton.icon(
              onPressed: onShowMap,
              icon: const Icon(Icons.map),
              label: const Text('지도 보기'),
            ),
            OutlinedButton.icon(
              onPressed: onShowAR,
              icon: const Icon(Icons.explore),
              label: const Text('AR HUD'),
            ),
            OutlinedButton.icon(
              onPressed: onShowEvidence,
              icon: const Icon(Icons.fact_check),
              label: const Text('증거 기록'),
            ),
            OutlinedButton.icon(
              onPressed: onShowSop,
              icon: const Icon(Icons.rule),
              label: const Text('SOP 위저드'),
            ),
            FilledButton(
              onPressed: busy || incident.status != 'pending' ? null : onResolve,
              child: Text(busy ? '전송 중…' : '해결완료 전송'),
            ),
          ],
        ),
      ]),
    );
  }
}
