/// Modelo espelhando a tabela `avarias`.
class Avaria {
  final int id;
  final String codigo;
  final String produto;
  final int qtdAvariada;
  final String motivo;
  final String status;        // 'aberto' | 'resolvido'
  final String registradoEm;
  final String resolvidoEm;

  const Avaria({
    required this.id,
    required this.codigo,
    required this.produto,
    this.qtdAvariada = 1,
    this.motivo = '',
    this.status = 'aberto',
    this.registradoEm = '',
    this.resolvidoEm = '',
  });

  bool get isAberta => status == 'aberto';

  factory Avaria.fromMap(Map<String, dynamic> map) {
    return Avaria(
      id: _toInt(map['id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      qtdAvariada: _toInt(map['qtd_avariada']),
      motivo: map['motivo']?.toString() ?? '',
      status: map['status']?.toString() ?? 'aberto',
      registradoEm: map['registrado_em']?.toString() ?? '',
      resolvidoEm: map['resolvido_em']?.toString() ?? '',
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
  };

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  @override
  String toString() => 'Avaria($id, $produto, $status)';
}
