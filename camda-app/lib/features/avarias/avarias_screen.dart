import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/avaria.dart';
import '../../data/models/avaria_unidade.dart';
import '../../data/repositories/avarias_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class AvariasScreen extends StatefulWidget {
  const AvariasScreen({super.key});

  @override
  State<AvariasScreen> createState() => _AvariasScreenState();
}

class _AvariasScreenState extends State<AvariasScreen>
    with SingleTickerProviderStateMixin {
  final _repo = AvariasRepository();
  late TabController _tabController;

  List<Avaria> _todas = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _repo.getAll();
      if (!mounted) return;
      setState(() { _todas = data; _loading = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _resolver(Avaria avaria) async {
    try {
      await _repo.resolver(avaria.id);
      await _loadData();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Avaria marcada como resolvida')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  Future<void> _updateNivel(String uid, double nivel) async {
    // Atualiza estado local imediatamente (otimista)
    setState(() {
      _todas = _todas.map((a) => a.copyWith(
        unidades: a.unidades
            .map((u) => u.uid == uid ? u.copyWith(nivel: nivel) : u)
            .toList(),
      )).toList();
    });
    try {
      await _repo.updateNivel(uid, nivel);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro ao salvar nível: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  Future<void> _addUnidade(int avariaId) async {
    try {
      final nova = await _repo.addUnidade(avariaId);
      setState(() {
        _todas = _todas.map((a) => a.id == avariaId
            ? a.copyWith(unidades: [...a.unidades, nova])
            : a).toList();
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  Future<void> _removeUnidade(int avariaId, String uid) async {
    try {
      await _repo.removeUnidade(uid);
      setState(() {
        _todas = _todas.map((a) => a.id == avariaId
            ? a.copyWith(unidades: a.unidades.where((u) => u.uid != uid).toList())
            : a).toList();
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final abertas = _todas.where((a) => a.isAberta).toList();
    final resolvidas = _todas.where((a) => !a.isAberta).toList();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Avarias'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Abertas (${_loading ? '...' : abertas.length})'),
            Tab(text: 'Resolvidas (${_loading ? '...' : resolvidas.length})'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
          labelPadding: const EdgeInsets.symmetric(horizontal: 12),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showRegistrarDialog,
        backgroundColor: AppColors.red,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando avarias...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildList(abertas, showResolve: true),
                    _buildList(resolvidas, showResolve: false),
                  ],
                ),
    );
  }

  Widget _buildList(List<Avaria> items, {required bool showResolve}) {
    if (items.isEmpty) {
      return lw.EmptyWidget(
        message: showResolve
            ? 'Nenhuma avaria aberta.\nBom sinal!'
            : 'Nenhuma avaria resolvida ainda.',
        icon: Icons.check_circle_outline,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, i) {
        final avaria = items[i];
        return _AvariaCard(
          avaria: avaria,
          showResolve: showResolve,
          onResolve: () => _resolver(avaria),
          onNivelChanged: _updateNivel,
          onAddUnidade: () => _addUnidade(avaria.id),
          onRemoveUnidade: (uid) => _removeUnidade(avaria.id, uid),
        ).animate().fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }

  void _showRegistrarDialog() {
    final codigoCtrl = TextEditingController();
    final produtoCtrl = TextEditingController();
    final motivoCtrl = TextEditingController();
    final capCtrl = TextEditingController(text: '20');
    int qtd = 1;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setDialogState) {
        return AlertDialog(
          title: const Text('Registrar Avaria'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: codigoCtrl,
                  decoration: const InputDecoration(labelText: 'Código do produto'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: produtoCtrl,
                  decoration: const InputDecoration(labelText: 'Nome do produto'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: capCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Capacidade do galão (litros)',
                    hintText: 'ex: 20',
                  ),
                ),
                const SizedBox(height: 8),
                Row(children: [
                  const Text('Quantidade:', style: TextStyle(color: AppColors.textSecondary)),
                  const Spacer(),
                  IconButton(
                    onPressed: () => setDialogState(() => qtd = (qtd - 1).clamp(1, 9999)),
                    icon: const Icon(Icons.remove, size: 18),
                  ),
                  Text('$qtd', style: const TextStyle(
                    fontFamily: 'JetBrainsMono', fontSize: 18,
                    fontWeight: FontWeight.w700, color: AppColors.red,
                  )),
                  IconButton(
                    onPressed: () => setDialogState(() => qtd++),
                    icon: const Icon(Icons.add, size: 18),
                  ),
                ]),
                const SizedBox(height: 8),
                TextField(
                  controller: motivoCtrl,
                  maxLines: 2,
                  decoration: const InputDecoration(labelText: 'Motivo da avaria'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
            ElevatedButton(
              onPressed: () async {
                if (codigoCtrl.text.isEmpty || produtoCtrl.text.isEmpty) return;
                Navigator.pop(ctx);
                final cap = double.tryParse(capCtrl.text.trim()) ?? 20.0;
                try {
                  await _repo.registrar(
                    codigo: codigoCtrl.text.trim(),
                    produto: produtoCtrl.text.trim(),
                    qtd: qtd,
                    motivo: motivoCtrl.text.trim(),
                    capacidadeLitros: cap,
                  );
                  await _loadData();
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
                  );
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.red, foregroundColor: Colors.white,
              ),
              child: const Text('Registrar'),
            ),
          ],
        );
      }),
    );
  }
}

// ── Avaria Card ───────────────────────────────────────────────────────────────

class _AvariaCard extends StatelessWidget {
  final Avaria avaria;
  final bool showResolve;
  final VoidCallback onResolve;
  final void Function(String uid, double nivel) onNivelChanged;
  final VoidCallback onAddUnidade;
  final void Function(String uid) onRemoveUnidade;

  const _AvariaCard({
    required this.avaria,
    required this.showResolve,
    required this.onResolve,
    required this.onNivelChanged,
    required this.onAddUnidade,
    required this.onRemoveUnidade,
  });

  Color _accentColor() {
    final pior = avaria.nivelMinimo;
    if (pior > 60) return const Color(0xFF22c55e);
    if (pior > 25) return const Color(0xFFf59e0b);
    return const Color(0xFFef4444);
  }

  @override
  Widget build(BuildContext context) {
    final accent = _accentColor();
    final dt = CamdaDateUtils.parseFlexible(avaria.registradoEm);
    final dataStr = dt != null ? CamdaDateUtils.formatDate(dt) : avaria.registradoEm;
    final qtd = avaria.unidades.length;

    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF0d1a18), Color(0xFF111e1c)],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accent.withOpacity(0.22)),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 16)],
      ),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────────────────
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFef4444).withOpacity(0.1),
                          border: Border.all(color: const Color(0xFFef4444).withOpacity(0.5)),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: const Text('⚠ ABERTA', style: TextStyle(
                          color: Color(0xFFf87171), fontSize: 10,
                          fontWeight: FontWeight.w800, letterSpacing: 2,
                        )),
                      ),
                      const SizedBox(width: 8),
                      Text(dataStr, style: TextStyle(
                        color: Colors.white.withOpacity(0.3), fontSize: 10,
                      )),
                    ]),
                    const SizedBox(height: 6),
                    Text(avaria.produto, style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w800, fontSize: 14,
                    )),
                    const SizedBox(height: 2),
                    Text(
                      'Cod: ${avaria.codigo}  ·  $qtd ${qtd == 1 ? "unidade" : "unidades"} danificadas',
                      style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 11),
                    ),
                    if (avaria.motivo.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text('🪣 ${avaria.motivo}',
                        style: TextStyle(color: Colors.white.withOpacity(0.35), fontSize: 11)),
                    ],
                  ],
                ),
              ),
              if (showResolve) ...[
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: onResolve,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFF22c55e).withOpacity(0.1),
                      border: Border.all(color: const Color(0xFF22c55e).withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text('✓ Resolver', style: TextStyle(
                      color: Color(0xFF4ade80), fontSize: 11, fontWeight: FontWeight.w700,
                    )),
                  ),
                ),
              ],
            ],
          ),

          const SizedBox(height: 14),

          // ── Galões ──────────────────────────────────────────────
          Container(
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.03),
              borderRadius: BorderRadius.circular(12),
            ),
            padding: const EdgeInsets.fromLTRB(10, 14, 10, 10),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ...avaria.unidades.asMap().entries.map((e) => Padding(
                    padding: const EdgeInsets.only(right: 10),
                    child: _GalaoWidget(
                      key: ValueKey(e.value.uid),
                      unidade: e.value,
                      capacidade: avaria.capacidadeLitros,
                      index: e.key,
                      canRemove: avaria.unidades.length > 1,
                      onNivelChanged: (nivel) => onNivelChanged(e.value.uid, nivel),
                      onRemove: () => onRemoveUnidade(e.value.uid),
                    ),
                  )),
                  _AddGalaoButton(onTap: onAddUnidade),
                ],
              ),
            ),
          ),

          const SizedBox(height: 10),

          // ── Totais ──────────────────────────────────────────────
          if (avaria.unidades.isNotEmpty)
            Row(children: [
              _StatChip(
                label: 'RESTANTE',
                value: '${avaria.totalRestanteLitros.toStringAsFixed(1)} L',
                color: accent,
              ),
              const SizedBox(width: 6),
              _StatChip(
                label: 'PERDIDO',
                value: '${avaria.totalPerdidoLitros.toStringAsFixed(1)} L',
                color: const Color(0xFFf87171),
              ),
              const SizedBox(width: 6),
              _StatChip(
                label: 'BALDES',
                value: '$qtd',
                color: const Color(0xFF60a5fa),
              ),
            ]),
        ],
      ),
    );
  }
}

