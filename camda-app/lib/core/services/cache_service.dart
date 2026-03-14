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
