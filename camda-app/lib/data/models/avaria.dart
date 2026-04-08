import 'dart:math' as math;
import 'avaria_unidade.dart';

/// Modelo espelhando a tabela `avarias` + unidades de galão.
class Avaria {
  final int id;
  final String codigo;
  final String produto;
  final int qtdAvariada;
  final String motivo;
  final String status;        // 'aberto' | 'resolvido'
  final String registradoEm;
  final String resolvidoEm;
  final double capacidadeLitros; // capacidade de cada galão/balde em litros
  final List<AvariaUnidade> unidades; // galões individuais com nível de preenchimento

  const Avaria({
    required this.id,
    required this.codigo,
    required this.produto,
    this.qtdAvariada = 1,
    this.motivo = '',
    this.status = 'aberto',
    this.registradoEm = '',
    this.resolvidoEm = '',
    this.capacidadeLitros = 20.0,
    this.unidades = const [],
  });

  bool get isAberta => status == 'aberto';

  double get totalRestanteLitros =>
      unidades.fold(0.0, (s, u) => s + u.litros(capacidadeLitros));

  double get totalPerdidoLitros =>
      unidades.fold(0.0, (s, u) => s + ((100.0 - u.nivel) / 100.0) * capacidadeLitros);

  double get nivelMinimo =>
      unidades.isEmpty ? 0.0 : unidades.map((u) => u.nivel).reduce(math.min);

  Avaria copyWith({List<AvariaUnidade>? unidades}) => Avaria(
    id: id,
    codigo: codigo,
    produto: produto,
    qtdAvariada: qtdAvariada,
    motivo: motivo,
    status: status,
    registradoEm: registradoEm,
    resolvidoEm: resolvidoEm,
    capacidadeLitros: capacidadeLitros,
    unidades: unidades ?? this.unidades,
  );

  factory Avaria.fromMap(Map<String, dynamic> map, {List<AvariaUnidade>? unidades}) {
    final cap = _d(map['capacidade_litros']);
    return Avaria(
      id: _i(map['id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      qtdAvariada: _i(map['qtd_avariada']),
      motivo: map['motivo']?.toString() ?? '',
      status: map['status']?.toString() ?? 'aberto',
      registradoEm: map['registrado_em']?.toString() ?? '',
      resolvidoEm: map['resolvido_em']?.toString() ?? '',
      capacidadeLitros: cap > 0 ? cap : 20.0,
      unidades: unidades ?? const [],
    );
  }

  Map<String, dynamic> toMap() => {
    'id': id,
    'codigo': codigo,
    'produto': produto,
    'qtd_avariada': qtdAvariada,
    'motivo': motivo,
    'status': status,
    'registrado_em': registradoEm,
    'resolvido_em': resolvidoEm,
    'capacidade_litros': capacidadeLitros,
  };

  static int _i(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  static double _d(dynamic v) {
    if (v == null) return 0.0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0.0;
  }

  @override
  String toString() => 'Avaria($id, $produto, $status)';
}
