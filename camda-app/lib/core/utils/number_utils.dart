import 'package:intl/intl.dart';

/// Utilitários de formatação numérica no padrão brasileiro.
class CamdaNumberUtils {
  CamdaNumberUtils._();

  static final _intFmt = NumberFormat('#,##0', 'pt_BR');
  static final _decFmt = NumberFormat('#,##0.##', 'pt_BR');
  static final _currFmt = NumberFormat('R\$ #,##0.00', 'pt_BR');

  static String formatInt(num? value) {
    if (value == null) return '—';
    return _intFmt.format(value);
  }

  static String formatDec(num? value) {
    if (value == null) return '—';
    return _decFmt.format(value);
  }

  static String formatCurrency(num? value) {
    if (value == null) return '—';
    return _currFmt.format(value);
  }

  /// Formata volume: litros se disponível, senão kg, senão unidades.
  static String formatVolume({double? litros, double? kg, double? unidades}) {
    if (litros != null && litros > 0) return '${formatDec(litros)} L';
    if (kg != null && kg > 0) return '${formatDec(kg)} kg';
    if (unidades != null) return formatInt(unidades);
    return '—';
  }

  static String formatDiff(int diff) {
    if (diff == 0) return '=';
    if (diff > 0) return '+$diff';
    return '$diff';
  }
}
