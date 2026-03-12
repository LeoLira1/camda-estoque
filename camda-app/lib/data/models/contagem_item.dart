/// Modelo espelhando a tabela `contagem_itens`.
class ContagemItem {
  final int id;
  final int uploadId;
  final String codigo;
  final String produto;
  final String categoria;
  final int qtdEstoque;
  final String status;      // 'pendente' | 'ok' | 'divergente'
  final String motivo;
  final int qtdDivergencia;
  final String registradoEm;

  const ContagemItem({
    required this.id,
    this.uploadId = 0,
    required this.codigo,
    required this.produto,
    required this.categoria,
    this.qtdEstoque = 0,
    this.status = 'pendente',
    this.motivo = '',
    this.qtdDivergencia = 0,
    this.registradoEm = '',
  });

  bool get isPendente => status == 'pendente';
  bool get isOk => status == 'ok';
  bool get isDivergente => status == 'divergente';

  factory ContagemItem.fromMap(Map<String, dynamic> map) {
    return ContagemItem(
      id: _toInt(map['id']),
      uploadId: _toInt(map['upload_id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      categoria: map['categoria']?.toString() ?? '',
      qtdEstoque: _toInt(map['qtd_estoque']),
      status: map['status']?.toString() ?? 'pendente',
      motivo: map['motivo']?.toString() ?? '',
      qtdDivergencia: _toInt(map['qtd_divergencia']),
      registradoEm: map['registrado_em']?.toString() ?? '',
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
