// lib/services/push_service.dart
import 'dart:convert';
import 'package:flutter/foundation.dart';                 // debugPrint
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:http/http.dart' as http;

import '../firebase_options.dart';

const _BE = 'http://43.202.250.26:5000';                  // 백엔드 주소
const _topic = 'alerts';

final _fln = FlutterLocalNotificationsPlugin();
const _androidChannel = AndroidNotificationChannel(
  'alerts_high',
  '경보',
  description: '위험/주의 알림',
  importance: Importance.high,
);

/// 백그라운드/종료 상태에서 데이터 전용 메시지 대비(서버가 notification 포함 보내면 시스템이 표시함)
@pragma('vm:entry-point')
Future<void> _bgHandler(RemoteMessage message) async {
  // 필요시 로깅만
}

class PushService {
  static Future<void> init() async {
    // 0) Firebase 초기화
    await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);

    // 1) 권한 (Android 13+)
    if (await Permission.notification.isDenied) {
      await Permission.notification.request();
    }

    // 2) 포어그라운드(iOS 포함) 표시 허용
    await FirebaseMessaging.instance.setForegroundNotificationPresentationOptions(
      alert: true, badge: true, sound: true,
    );

    // 3) 로컬 알림(포어그라운드 배너용)
    const initAndroid = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initIOS = DarwinInitializationSettings();
    await _fln.initialize(const InitializationSettings(android: initAndroid, iOS: initIOS));
    await _fln
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_androidChannel);

    // 4) 백그라운드 핸들러
    FirebaseMessaging.onBackgroundMessage(_bgHandler);

    // 5) FCM 토큰 → 서버 등록
    final t = await FirebaseMessaging.instance.getToken();
    debugPrint('FCM TOKEN: $t');                          // 콘솔에서 복사 가능
    if (t != null) await _registerToken(t);
    FirebaseMessaging.instance.onTokenRefresh.listen(_registerToken);

    // 6) 포어그라운드 수신 → 배너 표시
    FirebaseMessaging.onMessage.listen((m) {
      final n = m.notification;
      if (n != null) {
        _fln.show(
          n.hashCode,
          n.title,
          n.body,
          const NotificationDetails(
            android: AndroidNotificationDetails(
              'alerts_high',
              '경보',
              importance: Importance.high,
              priority: Priority.high,
            ),
            iOS: DarwinNotificationDetails(
              presentAlert: true, presentBadge: true, presentSound: true,
            ),
          ),
          payload: (m.data['event_id'] ?? '').toString(),
        );
      }
    });
  }

  static Future<void> _registerToken(String token) async {
    // 서버가 토픽 구독 처리 (Firebase Admin에서 topic: alerts)
    try {
      final res = await http.post(
        Uri.parse('$_BE/devices/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'token': token, 'topic': _topic}),
      );
      debugPrint('register token -> ${res.statusCode} ${res.body}');
    } catch (e) {
      debugPrint('register token error: $e');
    }
  }
}