import '../database/turso_client.dart';
import '../models/venda.dart';

class VendasRepository {
  final TursoClient _client;

  VendasRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  Future<List<Venda>> getAll({String? grupo}) async {
    var sql = '''
      SELECT id, codigo, produto, grupo, qtd_vendida, qtd_estoque, data_upload
      FROM vendas_historico
    ''';
    final args = <dynamic>[];
    if (grupo != null && grupo.isNotEmpty) {
      sql += ' WHERE grupo = ?';
      args.add(grupo);
    }
    sql += ' ORDER BY data_upload DESC, qtd_vendida DESC';

    final result = await _client.query(sql, args);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Venda.fromMap).toList();
  }

  Future<List<String>> getGrupos() async {
    final result = await _client.query(
      'SELECT DISTINCT grupo FROM vendas_historico ORDER BY grupo',
    );
    if (result.hasError) throw TursoException(result.error!);
    return result.rows
        .map((r) => r.first?.toString() ?? '')
        .where((g) => g.isNotEmpty)
        .toList();
  }

  Future<List<Map<String, dynamic>>> getTopProdutos({int limit = 10}) async {
    final result = await _client.query('''
      SELECT produto, grupo,
             SUM(qtd_vendida) as total_vendido,
             MAX(data_upload) as ultima_data
      FROM vendas_historico
      GROUP BY produto
      ORDER BY total_vendido DESC
      LIMIT ?
    ''', [limit]);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps();
  }

  Future<List<Map<String, dynamic>>> getVendasPorGrupo() async {
    final result = await _client.query('''
      SELECT grupo, SUM(qtd_vendida) as total_vendido, COUNT(DISTINCT produto) as produtos
      FROM vendas_historico
      GROUP BY grupo
      ORDER BY total_vendido DESC
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps();
  }
}
