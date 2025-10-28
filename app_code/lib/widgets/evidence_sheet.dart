import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../api_client.dart';

class EvidenceSheet extends StatefulWidget {
  final int eventId;
  const EvidenceSheet({super.key, required this.eventId});

  @override
  State<EvidenceSheet> createState() => _EvidenceSheetState();
}

class _EvidenceSheetState extends State<EvidenceSheet> {
  final _picker = ImagePicker();
  bool _busy = false;
  String? _note;

  Future<void> _pickPhoto() async {
    final x = await _picker.pickImage(source: ImageSource.camera, imageQuality: 85);
    if (x == null) return;
    await _upload(kind: 'photo', path: x.path);
  }

  Future<void> _pickVideo() async {
    final x = await _picker.pickVideo(source: ImageSource.camera, maxDuration: const Duration(minutes: 2));
    if (x == null) return;
    await _upload(kind: 'video', path: x.path);
  }

  Future<void> _upload({required String kind, String? path, String? note}) async {
    if (_busy) return;
    setState(() => _busy = true);

    // ⬇️ 레코드 구조 분해
    final (ok, err) = await Api.uploadEvidence(
      eventId: widget.eventId,
      filePath: path ?? '',
      kind: kind,
      note: note,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ok ? '업로드 완료' : '업로드 실패${err != null ? ' ($err)' : ''}')),
      );
      if (ok) Navigator.pop(context);
    }
    setState(() => _busy = false);
  }


  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('증거 기록', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _busy ? null : _pickPhoto,
                    icon: const Icon(Icons.photo_camera),
                    label: const Text('사진 촬영'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _busy ? null : _pickVideo,
                    icon: const Icon(Icons.videocam),
                    label: const Text('영상 촬영'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: '메모(선택)',
                border: OutlineInputBorder(),
              ),
              onChanged: (v) => _note = v,
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: (_busy || (_note == null || _note!.trim().isEmpty))
                    ? null
                    : () => _upload(kind: 'note', note: _note!.trim()),
                child: Text(_busy ? '업로드 중…' : '메모 업로드'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
