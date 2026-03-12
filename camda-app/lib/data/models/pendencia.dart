/// Modelo espelhando a tabela `pendencias_entrega`.
class Pendencia {
  final int id;
  final String fotoBase64;
  final String dataRegistro;
  final String observacao;

  const Pendencia({
    required this.id,
    required this.fotoBase64,
    required this.dataRegistro,
    this.observacao = '',
  });

  factory Pendencia.fromMap(Map<String, dynamic> map) {
    return Pendencia(
      id: _toInt(map['id']),
      fotoBase64: map['foto_base64']?.toString() ?? '',
      dataRegistro: map['data_registro']?.toString() ?? '',
      observacao: map['observacao']?.toString() ?? '',
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
