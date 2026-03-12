import '../database/turso_client.dart';
import '../models/pendencia.dart';

class PendenciasRepository {
  final TursoClient _client;

  PendenciasRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<Pendencia>> getAll() async {
    final result = await _client.query('''
      SELECT id, foto_base64, data_registro, COALESCE(observacao, '') as observacao
      FROM pendencias_entrega
      ORDER BY data_registro ASC
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Pendencia.fromMap).toList();
  }

  Future<void> inserir({
    required String fotoBase64,
    String observacao = '',
  }) async {
    final hoje = DateTime.now().toIso8601String().substring(0, 10);
    await _client.query(
      'INSERT INTO pendencias_entrega (foto_base64, data_registro, observacao) VALUES (?, ?, ?)',
      [fotoBase64, hoje, observacao.trim()],
    );
  }

  Future<void> deletar(int id) async {
    await _client.query(
      'DELETE FROM pendencias_entrega WHERE id = ?',
      [id],
    );
  }

  Future<void> atualizarObservacao(int id, String observacao) async {
    await _client.query(
      'UPDATE pendencias_entrega SET observacao = ? WHERE id = ?',
      [observacao.trim(), id],
    );
  }

  int diasDesde(String dataRegistro) {
    try {
      final dt = DateTime.parse(dataRegistro);
      return DateTime.now().difference(dt).inDays;
    } catch (_) {
      return 0;
    }
  }
}
