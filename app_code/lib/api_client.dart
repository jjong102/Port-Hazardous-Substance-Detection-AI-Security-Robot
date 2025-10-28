// lib/api_client.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'config.dart';
import 'models.dart';

const BE = String.fromEnvironment('BE', defaultValue: String.fromEnvironment('NEXT_PUBLIC_BACKEND_URL', defaultValue: 'http://43.202.250.26:5000'));


class Api {
  static Future<Incident?> getActiveIncident() async {
    final uri = Uri.parse('$BE/incident/active?vehicle_id=$VEHICLE_ID');
    try {
      final r = await http.get(uri).timeout(const Duration(seconds: 8));
      if (r.statusCode == 200) {
        return Incident.fromJson(jsonDecode(r.body) as Map<String, dynamic>);
      }
    } on TimeoutException {
      return null;
    } catch (_) {
      return null;
    }
    return null;
  }

  static Future<void> registerFcmToken(String token) async {
    final uri = Uri.parse('$BE/devices/register');
    await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'token': token, 'topic': 'alerts'}),
    );
  }


  // 200=성공, 403=토큰오류, -1=네트워크, -2=타임아웃
  static Future<int> resolveIncident(int id) async {
    final uri = Uri.parse('$BE/events/$id/resolve?token=$ADMIN_TOKEN');
    try {
      final r = await http
          .post(uri, headers: {'X-Admin-Token': ADMIN_TOKEN, 'X-User': 'app'})
          .timeout(const Duration(seconds: 8));
      return r.statusCode;
    } on TimeoutException {
      return -2;
    } catch (_) {
      return -1;
    }
  }

  // 오프라인 큐
  static const _qKey = 'resolve_queue';

  static Future<void> enqueue(int id) async {
    final sp = await SharedPreferences.getInstance();
    final list = sp.getStringList(_qKey) ?? <String>[];
    final s = id.toString();
    if (!list.contains(s)) {
      list.add(s);
      await sp.setStringList(_qKey, list);
    }
  }

  static Future<void> flushQueue() async {
    final sp = await SharedPreferences.getInstance();
    final list = sp.getStringList(_qKey) ?? <String>[];
    if (list.isEmpty) return;
    final rest = <String>[];
    for (final s in list) {
      final code = await resolveIncident(int.parse(s));
      if (code != 200) rest.add(s);
    }
    await sp.setStringList(_qKey, rest);
  }

  // Api.uploadEvidence만 교체
  static Future<(bool ok, String detail)> uploadEvidence({
    required int eventId,
    required String filePath,
    String kind = 'photo',
    String? note,
  }) async {
    final uri = Uri.parse('$BE/events/$eventId/evidence?token=$ADMIN_TOKEN');
    final req = http.MultipartRequest('POST', uri)
      ..headers['X-Admin-Token'] = ADMIN_TOKEN
      ..headers['X-User'] = 'app'
      ..fields['kind'] = kind;
    if (note != null && note.isNotEmpty) req.fields['note'] = note;

    if (kind != 'note') {
      final f = File(filePath);
      if (!await f.exists()) return (false, 'file not found');
      final bytes = await f.readAsBytes();
      req.fields['sha256'] = sha256.convert(bytes).toString();
      req.files.add(await http.MultipartFile.fromPath('file', filePath, filename: p.basename(filePath)));
    }

    try {
      final res = await req.send().timeout(const Duration(seconds: 60));
      final body = await res.stream.bytesToString();
      return (res.statusCode == 200, 'HTTP ${res.statusCode} $body');
    } catch (e) {
      return (false, 'exception $e');
    }
  }

  static Future<String?> buildReport(int eventId) async {
    final uri = Uri.parse('$BE/events/$eventId/report/pdf?token=$ADMIN_TOKEN');
    final r = await http.post(uri, headers: {
      'X-Admin-Token': ADMIN_TOKEN,
      'X-User': 'app',
    });
    if (r.statusCode == 200) {
      return (jsonDecode(r.body)['url'] as String?);
    }
    return null;
  }
}
