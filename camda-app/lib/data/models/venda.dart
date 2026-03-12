/// Modelo espelhando a tabela `vendas_historico`.
class Venda {
  final int id;
  final String codigo;
  final String produto;
  final String grupo;
  final int qtdVendida;
  final int qtdEstoque;
  final String dataUpload;

  const Venda({
    required this.id,
    required this.codigo,
    required this.produto,
    required this.grupo,
    this.qtdVendida = 0,
    this.qtdEstoque = 0,
    this.dataUpload = '',
  });

  factory Venda.fromMap(Map<String, dynamic> map) {
    return Venda(
      id: _toInt(map['id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      grupo: map['grupo']?.toString() ?? '',
      qtdVendida: _toInt(map['qtd_vendida']),
      qtdEstoque: _toInt(map['qtd_estoque']),
      dataUpload: map['data_upload']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toMap() => {
    'id': id,
    'codigo': codigo,
    'produto': produto,
    'grupo': grupo,
    'qtd_vendida': qtdVendida,
    'qtd_estoque': qtdEstoque,
    'data_upload': dataUpload,
  };

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
