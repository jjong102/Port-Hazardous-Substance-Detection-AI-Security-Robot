import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../models/hazard_event.dart';
import '../models/sensor_reading.dart';
import '../models/comment.dart';

class Api {
  static Uri _u(String p, [Map<String, String>? q]) =>
      Uri.parse('$kBackendBaseUrl$p').replace(queryParameters: q);

  static Future<List<HazardEvent>> latestMulti() async {
    final r = await http.get(_u('/latest_multi'));
    if (r.statusCode != 200) return [];
    final List arr = jsonDecode(r.body);
    return arr.map((e) => HazardEvent.fromJson(e)).toList();
  }

  static Future<HazardEvent?> getEvent(int id) async {
    final r = await http.get(_u('/event/$id'));
    if (r.statusCode != 200) return null;
    return HazardEvent.fromJson(jsonDecode(r.body));
  }

  static Future<bool> approve(int id) async {
    final r = await http.post(_u('/approve/$id'));
    return r.statusCode == 200;
  }

  static Future<SensorReading?> latestSensor(String type) async {
    final r = await http.get(_u('/want/$type'));
    if (r.statusCode != 200) return null;
    return SensorReading.fromJson(jsonDecode(r.body));
  }

  static Future<List<CommentRow>> getComments({
    int? eventId,
    int? afterId,
  }) async {
    final q = <String, String>{};
    if (eventId != null) q['event_id'] = '$eventId';
    if (afterId != null) q['after_id'] = '$afterId';
    final r = await http.get(_u('/comments', q));
    if (r.statusCode != 200) return [];
    final List arr = jsonDecode(r.body);
    return arr.map((e) => CommentRow.fromJson(e)).toList();
  }

  static Future<bool> postComment({
    int? eventId,
    required String author,
    required String message,
  }) async {
    final r = await http.post(
      _u('/comments'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(
        {'event_id': eventId, 'author': author, 'message': message},
      ),
    );
    return r.statusCode == 200;
  }

  static Future<void> registerPushToken(String token) async {
    await http.post(
      _u('/register_push_token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'token': token, 'platform': 'android'}),
    );
  }
}
