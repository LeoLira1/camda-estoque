import '../../core/utils/date_utils.dart';
import '../../core/constants/app_constants.dart';

/// Modelo espelhando a tabela `validade_lotes`.
class ValidadeLote {
  final int id;
  final String filial;
  final String grupo;
  final String produto;
  final String lote;
  final String fabricacao;
  final String vencimento;
  final int quantidade;
  final double valor;
  final String uploadedEm;

  const ValidadeLote({
    required this.id,
    this.filial = '',
    required this.grupo,
    required this.produto,
    required this.lote,
    this.fabricacao = '',
    required this.vencimento,
    this.quantidade = 0,
    this.valor = 0,
    this.uploadedEm = '',
  });

  DateTime? get vencimentoDate => CamdaDateUtils.parseFlexible(vencimento);

  int get diasParaVencer {
    final dt = vencimentoDate;
    if (dt == null) return 9999;
    return CamdaDateUtils.diasParaVencer(dt);
  }

  bool get isVencido => diasParaVencer < 0;
  bool get isCritico => !isVencido && diasParaVencer <= AppConstants.diasAlertaVencimentoCritico;
  bool get isAlerta => !isVencido && !isCritico && diasParaVencer <= AppConstants.diasAlertaVencimento;
  bool get isOk => !isVencido && diasParaVencer > AppConstants.diasAlertaVencimento;

  String get statusLabel {
    if (isVencido) return 'Vencido';
    if (isCritico) return 'Crítico';
    if (isAlerta) return 'Alerta';
    return 'OK';
  }

  factory ValidadeLote.fromMap(Map<String, dynamic> map) {
    return ValidadeLote(
      id: _toInt(map['id']),
      filial: map['filial']?.toString() ?? '',
      grupo: map['grupo']?.toString() ?? '',
      produto: map['produto']?.toString() ?? '',
      lote: map['lote']?.toString() ?? '',
      fabricacao: map['fabricacao']?.toString() ?? '',
      vencimento: map['vencimento']?.toString() ?? '',
      quantidade: _toInt(map['quantidade']),
      valor: _toDouble(map['valor']),
      uploadedEm: map['uploaded_em']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toMap() => {
    'id': id,
    'filial': filial,
    'grupo': grupo,
    'produto': produto,
    'lote': lote,
    'fabricacao': fabricacao,
    'vencimento': vencimento,
    'quantidade': quantidade,
    'valor': valor,
    'uploaded_em': uploadedEm,
  };

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  static double _toDouble(dynamic v) {
    if (v == null) return 0.0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v.toString()) ?? 0.0;
  }
}
