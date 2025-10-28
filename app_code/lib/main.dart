import 'package:flutter/material.dart';
import 'screens/incident_screen.dart';
import 'services/push_service.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform, // ★ 중요
  );
  await PushService.init();
  runApp(const App());
}

class App extends StatelessWidget {
  const App({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '현장 처리',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: const Color(0xFF111827)),
      home: const IncidentScreen(),
    );
  }
}
