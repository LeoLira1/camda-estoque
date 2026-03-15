/// Modelo espelhando a tabela `reposicao_loja`.
class Reposicao {
  final int id;
  final String codigo;
  final String produto;
  final String categoria;
  final int qtdVendida;
  final int qtdEstoque;
  final String criadoEm;
  final bool reposto;
  final String repostoEm;

  const Reposicao({
    required this.id,
    required this.codigo,
    required this.produto,
    required this.categoria,
    this.qtdVendida = 0,
    this.qtdEstoque = 0,
    this.criadoEm = '',
    this.reposto = false,
    this.repostoEm = '',
  });

  bool get pendente => !reposto;

  factory Reposicao.fromMap(Map<String, dynamic> map) {
    return Reposicao(
      id: _toInt(map['id']),
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      categoria: map['categoria']?.toString() ?? '',
      qtdVendida: _toInt(map['qtd_vendida']),
      qtdEstoque: _toInt(map['qtd_estoque']),
      criadoEm: map['criado_em']?.toString() ?? '',
      reposto: _toInt(map['reposto']) == 1,
      repostoEm: map['reposto_em']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toMap() => {
    'id': id,
    'codigo': codigo,
    'produto': produto,
    'categoria': categoria,
    'qtd_vendida': qtdVendida,
    'criado_em': criadoEm,
    'reposto': reposto ? 1 : 0,
    'reposto_em': repostoEm,
  };

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
