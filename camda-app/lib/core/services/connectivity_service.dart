import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import '../../data/database/turso_client.dart';
import 'sync_queue_service.dart';

/// Chave global do Navigator para mostrar snackbars de sync fora do BuildContext.
final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

/// Monitora a conectividade de rede e sincroniza a fila offline ao reconectar.
///
/// Uso:
/// ```dart
/// // Em main() antes de runApp:
/// await ConnectivityService.init();
/// ```
class ConnectivityService {
  ConnectivityService._();

  /// Estado atual de conexão.
  static bool isOnline = true;

  /// Notificador reativo — use com [ValueListenableBuilder] na UI.
  static final ValueNotifier<bool> status = ValueNotifier(true);

  static StreamSubscription<List<ConnectivityResult>>? _sub;
  static bool _syncing = false;

  // ─── Inicialização ────────────────────────────────────────────────────────

  /// Inicializa o serviço: verifica estado atual e começa a escutar mudanças.
  /// Chamar uma vez em [main()] antes de [runApp].
  static Future<void> init() async {
    await SyncQueueService.init();

    // Verifica estado inicial
    final results = await Connectivity().checkConnectivity();
    final online = _hasInternet(results);
    isOnline = online;
    status.value = online;

    // Escuta mudanças de conectividade
    _sub = Connectivity().onConnectivityChanged.listen(_onConnectivityChanged);
  }

  /// Para o monitoramento (raramente necessário).
  static void dispose() {
    _sub?.cancel();
    _sub = null;
  }

  // ─── Sync manual ─────────────────────────────────────────────────────────

  /// Drena a fila de operações pendentes agora.
  /// Chamado automaticamente ao reconectar, mas pode ser chamado manualmente.
  static Future<void> syncNow() async {
    if (_syncing) return;
    _syncing = true;

    try {
      final ops = await SyncQueueService.getAll();
      if (ops.isEmpty) {
        _syncing = false;
        return;
      }

      debugPrint('[Connectivity] sincronizando ${ops.length} op(s) pendente(s)...');
      int synced = 0;

      for (final op in ops) {
        try {
          await TursoClient.instance.query(op.sql, op.args);
          await SyncQueueService.remove(op.id);
          synced++;
        } catch (e) {
          debugPrint('[Connectivity] falha ao sincronizar op ${op.id}: $e');
          await SyncQueueService.recordFailure(op.id);
        }
      }

      if (synced > 0) {
        _showSyncSnackbar(synced);
      }
    } finally {
      _syncing = false;
    }
  }

  // ─── Privado ──────────────────────────────────────────────────────────────

  static void _onConnectivityChanged(List<ConnectivityResult> results) {
    final online = _hasInternet(results);
    if (online == isOnline) return; // sem mudança real

    isOnline = online;
    status.value = online;
    debugPrint('[Connectivity] status: ${online ? "online" : "offline"}');

    if (online) {
      syncNow();
    }
  }

  static bool _hasInternet(List<ConnectivityResult> results) {
    return results.any((r) =>
        r == ConnectivityResult.mobile ||
        r == ConnectivityResult.wifi ||
        r == ConnectivityResult.ethernet);
  }

  static void _showSyncSnackbar(int count) {
    final ctx = navigatorKey.currentContext;
    if (ctx == null) return;
    ScaffoldMessenger.of(ctx).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.cloud_done_outlined, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Text(
              count == 1
                  ? 'Sincronizado: 1 alteração enviada'
                  : 'Sincronizado: $count alterações enviadas',
            ),
          ],
        ),
        backgroundColor: const Color(0xFF00D68F),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }
}
