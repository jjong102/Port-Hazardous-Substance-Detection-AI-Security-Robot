import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:intl/intl.dart';
import '../models/hazard_event.dart';
import '../models/comment.dart';
import '../services/api.dart';

class EventDetailScreen extends StatefulWidget {
  final int eventId;
  const EventDetailScreen({super.key, required this.eventId});

  @override
  State<EventDetailScreen> createState() => _EventDetailScreenState();
}

class _EventDetailScreenState extends State<EventDetailScreen> {
  HazardEvent? ev;
  List<CommentRow> comments = [];
  final ctrl = TextEditingController();
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(
      const Duration(seconds: 6),
          (_) => _loadComments(incremental: true),
    );
  }

  Future<void> _load() async {
    final e = await Api.getEvent(widget.eventId);
    if (!mounted) return;
    setState(() => ev = e);
    await _loadComments();
  }

  Future<void> _loadComments({bool incremental = false}) async {
    final lastId = incremental && comments.isNotEmpty ? comments.last.id : null;
    final rows =
    await Api.getComments(eventId: widget.eventId, afterId: lastId);
    if (!mounted) return;
    setState(() => comments = incremental ? [...comments, ...rows] : rows);
  }

  @override
  void dispose() {
    _timer?.cancel();
    ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (ev == null) {
      return const Scaffold(
          body: Center(child: CircularProgressIndicator()));
    }
    final e = ev!;
    final pos = LatLng(e.lat, e.lng);
    return Scaffold(
      appBar: AppBar(title: Text('이벤트 #${e.id}')),
      body: Column(children: [
        // 지도
        SizedBox(
          height: 200,
          child: GoogleMap(
            initialCameraPosition:
            CameraPosition(target: pos, zoom: 15),
            markers: {
              Marker(
                markerId: const MarkerId('ev'),
                position: pos,
                infoWindow: InfoWindow(
                  title:
                  '${e.substance} ${e.concentration.toStringAsFixed(2)}ppm',
                ),
              )
            },
            myLocationButtonEnabled: false,
            zoomControlsEnabled: false,
          ),
        ),
        // 정보
        Padding(
          padding: const EdgeInsets.all(12.0),
          child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${e.substance}  ${e.concentration.toStringAsFixed(2)} ppm',
                  style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.bold),
                ),
                Text(
                    '${e.lat.toStringAsFixed(5)}, ${e.lng.toStringAsFixed(5)} • ${DateFormat('MM/dd HH:mm:ss').format(e.timestamp)}'),
                const SizedBox(height: 8),
                Row(children: [
                  Chip(label: Text(e.status)),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    onPressed: e.status == 'approved'
                        ? null
                        : () async {
                      final ok = await Api.approve(e.id);
                      if (ok) {
                        final updated =
                        await Api.getEvent(e.id);
                        if (!mounted) return;
                        setState(() => ev = updated);
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('승인되었습니다.'),
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.check),
                    label: const Text('승인'),
                  ),
                ]),
              ]),
        ),
        const Divider(height: 1),
        // 코멘트
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: comments.length,
            itemBuilder: (_, i) {
              final c = comments[i];
              return Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${c.author} • ${DateFormat('MM/dd HH:mm').format(c.createdAt)}',
                        style: const TextStyle(
                            fontSize: 12, color: Colors.white60),
                      ),
                      Text(c.message),
                    ]),
              );
            },
          ),
        ),
        Row(children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(8.0),
              child: TextField(
                controller: ctrl,
                decoration: const InputDecoration(
                  hintText: '코멘트 입력',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.send),
            onPressed: () async {
              final txt = ctrl.text.trim();
              if (txt.isEmpty) return;
              await Api.postComment(
                  eventId: e.id, author: 'app', message: txt);
              ctrl.clear();
              await _loadComments();
            },
          ),
        ]),
      ]),
    );
  }
}
