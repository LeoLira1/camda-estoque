import '../database/turso_client.dart';
import '../models/reposicao.dart';
import '../../core/services/cache_service.dart';
import '../../core/services/connectivity_service.dart';
import '../../core/services/sync_queue_service.dart';

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

    try {
      final result = await _client.query(sql);
      if (result.hasError) throw TursoException(result.error!);
      final rows = result.toMaps();
      if (!apenasPendentes) {
        await CacheService.saveReposicao(rows);
        CacheService.isOffline = false;
      }
      return rows.map(Reposicao.fromMap).toList();
    } catch (e) {
      final (cached, _) = await CacheService.loadReposicao();
      if (cached != null && cached.isNotEmpty) {
        CacheService.isOffline = true;
        var list = cached.map(Reposicao.fromMap).toList();
        if (apenasPendentes) {
          list = list.where((r) => r.reposto == 0).toList();
        }
        return list;
      }
      rethrow;
    }
  }

  Future<void> marcarReposto(int id) async {
    final now = DateTime.now().toIso8601String();
    const sql = 'UPDATE reposicao_loja SET reposto = 1, reposto_em = ? WHERE id = ?';

    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, [now, id]);
      await CacheService.marcarRepostoCache(id, now);
      return;
    }
    await _client.query(sql, [now, id]);
  }

  Future<void> adicionarItem({
    required String codigo,
    required String produto,
    required String categoria,
    required int qtdVendida,
  }) async {
    final now = DateTime.now().toIso8601String();
    const sql =
        '''INSERT INTO reposicao_loja (codigo, produto, categoria, qtd_vendida, criado_em, reposto)
         VALUES (?, ?, ?, ?, ?, 0)''';
    final args = [codigo, produto, categoria, qtdVendida, now];

    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, args);
      await CacheService.insertReposicaoItem({
        'id': -DateTime.now().millisecondsSinceEpoch,
        'codigo': codigo,
        'produto': produto,
        'categoria': categoria,
        'qtd_vendida': qtdVendida,
        'criado_em': now,
        'reposto': 0,
        'reposto_em': null,
        'qtd_estoque': 0,
      });
      return;
    }
    await _client.query(sql, args);
  }

  Future<int> countPendentes() async {
    try {
      final result = await _client.query(
        'SELECT COUNT(*) FROM reposicao_loja WHERE reposto = 0',
      );
      if (result.hasError) throw TursoException(result.error!);
      return _toInt(result.rows.firstOrNull?.firstOrNull);
    } catch (_) {
      final (cached, _) = await CacheService.loadReposicao();
      if (cached != null) {
        return cached.where((r) => r['reposto'] == 0).length;
      }
      return 0;
    }
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
