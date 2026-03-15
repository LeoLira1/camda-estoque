import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/validade_lote.dart';
import '../../data/repositories/validade_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/stat_card.dart';

class ValidadeScreen extends StatefulWidget {
  const ValidadeScreen({super.key});

  @override
  State<ValidadeScreen> createState() => _ValidadeScreenState();
}

class _ValidadeScreenState extends State<ValidadeScreen>
    with SingleTickerProviderStateMixin {
  final _repo = ValidadeRepository();
  late TabController _tabController;

  List<ValidadeLote> _todos = [];
  List<String> _grupos = [];
  String _grupoFiltro = 'Todos';
  int? _diasFiltro; // null = todos, senão <= N dias
  ValidadeResumo? _resumo;
  bool _loading = true;
  String? _error;

  static const _diasOptions = [7, 30, 60, 90];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
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
      final results = await Future.wait([
        _repo.getAll(),
        _repo.getGrupos(),
        _repo.getResumo(),
      ]);
      if (!mounted) return;
      setState(() {
        _todos = results[0] as List<ValidadeLote>;
        _grupos = ['Todos', ...(results[1] as List<String>)];
        _resumo = results[2] as ValidadeResumo;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<ValidadeLote> get _filteredAll {
    return _todos.where((l) {
      final matchGrupo = _grupoFiltro == 'Todos' || l.grupo == _grupoFiltro;
      final matchDias = _diasFiltro == null ||
          (!l.isVencido && l.diasParaVencer <= _diasFiltro!);
      return matchGrupo && matchDias;
    }).toList();
  }

  List<ValidadeLote> get _vencidos => _filteredAll.where((l) => l.isVencido).toList();
  List<ValidadeLote> get _alertas => _filteredAll.where((l) => l.isCritico || l.isAlerta).toList();
  List<ValidadeLote> get _ok => _filteredAll.where((l) => l.isOk).toList();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Validade de Lotes'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Alertas'),
            Tab(text: 'Vencidos'),
            Tab(text: 'OK'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando validade...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : Column(
                  children: [
                    if (_resumo != null) _buildResumoBar(),
                    _buildGrupoFilter(),
                    _buildDiasFilter(),
                    Expanded(
                      child: TabBarView(
                        controller: _tabController,
                        children: [
                          _buildList(_alertas),
                          _buildList(_vencidos),
                          _buildList(_ok),
                        ],
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _buildResumoBar() {
    final r = _resumo!;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: StatCardRow(cards: [
        StatCard(
          value: r.vencidos.toString(),
          label: 'Vencidos',
          valueColor: AppColors.red,
        ),
        StatCard(
          value: r.criticos.toString(),
          label: 'Críticos',
          valueColor: AppColors.statusAvaria,
        ),
        StatCard(
          value: r.alertas.toString(),
          label: 'Alertas',
          valueColor: AppColors.amber,
        ),
        StatCard(
          value: (r.total - r.vencidos - r.criticos - r.alertas).toString(),
          label: 'OK',
          valueColor: AppColors.green,
        ),
      ]),
    );
  }

  Widget _buildGrupoFilter() {
    if (_grupos.length <= 1) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: SizedBox(
        height: 32,
        child: ListView(
          scrollDirection: Axis.horizontal,
          children: _grupos
              .map((g) => Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: ChoiceChip(
                      label: Text(g, style: const TextStyle(fontSize: 11)),
                      selected: _grupoFiltro == g,
                      selectedColor: AppColors.blue,
                      onSelected: (_) => setState(() => _grupoFiltro = g),
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                    ),
                  ))
              .toList(),
        ),
      ),
    );
  }

  Widget _buildDiasFilter() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
      child: SizedBox(
        height: 32,
        child: ListView(
          scrollDirection: Axis.horizontal,
          children: [
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: ChoiceChip(
                label: const Text('Todos', style: TextStyle(fontSize: 11)),
                selected: _diasFiltro == null,
                selectedColor: AppColors.blue,
                onSelected: (_) => setState(() => _diasFiltro = null),
                padding: const EdgeInsets.symmetric(horizontal: 8),
              ),
            ),
            ..._diasOptions.map((d) => Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    label: Text('$d dias', style: const TextStyle(fontSize: 11)),
                    selected: _diasFiltro == d,
                    selectedColor: AppColors.amber,
                    onSelected: (_) => setState(() => _diasFiltro = _diasFiltro == d ? null : d),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildList(List<ValidadeLote> items) {
    if (items.isEmpty) {
      return const lw.EmptyWidget(
        message: 'Nenhum lote neste filtro.',
        icon: Icons.event_available_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) => _LoteTile(lote: items[i])
          .animate()
          .fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms),
    );
  }
}

class _LoteTile extends StatelessWidget {
  final ValidadeLote lote;

  const _LoteTile({required this.lote});

  @override
  Widget build(BuildContext context) {
    Color statusColor;
    String statusText;
    if (lote.isVencido) {
      statusColor = AppColors.red;
      statusText = 'VENCIDO';
    } else if (lote.isCritico) {
      statusColor = AppColors.statusAvaria;
      statusText = '${lote.diasParaVencer}d';
    } else if (lote.isAlerta) {
      statusColor = AppColors.amber;
      statusText = '${lote.diasParaVencer}d';
    } else {
      statusColor = AppColors.green;
      statusText = '${lote.diasParaVencer}d';
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: statusColor.withOpacity(0.25)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Center(
              child: Text(
                statusText,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: lote.isVencido ? 9 : 13,
                  fontWeight: FontWeight.w700,
                  color: statusColor,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  lote.produto,
                  style: const TextStyle(
                    fontFamily: 'Outfit',
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Row(children: [
                  Text('Lote: ${lote.lote}',
                      style: const TextStyle(fontSize: 10, color: AppColors.textMuted, fontFamily: 'JetBrainsMono')),
                  if (lote.filial.isNotEmpty) ...[
                    const Text(' · ', style: TextStyle(fontSize: 10, color: AppColors.textDisabled)),
                    Text(lote.filial, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                  ],
                ]),
                Text(
                  'Vence: ${lote.vencimento}',
                  style: TextStyle(fontSize: 10, color: statusColor.withOpacity(0.8)),
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                CamdaNumberUtils.formatInt(lote.quantidade),
                style: const TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              if (lote.valor > 0)
                Text(
                  CamdaNumberUtils.formatCurrency(lote.valor),
                  style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
