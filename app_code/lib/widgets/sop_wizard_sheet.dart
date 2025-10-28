import 'package:flutter/material.dart';

class SopWizardSheet extends StatefulWidget {
  final List<String> substances; // 예: ['NH3','CO']
  const SopWizardSheet({super.key, required this.substances});
  @override State<SopWizardSheet> createState() => _SopWizardSheetState();
}

class _SopWizardSheetState extends State<SopWizardSheet> {
  int _step = 0;

  List<String> _stepsFor(String k) {
    switch (k) {
      case 'NH3':
        return [
          '바람 불어오는 방향으로 대피 유도',
          '환기 확보. 밀폐공간 출입 금지',
          'PPE: 방독마스크(암모니아용)·보안경·장갑',
          '감지기 다시 측정 후 감소 추세 확인',
        ];
      case 'VOC':
        return [
          '점화원 제거. 스파크 금지',
          '환기팬 가동. 누출원 격리',
          'PPE: 유기용제용 방독마스크',
          '누출 차단 후 저농도 유지 확인',
        ];
      case 'CO':
        return [
          '즉시 환기. 밀폐공간 인원 대피',
          '산소결핍 위험 안내. 측정기 유지',
          '증상자 산소 공급 및 119 연락',
          '원인 제거 후 30분 모니터링',
        ];
      default:
        return ['현장 안전확보', '대피 및 통제', '재측정', '기록·보고'];
    }
  }

  @override
  Widget build(BuildContext context) {
    final targets = widget.substances.isEmpty ? ['GEN'] : widget.substances;
    final steps = targets.expand(_stepsFor).toList();

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('SOP 위저드', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Stepper(
            currentStep: _step,
            onStepContinue: () => setState(() => _step = (_step + 1).clamp(0, steps.length - 1)),
            onStepCancel: () => setState(() => _step = (_step - 1).clamp(0, steps.length - 1)),
            controlsBuilder: (c, d) => Row(
              children: [
                FilledButton(onPressed: d.onStepContinue, child: const Text('다음')),
                const SizedBox(width: 8),
                OutlinedButton(onPressed: d.onStepCancel, child: const Text('이전')),
              ],
            ),
            steps: [
              for (int i = 0; i < steps.length; i++)
                Step(title: Text('단계 ${i + 1}'), content: Text(steps[i])),
            ],
          ),
        ]),
      ),
    );
  }
}
