/// Unidade individual (galão/balde) dentro de uma avaria.
class AvariaUnidade {
  final int id;
  final int avariaId;
  final String uid;
  final double nivel; // 0.0 – 100.0 (percentual cheio)

  const AvariaUnidade({
    required this.id,
    required this.avariaId,
    required this.uid,
    required this.nivel,
  });

  double litros(double capacidade) => (nivel / 100.0) * capacidade;

  AvariaUnidade copyWith({double? nivel}) => AvariaUnidade(
    id: id,
    avariaId: avariaId,
    uid: uid,
    nivel: nivel ?? this.nivel,
  );

  factory AvariaUnidade.fromMap(Map<String, dynamic> map) {
    return AvariaUnidade(
      id: _i(map['id']),
      avariaId: _i(map['avaria_id']),
      uid: map['uid']?.toString() ?? '',
      nivel: _d(map['nivel']),
    );
  }

  static int _i(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  static double _d(dynamic v) {
    if (v == null) return 50.0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v.toString()) ?? 50.0;
  }
}
