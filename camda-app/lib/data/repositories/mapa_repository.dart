import '../database/turso_client.dart';
import '../models/mapa_posicao.dart';

class MapaRepository {
  final TursoClient _client;

  MapaRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  /// Retorna todos os racks ativos.
  Future<List<Rack>> getRacks() async {
    final result = await _client.query(
      'SELECT rack_id, nome, fileira, posicao, tem_face_b, ativo FROM racks WHERE ativo=1 ORDER BY fileira, posicao',
    );
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(Rack.fromMap).toList();
  }

  /// Retorna todos os paletes de um rack/face.
  Future<List<MapaPosicao>> getPaletesRack(String rua, String face) async {
    final result = await _client.query('''
      SELECT p.pos_key, p.rua, p.face, p.coluna, p.nivel,
             p.produto_id, mp.nome, p.quantidade, p.unidade, mp.cor_hex, p.atualizado
      FROM mapa_posicoes p
      LEFT JOIN mapa_produtos mp ON mp.produto_id = p.produto_id
      WHERE p.rua = ? AND p.face = ? AND p.produto_id IS NOT NULL
    ''', [rua, face]);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(MapaPosicao.fromMap).toList();
  }

  /// Retorna todos os paletes do armazém.
  Future<List<MapaPosicao>> getTodosPaletes() async {
    final result = await _client.query('''
      SELECT p.pos_key, p.rua, p.face, p.coluna, p.nivel,
             p.produto_id, mp.nome, p.quantidade, p.unidade, mp.cor_hex, p.atualizado
      FROM mapa_posicoes p
      LEFT JOIN mapa_produtos mp ON mp.produto_id = p.produto_id
      WHERE p.produto_id IS NOT NULL
      ORDER BY p.rua, p.face, p.coluna, p.nivel
    ''');
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(MapaPosicao.fromMap).toList();
  }

  /// Retorna todos os produtos do catálogo do mapa.
  Future<List<MapaProduto>> getProdutos() async {
    final result = await _client.query(
      'SELECT produto_id, nome, unidade_pad, cor_hex FROM mapa_produtos ORDER BY nome',
    );
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(MapaProduto.fromMap).toList();
  }

  /// Retorna ocupação geral por (rack, face).
  Future<Map<String, int>> getOcupacao() async {
    final result = await _client.query(
      'SELECT rua, face, COUNT(*) as ocupadas FROM mapa_posicoes WHERE produto_id IS NOT NULL GROUP BY rua, face',
    );
    if (result.hasError) throw TursoException(result.error!);
    final map = <String, int>{};
    for (final row in result.toMaps()) {
      final key = '${row['rua']}-${row['face']}';
      map[key] = _toInt(row['ocupadas']);
    }
    return map;
  }

  /// Busca produto em todas as posições do mapa.
  Future<List<MapaPosicao>> buscarProduto(String nomeParcial) async {
    final result = await _client.query('''
      SELECT p.pos_key, p.rua, p.face, p.coluna, p.nivel,
             p.produto_id, mp.nome, p.quantidade, p.unidade, mp.cor_hex, p.atualizado
      FROM mapa_posicoes p
      JOIN mapa_produtos mp ON mp.produto_id = p.produto_id
      WHERE LOWER(mp.nome) LIKE ?
      ORDER BY p.rua, p.face, p.coluna, p.nivel
    ''', ['%${nomeParcial.toLowerCase()}%']);
    if (result.hasError) throw TursoException(result.error!);
    return result.toMaps().map(MapaPosicao.fromMap).toList();
  }

  /// Insere ou atualiza palete numa posição.
  Future<void> upsertPalete({
    required String posKey,
    required String produtoId,
    required double quantidade,
    required String unidade,
  }) async {
    final parts = posKey.split('-');
    final rua = parts[0];
    final face = parts[1];
    final coluna = int.parse(parts[2].substring(1));
    final nivel = int.parse(parts[3].substring(1));
    final now = DateTime.now().toIso8601String();

    await _client.query('''
      INSERT INTO mapa_posicoes (pos_key, rua, face, coluna, nivel, produto_id, quantidade, unidade, atualizado)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(pos_key) DO UPDATE SET
        produto_id = excluded.produto_id,
        quantidade = excluded.quantidade,
        unidade    = excluded.unidade,
        atualizado = excluded.atualizado
    ''', [posKey, rua, face, coluna, nivel, produtoId, quantidade, unidade, now]);
  }

  /// Remove palete de uma posição.
  Future<void> deletePalete(String posKey) async {
    await _client.query(
      'DELETE FROM mapa_posicoes WHERE pos_key = ?',
      [posKey],
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}
