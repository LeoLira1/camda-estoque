import '../database/turso_client.dart';
import '../models/avaria.dart';
import '../../core/services/cache_service.dart';
import '../../core/services/connectivity_service.dart';
import '../../core/services/sync_queue_service.dart';

class AvariasRepository {
  final TursoClient _client;

  AvariasRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<Avaria>> getAll({bool apenasAbertas = false}) async {
    var sql = '''
      SELECT id, codigo, produto, qtd_avariada, motivo, status, registrado_em, resolvido_em
      FROM avarias
    ''';
    final args = <dynamic>[];
    if (apenasAbertas) {
      sql += " WHERE status = 'aberto'";
    }
    sql += ' ORDER BY registrado_em DESC';

    try {
      final result = await _client.query(sql, args);
      if (result.hasError) throw TursoException(result.error!);
      final rows = result.toMaps();
      // Salva cache completo (sem filtro) quando não há filtro aplicado
      if (!apenasAbertas) {
        await CacheService.saveAvarias(rows);
        CacheService.isOffline = false;
      }
      return rows.map(Avaria.fromMap).toList();
    } catch (e) {
      final (cached, _) = await CacheService.loadAvarias();
      if (cached != null && cached.isNotEmpty) {
        CacheService.isOffline = true;
        var list = cached.map(Avaria.fromMap).toList();
        if (apenasAbertas) {
          list = list.where((a) => a.status == 'aberto').toList();
        }
        return list;
      }
      rethrow;
    }
  }

  Future<void> registrar({
    required String codigo,
    required String produto,
    required int qtd,
    required String motivo,
  }) async {
    final now = DateTime.now().toIso8601String();
    const sql = '''INSERT INTO avarias (codigo, produto, qtd_avariada, motivo, status, registrado_em)
       VALUES (?, ?, ?, ?, 'aberto', ?)''';
    final args = [codigo, produto, qtd, motivo, now];

    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, args);
      await CacheService.insertAvaria({
        'id': -DateTime.now().millisecondsSinceEpoch, // ID temporário negativo
        'codigo': codigo,
        'produto': produto,
        'qtd_avariada': qtd,
        'motivo': motivo,
        'status': 'aberto',
        'registrado_em': now,
        'resolvido_em': null,
      });
      return;
    }
    await _client.query(sql, args);
  }

  Future<void> resolver(int id) async {
    final now = DateTime.now().toIso8601String();
    const sql = "UPDATE avarias SET status = 'resolvido', resolvido_em = ? WHERE id = ?";

    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(sql, [now, id]);
      await CacheService.resolverAvaria(id, now);
      return;
    }
    await _client.query(sql, [now, id]);
  }

  Future<int> countAbertas() async {
    try {
      final result = await _client.query(
        "SELECT COUNT(*) FROM avarias WHERE status = 'aberto'",
      );
      if (result.hasError) throw TursoException(result.error!);
      return _toInt(result.rows.firstOrNull?.firstOrNull);
    } catch (_) {
      // Offline: conta a partir do cache
      final (cached, _) = await CacheService.loadAvarias();
      if (cached != null) {
        return cached.where((r) => r['status'] == 'aberto').length;
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
