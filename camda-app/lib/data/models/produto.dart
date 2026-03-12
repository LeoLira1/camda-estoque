/// Modelo espelhando a tabela `estoque_mestre` do CAMDA.
class Produto {
  final String codigo;
  final String produto;
  final String categoria;
  final int qtdSistema;
  final int qtdFisica;
  final int diferenca;
  final String nota;
  final String status;       // 'ok' | 'falta' | 'sobra'
  final String ultimaContagem;
  final String criadoEm;
  final String observacoes;

  const Produto({
    required this.codigo,
    required this.produto,
    required this.categoria,
    this.qtdSistema = 0,
    this.qtdFisica = 0,
    this.diferenca = 0,
    this.nota = '',
    this.status = 'ok',
    this.ultimaContagem = '',
    this.criadoEm = '',
    this.observacoes = '',
  });

  factory Produto.fromMap(Map<String, dynamic> map) {
    return Produto(
      codigo: map['codigo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      categoria: map['categoria']?.toString() ?? '',
      qtdSistema: _toInt(map['qtd_sistema']),
      qtdFisica: _toInt(map['qtd_fisica']),
      diferenca: _toInt(map['diferenca']),
      nota: map['nota']?.toString() ?? '',
      status: map['status']?.toString() ?? 'ok',
      ultimaContagem: map['ultima_contagem']?.toString() ?? '',
      criadoEm: map['criado_em']?.toString() ?? '',
      observacoes: map['observacoes']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toMap() => {
    'codigo': codigo,
    'produto': produto,
    'categoria': categoria,
    'qtd_sistema': qtdSistema,
    'qtd_fisica': qtdFisica,
    'diferenca': diferenca,
    'nota': nota,
    'status': status,
    'ultima_contagem': ultimaContagem,
    'criado_em': criadoEm,
    'observacoes': observacoes,
  };

  Produto copyWith({
    String? codigo,
    String? produto,
    String? categoria,
    int? qtdSistema,
    int? qtdFisica,
    int? diferenca,
    String? nota,
    String? status,
    String? ultimaContagem,
    String? criadoEm,
    String? observacoes,
  }) {
    return Produto(
      codigo: codigo ?? this.codigo,
      produto: produto ?? this.produto,
      categoria: categoria ?? this.categoria,
      qtdSistema: qtdSistema ?? this.qtdSistema,
      qtdFisica: qtdFisica ?? this.qtdFisica,
      diferenca: diferenca ?? this.diferenca,
      nota: nota ?? this.nota,
      status: status ?? this.status,
      ultimaContagem: ultimaContagem ?? this.ultimaContagem,
      criadoEm: criadoEm ?? this.criadoEm,
      observacoes: observacoes ?? this.observacoes,
    );
  }

  bool get temDivergencia => status == 'falta' || status == 'sobra';
  bool get isOk => status == 'ok';

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  @override
  String toString() => 'Produto($codigo, $produto, status=$status)';
}
