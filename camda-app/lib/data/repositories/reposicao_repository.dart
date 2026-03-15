import '../database/turso_client.dart';
import '../models/reposicao.dart';

class ReposicaoRepository {
  final TursoClient _client;

  ReposicaoRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<Reposicao>> getAll({bool apenasPendentes = false}) async {
    var sql = '''
      SELECT r.id, r.codigo, r.produto, r.categoria, r.qtd_vendida,
             r.criado_em, r.reposto, r.reposto_em,
             COALESCE(e.qtd_sistema, 0) as qtd_estoque
      FROM reposicao_loja r
      LEFT JOIN estoque_mestre e ON TRIM(r.codigo) = TRIM(e.codigo)
    ''';
    if (apenasPendentes) sql += ' WHERE r.reposto = 0';
    sql += ' ORDER BY r.criado_em DESC';

    final result = await _client.query(sql);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Reposicao.fromMap).toList();
  }

  Future<void> marcarReposto(int id) async {
    final now = DateTime.now().toIso8601String();
    await _client.query(
      'UPDATE reposicao_loja SET reposto = 1, reposto_em = ? WHERE id = ?',
      [now, id],
    );
  }

  Future<void> adicionarItem({
    required String codigo,
    required String produto,
    required String categoria,
    required int qtdVendida,
  }) async {
    final now = DateTime.now().toIso8601String();
    await _client.query(
      '''INSERT INTO reposicao_loja (codigo, produto, categoria, qtd_vendida, criado_em, reposto)
         VALUES (?, ?, ?, ?, ?, 0)''',
      [codigo, produto, categoria, qtdVendida, now],
    );
  }

  Future<int> countPendentes() async {
    final result = await _client.query(
      'SELECT COUNT(*) FROM reposicao_loja WHERE reposto = 0',
    );
    if (result.hasError) throw TursoException(result.error!);
    return _toInt(result.rows.firstOrNull?.firstOrNull);
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