// ── Galão Widget ──────────────────────────────────────────────────────────────

class _GalaoWidget extends StatefulWidget {
  const _GalaoWidget({
    super.key,
    required this.unidade,
    required this.capacidade,
    required this.index,
    required this.canRemove,
    required this.onNivelChanged,
    required this.onRemove,
  });

  final AvariaUnidade unidade;
  final double capacidade;
  final int index;
  final bool canRemove;
  final ValueChanged<double> onNivelChanged;
  final VoidCallback onRemove;

  @override
  State<_GalaoWidget> createState() => _GalaoWidgetState();
}

class _GalaoWidgetState extends State<_GalaoWidget> with TickerProviderStateMixin {
  late AnimationController _levelCtrl;
  late AnimationController _waveCtrl;
  double _animFrom = 50.0;
  double _animTo = 50.0;
  double _sliderVal = 50.0;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _sliderVal = widget.unidade.nivel;
    _animFrom = _sliderVal;
    _animTo = _sliderVal;
    _levelCtrl = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 700),
    );
    _waveCtrl = AnimationController(
      vsync: this, duration: const Duration(seconds: 3),
    )..repeat();
  }

  @override
  void didUpdateWidget(_GalaoWidget old) {
    super.didUpdateWidget(old);
    // Só anima se foi uma atualização externa (não do slider local)
    if (old.unidade.nivel != widget.unidade.nivel &&
        (widget.unidade.nivel - _animTo).abs() > 0.5) {
      _animFrom = _currentLevel;
      _animTo = widget.unidade.nivel;
      setState(() => _sliderVal = widget.unidade.nivel);
      _levelCtrl.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _levelCtrl.dispose();
    _waveCtrl.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  double get _currentLevel {
    final t = Curves.easeOutCubic.transform(_levelCtrl.value.clamp(0.0, 1.0));
    return _animFrom + (_animTo - _animFrom) * t;
  }

  void _onSlider(double v) {
    setState(() => _sliderVal = v);
    _animFrom = _currentLevel;
    _animTo = v;
    _levelCtrl.forward(from: 0);
    // Debounce: só salva no Turso após parar de arrastar
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 600), () {
      widget.onNivelChanged(v);
    });
  }

  static Color _cor(double pct) {
    if (pct > 60) return const Color(0xFF22c55e);
    if (pct > 25) return const Color(0xFFf59e0b);
    return const Color(0xFFef4444);
  }

  @override
  Widget build(BuildContext context) {
    final pct = _sliderVal;
    final litros = (pct / 100.0) * widget.capacidade;
    final cor = _cor(pct);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Rótulo do número
        Text(
          'Nº ${widget.index + 1}',
          style: TextStyle(
            fontSize: 10, fontWeight: FontWeight.w700,
            letterSpacing: 1.5, color: cor.withOpacity(0.8),
          ),
        ),
        const SizedBox(height: 4),

        // Visual do galão
        Stack(
          clipBehavior: Clip.none,
          children: [
            AnimatedBuilder(
              animation: Listenable.merge([_levelCtrl, _waveCtrl]),
              builder: (_, __) => SizedBox(
                width: 120,
                height: 155,
                child: CustomPaint(
                  painter: _GalaoPainter(
                    nivel: _currentLevel,
                    wavePhase: _waveCtrl.value * 2 * math.pi,
                    color: cor,
                  ),
                  child: Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // ─── LITROS RESTANTES – FONTE GRANDE ───
                        Text(
                          '${litros.toStringAsFixed(1)}L',
                          style: const TextStyle(
                            fontSize: 34,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                            height: 1.0,
                            shadows: [
                              Shadow(blurRadius: 10, color: Colors.black87),
                              Shadow(blurRadius: 4, color: Colors.black54),
                            ],
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${pct.round()}%',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: cor.withOpacity(0.9),
                            shadows: const [
                              Shadow(blurRadius: 6, color: Colors.black87),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            if (widget.canRemove)
              Positioned(
                top: -6,
                right: -6,
                child: GestureDetector(
                  onTap: widget.onRemove,
                  child: Container(
                    width: 20, height: 20,
                    decoration: BoxDecoration(
                      color: const Color(0xFF1a0808),
                      border: Border.all(color: const Color(0xFFef4444).withOpacity(0.6)),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.close, size: 12, color: Color(0xFFf87171)),
                  ),
                ),
              ),
          ],
        ),

        // Slider de nível
        SizedBox(
          width: 120,
          child: Column(children: [
            SliderTheme(
              data: SliderThemeData(
                trackHeight: 3,
                thumbRadius: 7,
                overlayRadius: 14,
                activeTrackColor: cor,
                inactiveTrackColor: cor.withOpacity(0.2),
                thumbColor: cor,
                overlayColor: cor.withOpacity(0.15),
              ),
              child: Slider(
                value: pct,
                min: 0,
                max: 100,
                onChanged: _onSlider,
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('0', style: TextStyle(
                    color: Colors.white.withOpacity(0.2), fontSize: 9,
                  )),
                  Text('${widget.capacidade.toStringAsFixed(0)}L', style: TextStyle(
                    color: Colors.white.withOpacity(0.2), fontSize: 9,
                  )),
                ],
              ),
            ),
          ]),
        ),

        const SizedBox(height: 4),

        // Badge de status
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
          decoration: BoxDecoration(
            color: cor.withOpacity(0.1),
            border: Border.all(color: cor.withOpacity(0.3)),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            pct > 60 ? '✓ OK' : pct > 25 ? '⚠ Baixo' : '🔴 Crítico',
            style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: cor),
          ),
        ),
      ],
    );
  }
}

