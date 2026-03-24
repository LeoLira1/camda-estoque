import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Representa uma operação SQL pendente de sincronização com o Turso.
class PendingOp {
  final String id;
  final String sql;
  final List<dynamic> args;
  final int timestamp;
  int retries;

  PendingOp({
    required this.id,
    required this.sql,
    required this.args,
    required this.timestamp,
    this.retries = 0,
  });

  Map<String, dynamic> toMap() => {
        'id': id,
        'sql': sql,
        'args': args,
        'timestamp': timestamp,
        'retries': retries,
      };

  factory PendingOp.fromMap(Map<String, dynamic> m) => PendingOp(
        id: m['id'] as String,
        sql: m['sql'] as String,
        args: (m['args'] as List<dynamic>),
        timestamp: m['timestamp'] as int,
        retries: (m['retries'] as int?) ?? 0,
      );
}

/// Fila persistente de mutações offline.
///
/// Quando não há internet as escritas são enfileiradas aqui.
/// O [ConnectivityService] drena esta fila ao reconectar.
class SyncQueueService {
  static const _key = 'sync_queue_v1';
  static const int _maxRetries = 3;

  /// Número de operações pendentes — use com [ValueListenableBuilder] na UI.
  static final ValueNotifier<int> pendingCount = ValueNotifier(0);

  // ─── Escrita ────────────────────────────────────────────────────────────────

  /// Adiciona uma operação SQL à fila.
  static Future<void> enqueue(String sql, List<dynamic> args) async {
    final prefs = await SharedPreferences.getInstance();
    final list = _loadRaw(prefs);
    final op = PendingOp(
      id: _genId(),
      sql: sql,
      args: args,
      timestamp: DateTime.now().millisecondsSinceEpoch,
    );
    list.add(op.toMap());
    await prefs.setString(_key, jsonEncode(list));
    pendingCount.value = list.length;
  }

  // ─── Leitura ────────────────────────────────────────────────────────────────

  /// Retorna todas as operações pendentes em ordem de chegada.
  static Future<List<PendingOp>> getAll() async {
    final prefs = await SharedPreferences.getInstance();
    return _loadRaw(prefs).map(PendingOp.fromMap).toList();
  }

  // ─── Remoção ────────────────────────────────────────────────────────────────

  /// Remove uma operação da fila pelo [id].
  static Future<void> remove(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final list = _loadRaw(prefs)..removeWhere((m) => m['id'] == id);
    await prefs.setString(_key, jsonEncode(list));
    pendingCount.value = list.length;
  }

  /// Incrementa as tentativas de uma operação.
  /// Se atingir [_maxRetries], remove da fila (descarta com log).
  static Future<void> recordFailure(String id) async {
    final prefs = await SharedPreferences.getInstance();
    final list = _loadRaw(prefs);
    final idx = list.indexWhere((m) => m['id'] == id);
    if (idx < 0) return;
    final retries = ((list[idx]['retries'] as int?) ?? 0) + 1;
    if (retries >= _maxRetries) {
      debugPrint('[SyncQueue] descartando op $id após $_maxRetries falhas: ${list[idx]['sql']}');
      list.removeAt(idx);
    } else {
      list[idx] = {...list[idx], 'retries': retries};
    }
    await prefs.setString(_key, jsonEncode(list));
    pendingCount.value = list.length;
  }

  /// Limpa toda a fila (usar com cuidado).
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
    pendingCount.value = 0;
  }

  /// Inicializa o contador ao subir o app.
  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    pendingCount.value = _loadRaw(prefs).length;
  }

  // ─── Helpers ────────────────────────────────────────────────────────────────

  static List<Map<String, dynamic>> _loadRaw(SharedPreferences prefs) {
    final raw = prefs.getString(_key);
    if (raw == null) return [];
    try {
      final decoded = jsonDecode(raw) as List<dynamic>;
      return decoded.cast<Map<String, dynamic>>();
    } catch (_) {
      return [];
    }
  }

  static String _genId() {
    final ts = DateTime.now().millisecondsSinceEpoch;
    final rnd = Random().nextInt(99999);
    return '${ts}_$rnd';
  }
}
