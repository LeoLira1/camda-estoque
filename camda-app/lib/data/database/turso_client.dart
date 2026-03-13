import 'dart:convert';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

/// Cliente HTTP para a API REST do Turso (libSQL HTTP protocol).
///
/// O Turso expõe um endpoint HTTP que aceita queries SQL:
///   POST /v2/pipeline
///   Authorization: Bearer <token>
///   Content-Type: application/json
class TursoClient {
  TursoClient._();

  static TursoClient? _instance;
  static TursoClient get instance => _instance ??= TursoClient._();

  String get _baseUrl {
    final raw = dotenv.env['TURSO_DATABASE_URL'] ?? '';
    // Turso HTTP API usa https://, mas a URL pode vir como libsql://
    return raw.replaceFirst(RegExp(r'^libsql://'), 'https://');
  }
  String get _token => dotenv.env['TURSO_AUTH_TOKEN'] ?? '';

  bool get isConfigured => _baseUrl.isNotEmpty && _token.isNotEmpty;

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $_token',
    'Content-Type': 'application/json',
  };

  /// Executa uma ou mais queries no pipeline do Turso.
  /// Retorna lista de resultados (um por query).
  Future<List<TursoResult>> execute(List<TursoQuery> queries) async {
    if (!isConfigured) {
      throw TursoException('Turso não configurado. Verifique TURSO_DATABASE_URL e TURSO_AUTH_TOKEN no .env');
    }

    final url = Uri.parse('$_baseUrl/v2/pipeline');
    final body = jsonEncode({
      'requests': queries.map((q) => q.toJson()).toList(),
    });

    final response = await http
        .post(url, headers: _headers, body: body)
        .timeout(const Duration(seconds: 15));

    if (response.statusCode != 200) {
      throw TursoException(
        'HTTP ${response.statusCode}: ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final results = (data['results'] as List<dynamic>? ?? []);

    return results.map((r) => TursoResult.fromJson(r as Map<String, dynamic>)).toList();
  }

  /// Atalho para query única.
  Future<TursoResult> query(String sql, [List<dynamic> args = const []]) async {
    final results = await execute([TursoQuery(sql: sql, args: args)]);
    return results.first;
  }

  /// Executa múltiplas queries em transação.
  Future<void> transaction(List<TursoQuery> queries) async {
    final allQueries = [
      TursoQuery(sql: 'BEGIN'),
      ...queries,
      TursoQuery(sql: 'COMMIT'),
    ];
    await execute(allQueries);
  }
}

// ── Models ──────────────────────────────────────────────────────────────────

class TursoQuery {
  final String sql;
  final List<dynamic> args;

  const TursoQuery({required this.sql, this.args = const []});

  Map<String, dynamic> toJson() => {
    'type': 'execute',
    'stmt': {
      'sql': sql,
      'args': args.map((a) => _encodeArg(a)).toList(),
    },
  };

  static Map<String, dynamic> _encodeArg(dynamic value) {
    if (value == null) return {'type': 'null'};
    if (value is int) return {'type': 'integer', 'value': value.toString()};
    if (value is double) return {'type': 'float', 'value': value};
    if (value is String) return {'type': 'text', 'value': value};
    if (value is bool) return {'type': 'integer', 'value': value ? '1' : '0'};
    return {'type': 'text', 'value': value.toString()};
  }
}

class TursoResult {
  final List<String> columns;
  final List<List<dynamic>> rows;
  final String? error;

  const TursoResult({
    required this.columns,
    required this.rows,
    this.error,
  });

  bool get hasError => error != null;

  factory TursoResult.fromJson(Map<String, dynamic> json) {
    if (json['type'] == 'error') {
      return TursoResult(
        columns: [],
        rows: [],
        error: json['error']?['message'] ?? 'Unknown error',
      );
    }

    final response = json['response'] as Map<String, dynamic>?;
    final result = response?['result'] as Map<String, dynamic>?;

    if (result == null) {
      return const TursoResult(columns: [], rows: []);
    }

    final cols = (result['cols'] as List<dynamic>? ?? [])
        .map((c) => (c as Map<String, dynamic>)['name']?.toString() ?? '')
        .toList();

    final rawRows = result['rows'] as List<dynamic>? ?? [];
    final rows = rawRows.map((row) {
      final cells = row as List<dynamic>;
      return cells.map((cell) {
        final cellMap = cell as Map<String, dynamic>;
        final type = cellMap['type']?.toString();
        final value = cellMap['value'];
        if (type == 'null' || value == null) return null;
        if (type == 'integer') return int.tryParse(value.toString()) ?? 0;
        if (type == 'float') return (value as num).toDouble();
        return value.toString();
      }).toList();
    }).toList();

    return TursoResult(columns: cols, rows: rows);
  }

  /// Converte resultado em lista de Map<String, dynamic>.
  List<Map<String, dynamic>> toMaps() {
    return rows.map((row) {
      final map = <String, dynamic>{};
      for (int i = 0; i < columns.length && i < row.length; i++) {
        map[columns[i]] = row[i];
      }
      return map;
    }).toList();
  }
}

class TursoException implements Exception {
  final String message;
  const TursoException(this.message);

  @override
  String toString() => 'TursoException: $message';
}
