import '../database/turso_client.dart';
import '../models/avaria.dart';
import '../models/avaria_unidade.dart';
import '../../core/services/cache_service.dart';
import '../../core/services/connectivity_service.dart';
import '../../core/services/sync_queue_service.dart';

class AvariasRepository {
  final TursoClient _client;
  bool _migrated = false;

  AvariasRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  // ── Migration ─────────────────────────────────────────────────────────────

  /// Cria tabela avaria_unidades e adiciona coluna capacidade_litros se necessário.
  Future<void> _ensureMigrated() async {
    if (_migrated) return;
    try {
      await _client.query(
        'ALTER TABLE avarias ADD COLUMN capacidade_litros REAL DEFAULT 20.0',
      );
    } catch (_) {} // coluna já existe

    try {
      await _client.query('''
        CREATE TABLE IF NOT EXISTS avaria_unidades (
          id        INTEGER PRIMARY KEY AUTOINCREMENT,
          avaria_id INTEGER NOT NULL,
          uid       TEXT    NOT NULL UNIQUE,
          nivel     REAL    NOT NULL DEFAULT 50.0
        )
      ''');
    } catch (_) {}

    _migrated = true;
  }

  // ── Read ──────────────────────────────────────────────────────────────────

  Future<List<Avaria>> getAll({bool apenasAbertas = false}) async {
    await _ensureMigrated();

    var sql = '''
      SELECT id, codigo, produto, qtd_avariada, motivo, status,
             registrado_em, resolvido_em, capacidade_litros
      FROM avarias
    ''';
    if (apenasAbertas) sql += " WHERE status = 'aberto'";
    sql += ' ORDER BY registrado_em DESC';

    try {
      // Busca avarias e unidades em pipeline único
      final results = await _client.execute([
        TursoQuery(sql: sql),
        TursoQuery(sql: 'SELECT id, avaria_id, uid, nivel FROM avaria_unidades ORDER BY id'),
      ]);

      final avariaResult = results[0];
      final unidadeResult = results[1];

      if (avariaResult.hasError) throw TursoException(avariaResult.error!);

      final rows = avariaResult.toMaps();

      // Agrupa unidades por avaria_id
      final unidadesByAvariaId = <int, List<AvariaUnidade>>{};
      if (!unidadeResult.hasError) {
        for (final um in unidadeResult.toMaps()) {
          final u = AvariaUnidade.fromMap(um);
          unidadesByAvariaId.putIfAbsent(u.avariaId, () => []).add(u);
        }
      }

      if (!apenasAbertas) {
        await CacheService.saveAvarias(rows);
        CacheService.isOffline = false;
      }

      return rows.map((r) {
        final id = _toInt(r['id']);
        return Avaria.fromMap(r, unidades: unidadesByAvariaId[id] ?? []);
      }).toList();
    } catch (e) {
      final (cached, _) = await CacheService.loadAvarias();
      if (cached != null && cached.isNotEmpty) {
        CacheService.isOffline = true;
        var list = cached.map((r) => Avaria.fromMap(r)).toList();
        if (apenasAbertas) list = list.where((a) => a.status == 'aberto').toList();
        return list;
      }
      rethrow;
    }
  }

  // ── Write – avaria ────────────────────────────────────────────────────────

  Future<void> registrar({
    required String codigo,
    required String produto,
    required int qtd,
    required String motivo,
    double capacidadeLitros = 20.0,
  }) async {
    await _ensureMigrated();
    final now = DateTime.now().toIso8601String();
    const insertSql = '''
      INSERT INTO avarias
        (codigo, produto, qtd_avariada, motivo, status, registrado_em, capacidade_litros)
      VALUES (?, ?, ?, ?, 'aberto', ?, ?)
    ''';
    final args = [codigo, produto, qtd, motivo, now, capacidadeLitros];

    if (!ConnectivityService.isOnline) {
      await SyncQueueService.enqueue(insertSql, args);
      await CacheService.insertAvaria({
        'id': -DateTime.now().millisecondsSinceEpoch,
        'codigo': codigo,
        'produto': produto,
        'qtd_avariada': qtd,
        'motivo': motivo,
        'status': 'aberto',
        'registrado_em': now,
        'resolvido_em': null,
        'capacidade_litros': capacidadeLitros,
      });
      return;
    }

    // Insere avaria e obtém ID em pipeline único
    final results = await _client.execute([
      TursoQuery(sql: insertSql, args: args),
      TursoQuery(sql: 'SELECT last_insert_rowid()'),
    ]);

    if (results.length >= 2 && !results[1].hasError && results[1].rows.isNotEmpty) {
      final newId = _toInt(results[1].rows.first.firstOrNull);
      if (newId > 0) {
        final uid = '${newId}_${DateTime.now().millisecondsSinceEpoch}';
        await _client.query(
          'INSERT INTO avaria_unidades (avaria_id, uid, nivel) VALUES (?, ?, 50.0)',
          [newId, uid],
        );
      }
    }
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

  // ── Write – unidades ──────────────────────────────────────────────────────

  /// Atualiza o nível de preenchimento de uma unidade no Turso.
  Future<void> updateNivel(String uid, double nivel) async {
    await _ensureMigrated();
    await _client.query(
      'UPDATE avaria_unidades SET nivel = ? WHERE uid = ?',
      [nivel, uid],
    );
  }

  /// Adiciona uma nova unidade (galão/balde) a uma avaria existente.
  Future<AvariaUnidade> addUnidade(int avariaId) async {
    await _ensureMigrated();
    final uid = '${avariaId}_${DateTime.now().millisecondsSinceEpoch}';
    final results = await _client.execute([
      TursoQuery(
        sql: 'INSERT INTO avaria_unidades (avaria_id, uid, nivel) VALUES (?, ?, 50.0)',
        args: [avariaId, uid],
      ),
      TursoQuery(sql: 'SELECT last_insert_rowid()'),
    ]);
    final newId = (results.length >= 2 && !results[1].hasError && results[1].rows.isNotEmpty)
        ? _toInt(results[1].rows.first.firstOrNull)
        : 0;
    return AvariaUnidade(id: newId, avariaId: avariaId, uid: uid, nivel: 50.0);
  }

  /// Remove uma unidade pelo uid.
  Future<void> removeUnidade(String uid) async {
    await _ensureMigrated();
    await _client.query('DELETE FROM avaria_unidades WHERE uid = ?', [uid]);
  }

  // ── Aggregates ────────────────────────────────────────────────────────────

  Future<int> countAbertas() async {
    try {
      final result = await _client.query(
        "SELECT COUNT(*) FROM avarias WHERE status = 'aberto'",
      );
      if (result.hasError) throw TursoException(result.error!);
      return _toInt(result.rows.firstOrNull?.firstOrNull);
    } catch (_) {
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
