import '../database/turso_client.dart';

class PrincipiosAtivosRepository {
  final TursoClient _client;

  PrincipiosAtivosRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<PrincipioAtivo>> getAll() async {
    final result = await _client.query('''
      SELECT pa.produto,
             pa.principio_ativo,
             COALESCE(pa.categoria,'') AS categoria,
             COALESCE(fp.fabricante,'') AS empresa
      FROM principios_ativos pa
      LEFT JOIN fabricantes_produtos fp
             ON UPPER(fp.produto) = UPPER(pa.produto)
      ORDER BY pa.principio_ativo, pa.produto
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

  /// Busca fuzzy por bigramas (Jaccard similarity).
  /// Retorna resultados com score ≥ [threshold], ordenados por relevância.
  Future<List<GrupoPrincipioAtivo>> buscar(String termo) async {
    final todos = await getAgrupados();
    if (termo.isEmpty) return todos;
    const threshold = 0.20;

    final scored = <(double, GrupoPrincipioAtivo)>[];
    for (final g in todos) {
      double score = _fuzzyScore(termo, g.principioAtivo);
      for (final p in g.produtos) {
        final ps = _fuzzyScore(termo, p.produto);
        if (ps > score) score = ps;
      }
      if (score >= threshold) scored.add((score, g));
    }
    scored.sort((a, b) => b.$1.compareTo(a.$1));
    return scored.map((e) => e.$2).toList();
  }

  /// Score de similaridade por bigramas (0.0 → sem match, 1.0 → idêntico/contém).
  /// Substring exata = 1.0. Caso contrário usa índice Jaccard de bigramas.
  static double _fuzzyScore(String needle, String haystack) {
    if (needle.isEmpty) return 1.0;
    if (haystack.isEmpty) return 0.0;
    final n = needle.toLowerCase().trim();
    final h = haystack.toLowerCase().trim();
    if (h.contains(n)) return 1.0;

    Set<String> bigrams(String s) {
      final result = <String>{};
      for (int i = 0; i < s.length - 1; i++) {
        result.add(s[i] + s[i + 1]);
      }
      return result.isEmpty ? {s} : result;
    }

    final nb = bigrams(n);
    final hb = bigrams(h);
    final intersect = nb.intersection(hb).length;
    final union = nb.union(hb).length;
    return union == 0 ? 0.0 : intersect / union;
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
  final String empresa;

  const PrincipioAtivo({
    required this.produto,
    required this.principioAtivo,
    this.categoria = '',
    this.empresa = '',
  });

  factory PrincipioAtivo.fromMap(Map<String, dynamic> map) => PrincipioAtivo(
    produto: map['produto']?.toString() ?? '',
    principioAtivo: map['principio_ativo']?.toString() ?? '',
    categoria: map['categoria']?.toString() ?? '',
    empresa: map['empresa']?.toString() ?? '',
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
