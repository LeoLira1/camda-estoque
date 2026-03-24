import '../database/turso_client.dart';
import '../models/contagem_item.dart';
import '../../core/services/cache_service.dart';
import '../../core/services/connectivity_service.dart';
import '../../core/services/sync_queue_service.dart';

class ContagemRepository {
  final TursoClient _client;

  ContagemRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<ContagemItem>> getAll() async {
    try {
      final result = await _client.query('''
        SELECT ci.id, ci.upload_id, ci.codigo, ci.produto, ci.categoria, ci.qtd_estoque,
               ci.status, COALESCE(ci.motivo,'') as motivo,
               COALESCE(ci.qtd_divergencia, 0) as qtd_divergencia, ci.registrado_em,
               COALESCE(NULLIF(TRIM(em.observacoes),''), NULLIF(TRIM(em.nota),''), '') as nota_produto
        FROM contagem_itens ci
        LEFT JOIN estoque_mestre em ON UPPER(TRIM(em.codigo)) = UPPER(TRIM(ci.codigo))
        ORDER BY ci.produto ASC
      ''');
      if (result.hasError) throw TursoException(result.error!);
      final rows = result.toMaps();
      await CacheService.saveContagem(rows);
      CacheService.isOffline = false;
      return rows.map(ContagemItem.fromMap).toList();
    } catch (e) {
      final (cached, _) = await CacheService.loadContagem();
      if (cached != null && cached.isNotEmpty) {
        CacheService.isOffline = true;
        return cached.map(ContagemItem.fromMap).toList();
      }
      rethrow;
    }
  }

  /// Marca item como OK (contagem confere).
  Future<void> marcarOk(int id) async {
    const sql = "UPDATE contagem_itens SET status='ok', qtd_divergencia=0, motivo='' WHERE id=?";
    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, [id]);
      await CacheService.updateContagemItem(id, status: 'ok', qtdDivergencia: 0, motivo: '');
      return;
    }
    await _client.query(sql, [id]);
  }

  /// Marca item como divergente com quantidade e motivo.
  Future<void> marcarDivergente(int id, int qtdDivergencia, String motivo) async {
    const sql = "UPDATE contagem_itens SET status='divergente', qtd_divergencia=?, motivo=? WHERE id=?";
    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, [qtdDivergencia, motivo.trim(), id]);
      await CacheService.updateContagemItem(id,
          status: 'divergente', qtdDivergencia: qtdDivergencia, motivo: motivo.trim());
      return;
    }
    await _client.query(sql, [qtdDivergencia, motivo.trim(), id]);
  }

  /// Reseta item para pendente.
  Future<void> resetar(int id) async {
    const sql = "UPDATE contagem_itens SET status='pendente', qtd_divergencia=0, motivo='' WHERE id=?";
    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, [id]);
      await CacheService.updateContagemItem(id, status: 'pendente', qtdDivergencia: 0, motivo: '');
      return;
    }
    await _client.query(sql, [id]);
  }

  Future<ContagemResumo> getResumo() async {
    try {
      final result = await _client.query('''
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok,
          SUM(CASE WHEN status='divergente' THEN 1 ELSE 0 END) as divergentes,
          SUM(CASE WHEN status='pendente' THEN 1 ELSE 0 END) as pendentes
        FROM contagem_itens
      ''');
      if (result.hasError) throw TursoException(result.error!);
      final row = result.toMaps().firstOrNull ?? {};
      return ContagemResumo(
        total: _toInt(row['total']),
        ok: _toInt(row['ok']),
        divergentes: _toInt(row['divergentes']),
        pendentes: _toInt(row['pendentes']),
      );
    } catch (_) {
      // Offline: calcula resumo a partir do cache
      final (cached, _) = await CacheService.loadContagem();
      if (cached != null) {
        int total = cached.length, ok = 0, div = 0, pend = 0;
        for (final r in cached) {
          final s = r['status']?.toString() ?? 'pendente';
          if (s == 'ok') ok++;
          else if (s == 'divergente') div++;
          else pend++;
        }
        return ContagemResumo(total: total, ok: ok, divergentes: div, pendentes: pend);
      }
      return const ContagemResumo();
    }
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}

class ContagemResumo {
  final int total;
  final int ok;
  final int divergentes;
  final int pendentes;

  const ContagemResumo({
    this.total = 0,
    this.ok = 0,
    this.divergentes = 0,
    this.pendentes = 0,
  });

  double get pctConcluido => total > 0 ? ((ok + divergentes) / total) : 0.0;
}
