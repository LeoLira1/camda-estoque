import '../database/turso_client.dart';
import '../models/produto.dart';
import '../../core/services/cache_service.dart';

class EstoqueRepository {
  final TursoClient _client;

  EstoqueRepository({TursoClient? client})
      : _client = client ?? TursoClient.instance;

  /// Produtos ignorados em todo o sistema (inseridos por engano na planilha).
  /// Manter em MAIÚSCULAS — comparação é case-insensitive via UPPER() no SQL.
  static const _produtosIgnorados = [
    'AÇÚCAR',
    'ACUCAR',
    'ARQUIVO MORTO',
    // Adicione outros conforme necessário
  ];

  /// Retorna todos os produtos do estoque_mestre.
  Future<List<Produto>> getAll({String? categoria, String? status}) async {
    var sql = '''
      SELECT codigo, produto, categoria, qtd_sistema, qtd_fisica,
             diferenca, nota, status, ultima_contagem, criado_em,
             COALESCE(observacoes, '') as observacoes
      FROM estoque_mestre
    ''';
    final conditions = <String>[];
    final args = <dynamic>[];

    if (categoria != null && categoria.isNotEmpty) {
      conditions.add('categoria = ?');
      args.add(categoria);
    }
    if (status != null && status.isNotEmpty) {
      conditions.add('status = ?');
      args.add(status);
    }
    if (_produtosIgnorados.isNotEmpty) {
      final ph = _produtosIgnorados.map((_) => '?').join(', ');
      conditions.add('UPPER(TRIM(produto)) NOT IN ($ph)');
      args.addAll(_produtosIgnorados);
    }

    if (conditions.isNotEmpty) {
      sql += ' WHERE ${conditions.join(' AND ')}';
    }
    sql += ' ORDER BY produto ASC';

    try {
      final result = await _client.query(sql, args);
      if (result.hasError) throw TursoException(result.error!);
      final produtos = result.toMaps().map(Produto.fromMap).toList();
      // Salva no cache apenas para getAll sem filtros (dados completos)
      if (categoria == null && status == null) {
        await CacheService.saveEstoque(produtos.map((p) => p.toMap()).toList());
        CacheService.isOffline = false;
      }
      return produtos;
    } catch (e) {
      // Tenta fallback do cache quando a rede falha
      if (categoria == null && status == null) {
        final (cached, _) = await CacheService.loadEstoque();
        if (cached != null && cached.isNotEmpty) {
          CacheService.isOffline = true;
          final fromIgnored = _produtosIgnorados.toSet();
          return cached
              .map(Produto.fromMap)
              .where((p) => !fromIgnored.contains(p.produto.toUpperCase().trim()))
              .toList();
        }
      }
      rethrow;
    }
  }

  /// Busca produto por código.
  Future<Produto?> getByCode(String codigo) async {
    final result = await _client.query(
      '''SELECT codigo, produto, categoria, qtd_sistema, qtd_fisica,
                diferenca, nota, status, ultima_contagem, criado_em,
                COALESCE(observacoes, '') as observacoes
         FROM estoque_mestre WHERE codigo = ?''',
      [codigo],
    );
    if (result.hasError) throw TursoException(result.error!);
    final maps = result.toMaps();
    return maps.isEmpty ? null : Produto.fromMap(maps.first);
  }

  /// Retorna lista de categorias distintas.
  Future<List<String>> getCategorias() async {
    final result = await _client.query(
      'SELECT DISTINCT categoria FROM estoque_mestre ORDER BY categoria',
    );
    if (result.hasError) throw TursoException(result.error!);
    return result.rows
        .map((r) => r.first?.toString() ?? '')
        .where((c) => c.isNotEmpty)
        .toList();
  }

  /// Resumo rápido para o dashboard.
  Future<EstoqueResumo> getResumo() async {
    final ph = _produtosIgnorados.map((_) => '?').join(', ');
    final whereClause = _produtosIgnorados.isNotEmpty
        ? 'WHERE UPPER(TRIM(produto)) NOT IN ($ph)'
        : '';
    try {
      final results = await Future.wait([
        _client.query('''
          SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok,
            SUM(qtd_sistema) as total_itens
          FROM estoque_mestre
          $whereClause
        ''', [..._produtosIgnorados]),
        _client.query(
          "SELECT SUM(CASE WHEN status='falta' THEN 1 ELSE 0 END) as faltas, "
          "SUM(CASE WHEN status='sobra' THEN 1 ELSE 0 END) as sobras FROM divergencias",
        ),
      ]);
      final r1 = results[0];
      final r2 = results[1];
      if (r1.hasError) throw TursoException(r1.error!);
      if (r2.hasError) throw TursoException(r2.error!);
      final row1 = r1.toMaps().firstOrNull ?? {};
      final row2 = r2.toMaps().firstOrNull ?? {};
      return EstoqueResumo(
        total: _toInt(row1['total']),
        faltas: _toInt(row2['faltas']),
        sobras: _toInt(row2['sobras']),
        ok: _toInt(row1['ok']),
        totalItens: _toInt(row1['total_itens']),
      );
    } catch (_) {
      // Calcula resumo a partir do cache local se rede falhar
      final (cached, _) = await CacheService.loadEstoque();
      if (cached != null && cached.isNotEmpty) {
        final produtos = cached.map(Produto.fromMap).toList();
        return EstoqueResumo(
          total: produtos.length,
          faltas: produtos.where((p) => p.status == 'falta').length,
          sobras: produtos.where((p) => p.status == 'sobra').length,
          ok: produtos.where((p) => p.status == 'ok').length,
          totalItens: produtos.fold(0, (s, p) => s + p.qtdSistema),
        );
      }
      rethrow;
    }
  }

  /// Atualiza quantidade física e status de um produto.
  Future<void> updateContagem({
    required String codigo,
    required int qtdFisica,
    required String status,
    String nota = '',
  }) async {
    final now = DateTime.now().toIso8601String();
    await _client.query(
      '''UPDATE estoque_mestre
         SET qtd_fisica = ?, diferenca = (? - qtd_sistema), status = ?,
             nota = ?, ultima_contagem = ?
         WHERE codigo = ?''',
      [qtdFisica, qtdFisica, status, nota, now, codigo],
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}

class EstoqueResumo {
  final int total;
  final int faltas;
  final int sobras;
  final int ok;
  final int totalItens;

  const EstoqueResumo({
    this.total = 0,
    this.faltas = 0,
    this.sobras = 0,
    this.ok = 0,
    this.totalItens = 0,
  });
}
