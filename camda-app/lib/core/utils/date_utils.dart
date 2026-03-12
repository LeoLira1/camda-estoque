import 'package:intl/intl.dart';

/// Utilitários de data/hora no fuso de Brasília (BRT = UTC-3).
class CamdaDateUtils {
  CamdaDateUtils._();

  static final _brt = DateTime.now().timeZoneOffset; // fallback
  static const _brtOffset = Duration(hours: -3);

  static DateTime nowBRT() => DateTime.now().toUtc().add(const Duration(hours: -3));

  static String formatDate(DateTime dt) =>
      DateFormat('dd/MM/yyyy').format(dt);

  static String formatDateTime(DateTime dt) =>
      DateFormat('dd/MM/yyyy HH:mm').format(dt);

  static String formatTime(DateTime dt) =>
      DateFormat('HH:mm').format(dt);

  static String formatDateBR(DateTime dt) {
    const meses = [
      '', 'jan', 'fev', 'mar', 'abr', 'mai', 'jun',
      'jul', 'ago', 'set', 'out', 'nov', 'dez'
    ];
    return '${dt.day} ${meses[dt.month]} ${dt.year}';
  }

  static String diaSemana(DateTime dt) {
    const dias = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    return dias[dt.weekday % 7];
  }

  static String diaSemanaFull(DateTime dt) {
    const dias = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
    return dias[dt.weekday % 7];
  }

  /// Retorna quantos dias faltam para a data de vencimento.
  static int diasParaVencer(DateTime vencimento) {
    final hoje = nowBRT();
    final hojeDate = DateTime(hoje.year, hoje.month, hoje.day);
    final vencDate = DateTime(vencimento.year, vencimento.month, vencimento.day);
    return vencDate.difference(hojeDate).inDays;
  }

  /// Parseia string ISO 8601 ou dd/MM/yyyy retornando DateTime ou null.
  static DateTime? parseFlexible(String? s) {
    if (s == null || s.isEmpty) return null;
    try {
      return DateTime.parse(s);
    } catch (_) {}
    try {
      return DateFormat('dd/MM/yyyy').parse(s);
    } catch (_) {}
    return null;
  }
}
