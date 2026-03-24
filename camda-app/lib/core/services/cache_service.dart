import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Serviço de cache local com TTL.
///
/// Armazena dados como JSON em SharedPreferences.
/// Cada entrada tem um timestamp; se o dado estiver mais velho que [kTtlMinutes],
/// é considerado stale (ainda pode ser usado mas indica modo offline).
class CacheService {
  static const int kTtlMinutes = 15;

  static const _kEstoque = 'cache_estoque_v1';
  static const _kEstoqueTs = 'cache_estoque_ts_v1';
  static const _kVendas = 'cache_vendas_v1';
  static const _kVendasTs = 'cache_vendas_ts_v1';
  static const _kDashboard = 'cache_dashboard_v1';
  static const _kDashboardTs = 'cache_dashboard_ts_v1';

  static const _kContagem = 'cache_contagem_v1';
  static const _kContagemTs = 'cache_contagem_ts_v1';
  static const _kAvarias = 'cache_avarias_v1';
  static const _kAvariasTs = 'cache_avarias_ts_v1';
  static const _kReposicao = 'cache_reposicao_v1';
  static const _kReposicaoTs = 'cache_reposicao_ts_v1';

  // ─── Estoque ─────────────────────────────────────────────────────────────

  static Future<void> saveEstoque(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kEstoque, jsonEncode(rows));
    await prefs.setInt(_kEstoqueTs, DateTime.now().millisecondsSinceEpoch);
  }

  /// Retorna (dados, isStale). [isStale] = true se TTL expirou ou se não há cache.
  static Future<(List<Map<String, dynamic>>?, bool)> loadEstoque() async {
    return _load(_kEstoque, _kEstoqueTs);
  }

  // ─── Vendas ───────────────────────────────────────────────────────────────

  static Future<void> saveVendas(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kVendas, jsonEncode(rows));
    await prefs.setInt(_kVendasTs, DateTime.now().millisecondsSinceEpoch);
  }

  static Future<(List<Map<String, dynamic>>?, bool)> loadVendas() async {
    return _load(_kVendas, _kVendasTs);
  }

  // ─── Dashboard summary ────────────────────────────────────────────────────

  static Future<void> saveDashboard(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kDashboard, jsonEncode(data));
    await prefs.setInt(_kDashboardTs, DateTime.now().millisecondsSinceEpoch);
  }

  static Future<(Map<String, dynamic>?, bool)> loadDashboard() async {
    final (raw, stale) = await _load(_kDashboard, _kDashboardTs);
    if (raw == null || raw.isEmpty) return (null, stale);
    return (raw.first, stale);
  }

  // ─── Contagem ─────────────────────────────────────────────────────────────

  static Future<void> saveContagem(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kContagem, jsonEncode(rows));
    await prefs.setInt(_kContagemTs, DateTime.now().millisecondsSinceEpoch);
  }

  static Future<(List<Map<String, dynamic>>?, bool)> loadContagem() async {
    return _load(_kContagem, _kContagemTs);
  }

  /// Atualização otimista: modifica um item na cache de contagem sem ir ao servidor.
  static Future<void> updateContagemItem(
    int id, {
    required String status,
    required int qtdDivergencia,
    required String motivo,
  }) async {
    final (rows, _) = await loadContagem();
    if (rows == null) return;
    final updated = rows.map((r) {
      if (r['id'] == id) {
        return {...r, 'status': status, 'qtd_divergencia': qtdDivergencia, 'motivo': motivo};
      }
      return r;
    }).toList();
    await saveContagem(updated);
  }

  // ─── Avarias ──────────────────────────────────────────────────────────────

  static Future<void> saveAvarias(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAvarias, jsonEncode(rows));
    await prefs.setInt(_kAvariasTs, DateTime.now().millisecondsSinceEpoch);
  }

  static Future<(List<Map<String, dynamic>>?, bool)> loadAvarias() async {
    return _load(_kAvarias, _kAvariasTs);
  }

  /// Atualização otimista: insere uma avaria na cache local.
  static Future<void> insertAvaria(Map<String, dynamic> row) async {
    final (rows, _) = await loadAvarias();
    final list = rows ?? [];
    list.insert(0, row);
    await saveAvarias(list);
  }

  /// Atualização otimista: resolve uma avaria na cache local.
  static Future<void> resolverAvaria(int id, String resolvidoEm) async {
    final (rows, _) = await loadAvarias();
    if (rows == null) return;
    final updated = rows.map((r) {
      if (r['id'] == id) {
        return {...r, 'status': 'resolvido', 'resolvido_em': resolvidoEm};
      }
      return r;
    }).toList();
    await saveAvarias(updated);
  }

  // ─── Reposição ────────────────────────────────────────────────────────────

  static Future<void> saveReposicao(List<Map<String, dynamic>> rows) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kReposicao, jsonEncode(rows));
    await prefs.setInt(_kReposicaoTs, DateTime.now().millisecondsSinceEpoch);
  }

  static Future<(List<Map<String, dynamic>>?, bool)> loadReposicao() async {
    return _load(_kReposicao, _kReposicaoTs);
  }

  /// Atualização otimista: marca item de reposição como reposto na cache.
  static Future<void> marcarRepostoCache(int id, String repostoEm) async {
    final (rows, _) = await loadReposicao();
    if (rows == null) return;
    final updated = rows.map((r) {
      if (r['id'] == id) {
        return {...r, 'reposto': 1, 'reposto_em': repostoEm};
      }
      return r;
    }).toList();
    await saveReposicao(updated);
  }

  /// Atualização otimista: insere item de reposição na cache.
  static Future<void> insertReposicaoItem(Map<String, dynamic> row) async {
    final (rows, _) = await loadReposicao();
    final list = rows ?? [];
    list.insert(0, row);
    await saveReposicao(list);
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  static Future<(List<Map<String, dynamic>>?, bool)> _load(
      String dataKey, String tsKey) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(dataKey);
    if (raw == null) return (null, true);

    final ts = prefs.getInt(tsKey) ?? 0;
    final age = DateTime.now().millisecondsSinceEpoch - ts;
    final isStale = age > kTtlMinutes * 60 * 1000;

    try {
      final decoded = jsonDecode(raw) as List<dynamic>;
      return (decoded.cast<Map<String, dynamic>>(), isStale);
    } catch (_) {
      return (null, true);
    }
  }

  // ─── Modo offline ─────────────────────────────────────────────────────────

  /// true quando o último carregamento de estoque veio do cache local.
  static bool isOffline = false;

  static Future<void> clearAll() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kEstoque);
    await prefs.remove(_kEstoqueTs);
    await prefs.remove(_kVendas);
    await prefs.remove(_kVendasTs);
    await prefs.remove(_kDashboard);
    await prefs.remove(_kDashboardTs);
    await prefs.remove(_kContagem);
    await prefs.remove(_kContagemTs);
    await prefs.remove(_kAvarias);
    await prefs.remove(_kAvariasTs);
    await prefs.remove(_kReposicao);
    await prefs.remove(_kReposicaoTs);
  }

  /// Verifica se existe algum cache válido (não expirado).
  static Future<bool> hasValidCache() async {
    final prefs = await SharedPreferences.getInstance();
    final ts = prefs.getInt(_kEstoqueTs) ?? 0;
    if (ts == 0) return false;
    final age = DateTime.now().millisecondsSinceEpoch - ts;
    return age <= kTtlMinutes * 60 * 1000;
  }
}
