import '../database/turso_client.dart';
import '../models/contagem_item.dart';

class ContagemRepository {
  final TursoClient _client;

  ContagemRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<ContagemItem>> getAll() async {
    final result = await _client.query('''
      SELECT id, upload_id, codigo, produto, categoria, qtd_estoque,
             status, COALESCE(motivo,'') as motivo,
             COALESCE(qtd_divergencia, 0) as qtd_divergencia, registrado_em
      FROM contagem_itens
      ORDER BY produto ASC
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(ContagemItem.fromMap).toList();
  }

  /// Marca item como OK (contagem confere).
  Future<void> marcarOk(int id) async {
    await _client.query(
      "UPDATE contagem_itens SET status='ok', qtd_divergencia=0, motivo='' WHERE id=?",
      [id],
    );
  }

  /// Marca item como divergente com quantidade e motivo.
  Future<void> marcarDivergente(int id, int qtdDivergencia, String motivo) async {
    await _client.query(
      "UPDATE contagem_itens SET status='divergente', qtd_divergencia=?, motivo=? WHERE id=?",
      [qtdDivergencia, motivo.trim(), id],
    );
  }

  /// Reseta item para pendente.
  Future<void> resetar(int id) async {
    await _client.query(
      "UPDATE contagem_itens SET status='pendente', qtd_divergencia=0, motivo='' WHERE id=?",
      [id],
    );
  }

  Future<ContagemResumo> getResumo() async {
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
