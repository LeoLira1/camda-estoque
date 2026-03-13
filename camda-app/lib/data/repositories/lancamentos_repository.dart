import '../database/turso_client.dart';
import '../models/lancamento.dart';

class LancamentosRepository {
  final TursoClient _client;

  LancamentosRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<Lancamento>> getAll({int limit = 200}) async {
    final result = await _client.query('''
      SELECT id, codigo, produto, categoria, tipo, quantidade, motivo, registrado_em
      FROM lancamentos_manuais
      ORDER BY id DESC
      LIMIT ?
    ''', [limit]);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Lancamento.fromMap).toList();
  }

  Future<void> inserir({
    required String codigo,
    required String produto,
    required String categoria,
    required String tipo,
    required int quantidade,
    String motivo = '',
  }) async {
    final now = DateTime.now().toIso8601String();
    await _client.query('''
      INSERT INTO lancamentos_manuais
        (codigo, produto, categoria, tipo, quantidade, motivo, registrado_em)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [codigo, produto, categoria, tipo, quantidade, motivo.trim(), now]);
  }

  Future<void> excluir(int id) async {
    await _client.query(
      'DELETE FROM lancamentos_manuais WHERE id = ?',
      [id],
    );
  }

  Future<List<Map<String, dynamic>>> getResumoTipos() async {
    final result = await _client.query('''
      SELECT tipo,
             COUNT(*) as total_registros,
             SUM(quantidade) as total_quantidade
      FROM lancamentos_manuais
      GROUP BY tipo
      ORDER BY total_registros DESC
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps();
  }
}
