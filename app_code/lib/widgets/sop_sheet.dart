import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config.dart';

class SopSheet extends StatefulWidget {
  final int eventId;
  final String substance; // 'NH3'|'VOC'|'CO'
  const SopSheet({super.key, required this.eventId, required this.substance});
  @override State<SopSheet> createState() => _SopSheetState();
}

class _SopSheetState extends State<SopSheet> {
  List<Map<String,dynamic>> steps = [];
  final notes = <String,String>{};
  final checks = <String,bool>{};
  bool loading=true;

  @override
  void initState(){ super.initState(); _load(); }

  Future<void> _load() async {
    final r = await http.get(Uri.parse('$BE/sop?substance=${widget.substance}'));
    if (r.statusCode==200){
      final List data = jsonDecode(r.body);
      steps = data.cast<Map<String,dynamic>>();
    }
    setState(()=>loading=false);
  }

  Future<void> _send(String id, {bool? ok, String? note}) async {
    await http.post(Uri.parse('$BE/events/${widget.eventId}/sop_log'),
        headers: {'Content-Type':'application/json'},
        body: jsonEncode({'step_id':id,'ok':ok,'note':note}));
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator());
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('SOP - ${widget.substance}', style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height:8),
        ...steps.map((s){
          final id=s['id'] as String, type=s['type'] as String, text=s['text'] as String;
          if (type=='check') {
            final v = checks[id] ?? false;
            return CheckboxListTile(
              value: v, title: Text(text),
              onChanged: (nv){ setState(()=>checks[id]=nv??false); _send(id, ok:nv??false); },
            );
          } else {
            final ctl = TextEditingController(text: notes[id]??'');
            return Column(children:[
              Align(alignment: Alignment.centerLeft, child: Text(text)),
              TextField(controller: ctl, onSubmitted:(t){ notes[id]=t; _send(id, note:t); },
                  decoration: const InputDecoration(border: OutlineInputBorder(), hintText:'입력')),
              const SizedBox(height:8),
            ]);
          }
        }),
        const SizedBox(height:8),
      ]),
    );
  }
}