// ── Galão Painter ─────────────────────────────────────────────────────────────

class _GalaoPainter extends CustomPainter {
  final double nivel;
  final double wavePhase;
  final Color color;

  const _GalaoPainter({
    required this.nivel,
    required this.wavePhase,
    required this.color,
  });

  static const _bodyL = 6.0;
  static const _bodyT = 32.0;
  static const _bodyRadius = Radius.circular(10);

  @override
  void paint(Canvas canvas, Size size) {
    final bodyR = size.width - _bodyL;
    final bodyB = size.height - 6;
    final bodyRRect = RRect.fromLTRBR(_bodyL, _bodyT, bodyR, bodyB, _bodyRadius);

    // ── Fundo do corpo ─────────────────────────────────────────
    canvas.drawRRect(
      bodyRRect,
      Paint()..color = const Color(0xFF7ab0a8).withOpacity(0.12),
    );

    // ── Líquido com onda ──────────────────────────────────────
    canvas.save();
    canvas.clipRRect(bodyRRect);

    if (nivel > 0.1) {
      final pct = nivel / 100.0;
      final bodyH = bodyB - _bodyT;
      final liqTop = bodyB - pct * bodyH;
      const waveAmp = 3.5;

      final wave = Path()..moveTo(_bodyL, liqTop + waveAmp);
      const steps = 50;
      final segW = (bodyR - _bodyL) / steps;
      for (int i = 0; i <= steps; i++) {
        final x = _bodyL + i * segW;
        final y = liqTop + waveAmp * math.sin(wavePhase + i * math.pi * 4.0 / steps);
        wave.lineTo(x, y);
      }
      wave.lineTo(bodyR, bodyB);
      wave.lineTo(_bodyL, bodyB);
      wave.close();

      // Gradiente do líquido
      canvas.drawPath(
        wave,
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [color.withOpacity(0.9), color.withOpacity(0.7)],
          ).createShader(Rect.fromLTWH(
            _bodyL, liqTop - waveAmp, bodyR - _bodyL, bodyB - liqTop + waveAmp,
          )),
      );

      // Brilho central (horizontal)
      canvas.drawRect(
        Rect.fromLTWH(_bodyL, liqTop, bodyR - _bodyL, bodyB - liqTop),
        Paint()
          ..shader = LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [
              Colors.white.withOpacity(0),
              Colors.white.withOpacity(0.18),
              Colors.white.withOpacity(0),
            ],
            stops: const [0.0, 0.5, 1.0],
          ).createShader(Rect.fromLTWH(_bodyL, liqTop, bodyR - _bodyL, 1)),
      );

