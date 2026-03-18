import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/contagem_item.dart';
import '../../data/repositories/contagem_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/glass_card.dart';

class ContagemScreen extends StatefulWidget {
  const ContagemScreen({super.key});

  @override
  State<ContagemScreen> createState() => _ContagemScreenState();
}

class _ContagemScreenState extends State<ContagemScreen>
    with SingleTickerProviderStateMixin {
  final _repo = ContagemRepository();
  late TabController _tabController;

  List<ContagemItem> _todos = [];
  ContagemResumo? _resumo;
  String _filtroStatus = 'pendente';
  String _searchQuery = '';
  final _searchCtrl = TextEditingController();
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() => _filtroStatus = _statusDaAba(_tabController.index));
      }
    });
    _searchCtrl.addListener(() => setState(() => _searchQuery = _searchCtrl.text));
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  String _statusDaAba(int index) {
    switch (index) {
      case 0: return 'pendente';
      case 1: return 'ok';
      case 2: return 'divergente';
      default: return 'pendente';
    }
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final results = await Future.wait([_repo.getAll(), _repo.getResumo()]);
      if (!mounted) return;
      setState(() {
        _todos = results[0] as List<ContagemItem>;
        _resumo = results[1] as ContagemResumo;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<ContagemItem> get _filtrados {
    var lista = _todos.where((i) => i.status == _filtroStatus).toList();
    if (_searchQuery.trim().isNotEmpty) {
      final q = _searchQuery.toLowerCase();
      lista = lista.where((i) =>
        i.produto.toLowerCase().contains(q) ||
        i.codigo.toLowerCase().contains(q) ||
        i.categoria.toLowerCase().contains(q)
      ).toList();
    }
    return lista;
  }

  Future<void> _marcarOk(ContagemItem item) async {
    try {
      await _repo.marcarOk(item.id);
      await _loadData();
    } catch (e) {
      _snackError('$e');
    }
  }

  Future<void> _marcarDivergente(ContagemItem item) async {
    int qtdDiv = item.qtdDivergencia;
    final motivoCtrl = TextEditingController(text: item.motivo);

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setD) {
        return AlertDialog(
          title: Text('Divergência — ${item.produto}', maxLines: 2, overflow: TextOverflow.ellipsis),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Row(children: [
              const Text('Diferença:', style: TextStyle(color: AppColors.textSecondary)),
              const Spacer(),
              IconButton(onPressed: () => setD(() => qtdDiv = (qtdDiv - 1).clamp(-999999, 999999)), icon: const Icon(Icons.remove, size: 18)),
              Text('$qtdDiv', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.amber)),
              IconButton(onPressed: () => setD(() => qtdDiv++), icon: const Icon(Icons.add, size: 18)),
            ]),
            const SizedBox(height: 8),
            TextField(
              controller: motivoCtrl,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Motivo / Observação', isDense: true),
            ),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(ctx);
                try {
                  await _repo.marcarDivergente(item.id, qtdDiv, motivoCtrl.text.trim());
                  await _loadData();
                } catch (e) { _snackError('$e'); }
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.amber, foregroundColor: AppColors.background),
              child: const Text('Salvar'),
            ),
          ],
        );
      }),
    );
  }

  Future<void> _resetar(ContagemItem item) async {
    try {
      await _repo.resetar(item.id);
      await _loadData();
    } catch (e) {
      _snackError('$e');
    }
  }

  void _snackError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: AppColors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            if (_loading)
              const Expanded(child: lw.LoadingWidget(message: 'Carregando contagem...'))
            else if (_error != null)
              Expanded(child: lw.ErrorWidget(message: _error!, onRetry: _loadData))
            else
              Expanded(
                child: Column(
                  children: [
                    if (_resumo != null)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(12, 0, 12, 4),
                        child: _buildProgressBar(_resumo!),
                      ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      child: _buildSearch(),
                    ),
                    _buildTabBar(),
                    Expanded(
                      child: TabBarView(
                        controller: _tabController,
                        children: [
                          _buildList(showOkBtn: true, showDivBtn: true, showResetBtn: false),
                          _buildList(showOkBtn: false, showDivBtn: false, showResetBtn: true),
                          _buildList(showOkBtn: false, showDivBtn: true, showResetBtn: true),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final now = CamdaDateUtils.nowBRT();
    final hora = CamdaDateUtils.formatTime(now);
    final diaNome = CamdaDateUtils.diaSemanaFull(now);
    final data = CamdaDateUtils.formatDate(now);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ShaderMask(
                shaderCallback: (bounds) =>
                    AppColors.greenGradient.createShader(bounds),
                child: const Text(
                  'Contagem Física',
                  style: TextStyle(
                    fontFamily: 'Outfit',
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ),
              const Spacer(),
              IconButton(
                onPressed: _loadData,
                icon: const Icon(Icons.refresh, color: AppColors.textMuted, size: 20),
                tooltip: 'Atualizar',
              ),
            ],
          ),
          Text(
            '$diaNome · $data · $hora',
            style: const TextStyle(
              fontFamily: 'JetBrainsMono',
              fontSize: 11,
              color: AppColors.textDisabled,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1, end: 0);
  }

  Widget _buildProgressBar(ContagemResumo r) {
    final pct = r.pctConcluido;
    return GlassCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('Progresso da contagem', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
          Text('${(pct * 100).toStringAsFixed(0)}%', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.green)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: pct,
            minHeight: 6,
            backgroundColor: AppColors.surfaceBorder,
            valueColor: const AlwaysStoppedAnimation(AppColors.green),
          ),
        ),
        const SizedBox(height: 8),
        Row(children: [
          _statPill('${r.ok}', 'OK', AppColors.green),
          const SizedBox(width: 8),
          _statPill('${r.divergentes}', 'Divergentes', AppColors.amber),
          const SizedBox(width: 8),
          _statPill('${r.pendentes}', 'Pendentes', AppColors.textMuted),
          const Spacer(),
          Text('${r.total} itens', style: const TextStyle(fontSize: 10, color: AppColors.textDisabled)),
        ]),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 100.ms);
  }

  Widget _statPill(String value, String label, Color color) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 6, height: 6, decoration: BoxDecoration(shape: BoxShape.circle, color: color)),
      const SizedBox(width: 4),
      Text('$value $label', style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.w600)),
    ]);
  }

  Widget _buildSearch() {
    return TextField(
      controller: _searchCtrl,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        hintText: 'Buscar produto, código ou categoria...',
        prefixIcon: const Icon(Icons.search, color: AppColors.textMuted, size: 18),
        isDense: true,
        suffixIcon: _searchQuery.isNotEmpty
            ? IconButton(icon: const Icon(Icons.clear, size: 16, color: AppColors.textMuted), onPressed: () => _searchCtrl.clear())
            : null,
      ),
    );
  }

  Widget _buildTabBar() {
    final pendentes = _todos.where((i) => i.isPendente).length;
    final ok = _todos.where((i) => i.isOk).length;
    final divergentes = _todos.where((i) => i.isDivergente).length;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          color: AppColors.green.withOpacity(0.15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.green.withOpacity(0.4)),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: Colors.transparent,
        labelColor: AppColors.green,
        unselectedLabelColor: AppColors.textMuted,
        labelStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 11, fontWeight: FontWeight.w700),
        unselectedLabelStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 11, fontWeight: FontWeight.w500),
        padding: const EdgeInsets.all(4),
        tabs: [
          Tab(text: 'Pendentes ($pendentes)'),
          Tab(text: 'OK ($ok)'),
          Tab(text: 'Div. ($divergentes)'),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms, delay: 150.ms);
  }

  Widget _buildList({
    required bool showOkBtn,
    required bool showDivBtn,
    required bool showResetBtn,
  }) {
    final items = _filtrados;
    if (items.isEmpty) {
      return lw.EmptyWidget(
        message: _filtroStatus == 'pendente'
            ? 'Nenhum item pendente!'
            : _filtroStatus == 'ok'
                ? 'Nenhum item marcado como OK ainda.'
                : 'Nenhuma divergência registrada.',
        icon: _filtroStatus == 'ok' ? Icons.check_circle_outline : Icons.inventory_2_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 24),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) {
        final item = items[i];
        return _ContagemTile(
          item: item,
          showOkBtn: showOkBtn,
          showDivBtn: showDivBtn,
          showResetBtn: showResetBtn,
          onOk: () => _marcarOk(item),
          onDiv: () => _marcarDivergente(item),
          onReset: () => _resetar(item),
        ).animate().fadeIn(duration: 200.ms, delay: (i * 15).clamp(0, 300).ms);
      },
    );
  }
}

