import 'dart:ui';

/// Modelo para posição no mapa do armazém.
/// Espelha `mapa_posicoes` + `mapa_produtos`.
class MapaPosicao {
  final String posKey;   // ex: "R1-A-C1-N1"
  final String rua;      // "R1" .. "R10"
  final String face;     // "A" | "B"
  final int coluna;      // 1..13
  final int nivel;       // 1..4
  final String? produtoId;
  final String? produto;
  final double? quantidade;
  final String? unidade;
  final String? corHex;
  final String? atualizado;

  const MapaPosicao({
    required this.posKey,
    required this.rua,
    required this.face,
    required this.coluna,
    required this.nivel,
    this.produtoId,
    this.produto,
    this.quantidade,
    this.unidade,
    this.corHex,
    this.atualizado,
  });

  bool get isOcupada => produtoId != null && produtoId!.isNotEmpty;

  Color get cor {
    if (corHex == null) return const Color(0xFF4ADE80);
    try {
      final hex = corHex!.replaceAll('#', '');
      return Color(int.parse('FF$hex', radix: 16));
    } catch (_) {
      return const Color(0xFF4ADE80);
    }
  }

  factory MapaPosicao.fromMap(Map<String, dynamic> map) {
    return MapaPosicao(
      posKey: map['pos_key']?.toString() ?? '',
      rua: map['rua']?.toString() ?? '',
      face: map['face']?.toString() ?? '',
      coluna: _toInt(map['coluna']),
      nivel: _toInt(map['nivel']),
      produtoId: map['produto_id']?.toString(),
      produto: map['nome']?.toString() ?? map['produto']?.toString(),
      quantidade: _toDouble(map['quantidade']),
      unidade: map['unidade']?.toString(),
      corHex: map['cor_hex']?.toString(),
      atualizado: map['atualizado']?.toString(),
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }

  static double? _toDouble(dynamic v) {
    if (v == null) return null;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse(v.toString());
  }
}

/// Rack do armazém.
class Rack {
  final String rackId;    // "R1" .. "R10"
  final String nome;
  final int fileira;
  final int posicao;
  final bool temFaceB;
  final bool ativo;

  const Rack({
    required this.rackId,
    required this.nome,
    required this.fileira,
    required this.posicao,
    this.temFaceB = true,
    this.ativo = true,
  });

  factory Rack.fromMap(Map<String, dynamic> map) {
    return Rack(
      rackId: map['rack_id']?.toString() ?? '',
      nome: map['nome']?.toString() ?? '',
      fileira: _toInt(map['fileira']),
      posicao: _toInt(map['posicao']),
      temFaceB: _toInt(map['tem_face_b']) == 1,
      ativo: _toInt(map['ativo']) == 1,
    );
  }

  static int _toInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse(v.toString()) ?? 0;
  }
}

/// Produto cadastrado no catálogo do mapa.
class MapaProduto {
  final String produtoId;
  final String nome;
  final String unidadePad;
  final String? corHex;

  const MapaProduto({
    required this.produtoId,
    required this.nome,
    required this.unidadePad,
    this.corHex,
  });

  factory MapaProduto.fromMap(Map<String, dynamic> map) {
    return MapaProduto(
      produtoId: map['produto_id']?.toString() ?? '',
      nome: map['nome']?.toString() ?? '',
      unidadePad: map['unidade_pad']?.toString() ?? 'L',
      corHex: map['cor_hex']?.toString(),
    );
  }
}
