// app/lib/screens/log_screen.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config.dart';
import '../api_client.dart';

class LogScreen extends StatefulWidget {
  final int eventId;
  const LogScreen({super.key, required this.eventId});
  @override State<LogScreen> createState()=>_LogScreenState();
}
class _LogScreenState extends State<LogScreen> {
  List evidence=[], actions=[]; bool loading=true, err=false;
  Future<void> _load() async {
    try{
      final r = await http.get(Uri.parse('SERVER_URL/events/${widget.eventId}/timeline'),
          headers: ADMIN_TOKEN.isNotEmpty ? {'X-Admin-Token': ADMIN_TOKEN} : {});
      final j = jsonDecode(r.body);
      setState((){ evidence=j['evidence']??[]; actions=j['actions']??[]; loading=false; });
    }catch(_){ setState(()=>err=true); }
  }
  @override void initState(){super.initState(); _load();}
  @override Widget build(BuildContext c){
    if (err) return const Scaffold(body: Center(child: Text('로드 실패')));
    return Scaffold(appBar: AppBar(title: Text('해결 전 로그 #${widget.eventId}')),
        body: loading? const Center(child:CircularProgressIndicator())
            : ListView(padding: const EdgeInsets.all(12), children: [
          const Text('증거', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height:8),
          for (final e in evidence)
            ListTile(
              leading: Icon(_icon(e['kind']??'')),
              title: Text('${e['kind']}  ${e['ts']}'),
              subtitle: Text((e['note']??'').toString()),
              onTap: (){
                final u = e['url']??'';
                if (u is String && u.isNotEmpty) {
                  Navigator.push(c, MaterialPageRoute(builder:(_)=>_Viewer(url:'SERVER_URL$u')));
                }
              },
            ),
          const Divider(),
          const Text('액션', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height:8),
          for (final a in actions)
            ListTile(
              leading: const Icon(Icons.timeline),
              title: Text('${a['action']}  ${a['ts']}'),
              subtitle: Text('${a['actor']} ${(a['detail']??'')}'),
            ),
        ]));
  }
  IconData _icon(String k){ switch(k){case 'video':return Icons.videocam;case 'audio':return Icons.mic;case 'note':return Icons.note;default:return Icons.photo;}}
}

class _Viewer extends StatelessWidget{
  final String url; const _Viewer({required this.url});
  @override Widget build(BuildContext c)=>Scaffold(appBar: AppBar(title: const Text('미리보기')),
      body: Center(child: Image.network(url, errorBuilder: (_,__,___)=>const Text('미리보기 불가'))));
}

class ActiveLogScreen extends StatefulWidget { const ActiveLogScreen({super.key}); @override State<ActiveLogScreen> createState()=>_ActiveLogScreenState(); }
class _ActiveLogScreenState extends State<ActiveLogScreen> {
  int? _id;
  @override void initState(){super.initState(); _load();}
  Future<void> _load() async { final inc = await Api.getActiveIncident(); if(!mounted) return; setState(()=>_id=inc?.id); }
  @override Widget build(BuildContext c){ if(_id==null) return const Scaffold(body: Center(child:CircularProgressIndicator())); return LogScreen(eventId:_id!); }
}
