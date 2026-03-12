/// Modelo espelhando a tabela `lancamentos_manuais`.
class Lancamento {
  final int id;
  final String codigo;
  final String produto;
  final String categoria;
  final String tipo;        // 'entrada' | 'saida' | 'ajuste'
  final int quantidade;
  final String motivo;
  final String registradoEm;

  const Lancamento({
    required this.id,
    required this.codigo,
    required this.produto,
    required this.categoria,
    required this.tipo,
    this.quantidade = 0,
    this.motivo = '',
    this.registradoEm = '',
  });

  bool get isEntrada => tipo == 'entrada';
  bool get isSaida => tipo == 'saida';

  factory Lancamento.fromMap(Map<String, dynamic> map) {
    return Lancamento(
      id: _toInt(map['id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      categoria: map['categoria']?.toString() ?? '',
      tipo: map['tipo']?.toString() ?? '',
      quantidade: _toInt(map['quantidade']),
      motivo: map['motivo']?.toString() ?? '',
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