class _ContagemTile extends StatelessWidget {
  final ContagemItem item;
  final bool showOkBtn;
  final bool showDivBtn;
  final bool showResetBtn;
  final VoidCallback onOk;
  final VoidCallback onDiv;
  final VoidCallback onReset;

  const _ContagemTile({
    required this.item,
    required this.showOkBtn,
    required this.showDivBtn,
    required this.showResetBtn,
    required this.onOk,
    required this.onDiv,
    required this.onReset,
  });

  @override
  Widget build(BuildContext context) {
    Color borderColor;
    switch (item.status) {
      case 'ok': borderColor = AppColors.green; break;
      case 'divergente': borderColor = AppColors.amber; break;
      default: borderColor = AppColors.surfaceBorder;
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: borderColor.withOpacity(item.isPendente ? 0.3 : 0.5)),
      ),
      padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text(item.produto,
                  style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                  maxLines: 2, overflow: TextOverflow.ellipsis),
            ),
            Text(CamdaNumberUtils.formatInt(item.qtdEstoque),
                style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
          ]),
          const SizedBox(height: 2),
          Row(children: [
            Text(item.categoria, style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
            if (item.codigo.isNotEmpty) ...[
              const Text(' · ', style: TextStyle(fontSize: 10, color: AppColors.textDisabled)),
              Text(item.codigo, style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, color: AppColors.textDisabled)),
            ],
          ]),
          if (item.isDivergente && item.qtdDivergencia != 0) ...[
            const SizedBox(height: 4),
            Text(
              'Divergência: ${CamdaNumberUtils.formatDiff(item.qtdDivergencia)}',
              style: const TextStyle(fontSize: 12, color: AppColors.amber, fontWeight: FontWeight.w600),
            ),
          ],
          if (item.motivo.isNotEmpty)
            Text(item.motivo, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary, fontStyle: FontStyle.italic)),
          if (showOkBtn || showDivBtn || showResetBtn) ...[
            const SizedBox(height: 8),
            Row(children: [
              if (showOkBtn)
                _ActionBtn(label: '✓ OK', color: AppColors.green, onTap: onOk),
              if (showOkBtn) const SizedBox(width: 6),
              if (showDivBtn)
                _ActionBtn(label: '≠ Divergência', color: AppColors.amber, onTap: onDiv),
              if (showResetBtn) ...[
                const Spacer(),
                _ActionBtn(label: '↺ Resetar', color: AppColors.textMuted, onTap: onReset),
              ],
            ]),
          ],
        ],
      ),
    );
  }
}

class _ActionBtn extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ActionBtn({required this.label, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
      ),
    );
  }
}