      // Reflexo vertical esquerdo
      if (bodyB - liqTop > 12) {
        canvas.drawRRect(
          RRect.fromLTRBR(
            _bodyL + 8, liqTop + 5, _bodyL + 14, bodyB - 10,
            const Radius.circular(4),
          ),
          Paint()
            ..color = Colors.white.withOpacity(0.2)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2),
        );
      }
    }

    canvas.restore();

    // ── Linhas de escala ───────────────────────────────────────
    final markPaint = Paint()
      ..color = Colors.white.withOpacity(0.12)
      ..strokeWidth = 0.8;
    final bodyH = bodyB - _bodyT;
    for (int i = 1; i < 5; i++) {
      final y = bodyB - (i / 5.0) * bodyH;
      canvas.drawLine(Offset(_bodyL + 5, y), Offset(bodyR - 5, y), markPaint);
    }

    // ── Contorno glassmorphism ────────────────────────────────
    canvas.drawRRect(
      bodyRRect,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.white.withOpacity(0.3),
            Colors.white.withOpacity(0.06),
          ],
        ).createShader(Rect.fromLTWH(_bodyL, _bodyT, bodyR - _bodyL, bodyB - _bodyT))
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.5,
    );

    // ── Gargalo (pescoço) ─────────────────────────────────────
    final neckL = size.width * 0.28;
    final neckR = size.width * 0.72;
    canvas.drawRRect(
      RRect.fromLTRBR(neckL, _bodyT - 18, neckR, _bodyT, const Radius.circular(5)),
      Paint()..color = const Color(0xFF8090A0),
    );

    // Tampa
    canvas.drawRRect(
      RRect.fromLTRBR(neckL - 2, _bodyT - 24, neckR + 2, _bodyT - 16, const Radius.circular(3)),
      Paint()..color = const Color(0xFF607080),
    );

    // ── Alça (arco no topo) ───────────────────────────────────
    final handlePath = Path()
      ..moveTo(size.width * 0.18, _bodyT - 2)
      ..quadraticBezierTo(size.width * 0.5, -10, size.width * 0.82, _bodyT - 2);

    canvas.drawPath(
      handlePath,
      Paint()
        ..color = const Color(0xFF7888A0)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 9
        ..strokeCap = StrokeCap.round,
    );
    canvas.drawPath(
      handlePath,
      Paint()
        ..color = const Color(0xFFc0d0d8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 5
        ..strokeCap = StrokeCap.round,
    );
    canvas.drawPath(
      handlePath,
      Paint()
        ..color = const Color(0xFFeef4f8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_GalaoPainter old) =>
      old.nivel != nivel || old.wavePhase != wavePhase || old.color != color;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

class _AddGalaoButton extends StatelessWidget {
  final VoidCallback onTap;
  const _AddGalaoButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 120,
        height: 210,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.03),
          border: Border.all(color: Colors.white.withOpacity(0.12), width: 1.5),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add, size: 28, color: Colors.white.withOpacity(0.3)),
            const SizedBox(height: 4),
            Text(
              'ADD BALDE',
              style: TextStyle(
                fontSize: 9, letterSpacing: 1.5,
                color: Colors.white.withOpacity(0.3),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.04),
          borderRadius: BorderRadius.circular(8),
          border: Border(left: BorderSide(color: color.withOpacity(0.5), width: 3)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(
              color: Colors.white.withOpacity(0.35), fontSize: 9, letterSpacing: 1.5,
            )),
            const SizedBox(height: 2),
            Text(value, style: TextStyle(
              color: color, fontSize: 15, fontWeight: FontWeight.w900,
            )),
          ],
        ),
      ),
    );
  }
}
