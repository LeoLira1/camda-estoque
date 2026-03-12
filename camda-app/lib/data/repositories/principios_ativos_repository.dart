import '../database/turso_client.dart';

class PrincipiosAtivosRepository {
  final TursoClient _client;

  PrincipiosAtivosRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<PrincipioAtivo>> getAll() async {
    final result = await _client.query('''
      SELECT produto, principio_ativo, COALESCE(categoria,'') as categoria
      FROM principios_ativos
      ORDER BY principio_ativo, produto
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(PrincipioAtivo.fromMap).toList();
  }

  /// Agrupa por princípio ativo, retornando lista com produtos relacionados.
  Future<List<GrupoPrincipioAtivo>> getAgrupados() async {
    final todos = await getAll();
    final map = <String, List<PrincipioAtivo>>{};
    for (final pa in todos) {
      map.putIfAbsent(pa.principioAtivo, () => []).add(pa);
    }

    // Busca quantidades do estoque para cada produto
    final estResult = await _client.query(
      'SELECT produto, qtd_sistema FROM estoque_mestre',
    );
    final qtdMap = <String, int>{};
    if (!estResult.hasError) {
      for (final row in estResult.toMaps()) {
        final nome = row['produto']?.toString().toUpperCase() ?? '';
        qtdMap[nome] = _toInt(row['qtd_sistema']);
      }
    }

    final grupos = map.entries.map((e) {
      final produtos = e.value;
      int totalQtd = 0;
      for (final p in produtos) {
        totalQtd += qtdMap[p.produto.toUpperCase()] ?? 0;
      }
      return GrupoPrincipioAtivo(
        principioAtivo: e.key,
        categoria: produtos.first.categoria,
        produtos: produtos,
        totalQuantidade: totalQtd,
      );
    }).toList()
      ..sort((a, b) => b.totalQuantidade.compareTo(a.totalQuantidade));

    return grupos;
  }

  Future<void> upsert(String produto, String principioAtivo, String categoria) async {
    await _client.query('''
      INSERT INTO principios_ativos (produto, principio_ativo, categoria)
      VALUES (?, ?, ?)
      ON CONFLICT(produto) DO UPDATE SET
        principio_ativo = excluded.principio_ativo,
        categoria = excluded.categoria
    ''', [produto.trim().toUpperCase(), principioAtivo.trim(), categoria.trim()]);
  }

  /// Busca fuzzy simples: retorna PAs que contêm o termo.
  Future<List<GrupoPrincipioAtivo>> buscar(String termo) async {
    final todos = await getAgrupados();
    final lower = termo.toLowerCase();
    return todos.where((g) =>
      g.principioAtivo.toLowerCase().contains(lower) ||
      g.produtos.any((p) => p.produto.toLowerCase().contains(lower))
    ).toList();
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}

class PrincipioAtivo {
  final String produto;
  final String principioAtivo;
  final String categoria;

  const PrincipioAtivo({
    required this.produto,
    required this.principioAtivo,
    this.categoria = '',
  });

  factory PrincipioAtivo.fromMap(Map<String, dynamic> map) => PrincipioAtivo(
    produto: map['produto']?.toString() ?? '',
    principioAtivo: map['principio_ativo']?.toString() ?? '',
    categoria: map['categoria']?.toString() ?? '',
  );
}

class GrupoPrincipioAtivo {
  final String principioAtivo;
  final String categoria;
  final List<PrincipioAtivo> produtos;
  final int totalQuantidade;

  const GrupoPrincipioAtivo({
    required this.principioAtivo,
    this.categoria = '',
    required this.produtos,
    this.totalQuantidade = 0,
  });

  int get numProdutos => produtos.length;
}
