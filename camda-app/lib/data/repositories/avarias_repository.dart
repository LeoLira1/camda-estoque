import '../database/turso_client.dart';
import '../models/avaria.dart';

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

    final result = await _client.query(sql, args);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Avaria.fromMap).toList();
  }

  Future<void> registrar({
    required String codigo,
    required String produto,
    required int qtd,
    required String motivo,
  }) async {
    final now = DateTime.now().toIso8601String();
    await _client.query(
      '''INSERT INTO avarias (codigo, produto, qtd_avariada, motivo, status, registrado_em)
         VALUES (?, ?, ?, ?, 'aberto', ?)''',
      [codigo, produto, qtd, motivo, now],
    );
  }

  Future<void> resolver(int id) async {
    final now = DateTime.now().toIso8601String();
    await _client.query(
      "UPDATE avarias SET status = 'resolvido', resolvido_em = ? WHERE id = ?",
      [now, id],
    );
  }

  Future<int> countAbertas() async {
    final result = await _client.query(
      "SELECT COUNT(*) FROM avarias WHERE status = 'aberto'",
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
