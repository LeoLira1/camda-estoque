import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/number_utils.dart';
import '../../data/repositories/principios_ativos_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/stat_card.dart';
import '../../shared/widgets/glass_card.dart';

class PrincipiosAtivosScreen extends StatefulWidget {
  const PrincipiosAtivosScreen({super.key});

  @override
  State<PrincipiosAtivosScreen> createState() => _PrincipiosAtivosScreenState();
}

class _PrincipiosAtivosScreenState extends State<PrincipiosAtivosScreen>
    with SingleTickerProviderStateMixin {
  final _repo = PrincipiosAtivosRepository();
  late TabController _tabController;

  List<GrupoPrincipioAtivo> _grupos = [];
  List<GrupoPrincipioAtivo> _filtrados = [];
  bool _loading = true;
  String? _error;
  final _searchCtrl = TextEditingController();
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _searchCtrl.addListener(_filtrar);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _repo.getAgrupados();
      if (!mounted) return;
      setState(() { _grupos = data; _filtrados = data; _loading = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _filtrar() {
    final q = _searchCtrl.text.trim();
    setState(() {
      _searchQuery = q.toLowerCase();
    });
    _aplicarFuzzy(q);
  }

  Future<void> _aplicarFuzzy(String query) async {
    if (query.isEmpty) {
      if (mounted) setState(() => _filtrados = _grupos);
      return;
    }
    // Usa o repositório com fuzzy real (bigrama Jaccard)
    try {
      final resultado = await _repo.buscar(query);
      if (!mounted) return;
      setState(() => _filtrados = resultado);
    } catch (_) {
      // fallback: contains simples se repo falhar
      final lower = query.toLowerCase();
      if (!mounted) return;
      setState(() {
        _filtrados = _grupos.where((g) =>
          g.principioAtivo.toLowerCase().contains(lower) ||
          g.produtos.any((p) => p.produto.toLowerCase().contains(lower))
        ).toList();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Princípios Ativos'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Lista'),
            Tab(text: 'Ranking'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando princípios ativos...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : Column(children: [
                  _buildKPIs(),
                  _buildSearch(),
                  Expanded(
                    child: TabBarView(
                      controller: _tabController,
                      children: [
                        _buildLista(),
                        _buildRanking(),
                      ],
                    ),
                  ),
                ]),
    );
  }

  Widget _buildKPIs() {
    final totalPA = _grupos.length;
    final totalProd = _grupos.fold(0, (s, g) => s + g.numProdutos);
    final totalQtd = _grupos.fold(0, (s, g) => s + g.totalQuantidade);
    final maisEstoque = _grupos.isNotEmpty ? _grupos.first : null;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: Column(children: [
        StatCardRow(cards: [
          StatCard(value: '$totalPA', label: 'P. Ativos', valueColor: AppColors.cyan),
          StatCard(value: '$totalProd', label: 'Produtos', valueColor: AppColors.blue),
          StatCard(value: CamdaNumberUtils.formatInt(totalQtd), label: 'Total Estoque', valueColor: AppColors.green),
        ]),
        if (maisEstoque != null) ...[
          const SizedBox(height: 8),
          GlassCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(children: [
              const Icon(Icons.emoji_events_outlined, color: AppColors.amber, size: 18),
              const SizedBox(width: 10),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Maior Volume', style: TextStyle(fontSize: 10, color: AppColors.textMuted, letterSpacing: 0.5)),
                Text(maisEstoque.principioAtivo,
                    style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                    maxLines: 1, overflow: TextOverflow.ellipsis),
              ])),
              Text(CamdaNumberUtils.formatInt(maisEstoque.totalQuantidade),
                  style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.amber)),
            ]),
          ),
        ],
      ]),
    ).animate().fadeIn(duration: 400.ms);
  }

  Widget _buildSearch() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: TextField(
        controller: _searchCtrl,
        style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
        decoration: InputDecoration(
          hintText: 'Buscar princípio ativo ou produto...',
          prefixIcon: const Icon(Icons.search, color: AppColors.textMuted, size: 18),
          isDense: true,
          suffixIcon: _searchQuery.isNotEmpty
              ? IconButton(icon: const Icon(Icons.clear, size: 16, color: AppColors.textMuted), onPressed: () => _searchCtrl.clear())
              : null,
        ),
      ),
    );
  }

  Widget _buildLista() {
    if (_filtrados.isEmpty) {
      return const lw.EmptyWidget(
        message: 'Nenhum princípio ativo encontrado.\nImporte dados via dashboard.',
        icon: Icons.science_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      itemCount: _filtrados.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) {
        final grupo = _filtrados[i];
        return _GrupoCard(grupo: grupo, rank: i + 1)
            .animate()
            .fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }

  Widget _buildRanking() {
    if (_grupos.isEmpty) {
      return const lw.EmptyWidget(message: 'Sem dados para ranking.', icon: Icons.bar_chart_outlined);
    }

    final top = _grupos.take(10).toList();
    final maxQtd = top.fold(1, (m, g) => g.totalQuantidade > m ? g.totalQuantidade : m);

    final colors = [
      AppColors.green, AppColors.cyan, AppColors.blue,
      AppColors.purple, AppColors.amber, AppColors.statusAvaria,
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(children: [
        GlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            const Row(children: [
              Icon(Icons.bar_chart_outlined, color: AppColors.green, size: 18),
              SizedBox(width: 8),
              Text('Top 10 por Volume de Estoque',
                  style: TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
            ]),
            const SizedBox(height: 16),
            SizedBox(
              height: 250,
              child: BarChart(
                BarChartData(
                  backgroundColor: Colors.transparent,
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    getDrawingHorizontalLine: (_) => FlLine(color: AppColors.surfaceBorder, strokeWidth: 1),
                  ),
                  borderData: FlBorderData(show: false),
                  titlesData: FlTitlesData(
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (v, _) {
                          final idx = v.toInt();
                          if (idx < 0 || idx >= top.length) return const SizedBox.shrink();
                          final pa = top[idx].principioAtivo;
                          return Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              pa.length > 8 ? '${pa.substring(0, 7)}.' : pa,
                              style: const TextStyle(fontSize: 8, color: AppColors.textMuted),
                            ),
                          );
                        },
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 40,
                        getTitlesWidget: (v, _) => Text(
                          CamdaNumberUtils.formatInt(v),
                          style: const TextStyle(fontSize: 8, color: AppColors.textMuted),
                        ),
                      ),
                    ),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  ),
                  barGroups: top.asMap().entries.map((e) {
                    final color = colors[e.key % colors.length];
                    return BarChartGroupData(
                      x: e.key,
                      barRods: [
                        BarChartRodData(
                          toY: e.value.totalQuantidade.toDouble(),
                          color: color,
                          width: 20,
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                        ),
                      ],
                    );
                  }).toList(),
                  maxY: maxQtd.toDouble() * 1.2,
                ),
              ),
            ),
          ]),
        ).animate().fadeIn(duration: 400.ms),
        const SizedBox(height: 12),
        // Tabela ranking
        ...top.asMap().entries.map((e) {
          final g = e.value;
          final color = colors[e.key % colors.length];
          final pct = maxQtd > 0 ? g.totalQuantidade / maxQtd : 0.0;
          return Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: color.withOpacity(0.2)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(children: [
                Container(
                  width: 28, height: 28,
                  decoration: BoxDecoration(color: color.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
                  child: Center(child: Text('${e.key + 1}', style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 12, fontWeight: FontWeight.w700, color: color))),
                ),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(g.principioAtivo, style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 4),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(3),
                    child: LinearProgressIndicator(value: pct, minHeight: 4, backgroundColor: AppColors.surfaceBorder, valueColor: AlwaysStoppedAnimation(color)),
                  ),
                  Text('${g.numProdutos} produto(s)', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                ])),
                const SizedBox(width: 10),
                Text(CamdaNumberUtils.formatInt(g.totalQuantidade), style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: color)),
              ]),
            ).animate().fadeIn(duration: 250.ms, delay: (e.key * 30).ms),
          );
        }),
      ]),
    );
  }
}

class _GrupoCard extends StatefulWidget {
  final GrupoPrincipioAtivo grupo;
  final int rank;

  const _GrupoCard({required this.grupo, required this.rank});

  @override
  State<_GrupoCard> createState() => _GrupoCardState();
}

class _GrupoCardState extends State<_GrupoCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final g = widget.grupo;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.cyan.withOpacity(0.15)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          GestureDetector(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(children: [
                Container(
                  width: 32, height: 32,
                  decoration: BoxDecoration(color: AppColors.cyan.withOpacity(0.12), borderRadius: BorderRadius.circular(8)),
                  child: Center(child: Text('${widget.rank}', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.cyan))),
                ),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(g.principioAtivo,
                      style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                      maxLines: 2, overflow: TextOverflow.ellipsis),
                  Text('${g.numProdutos} produto(s) · ${g.categoria}',
                      style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                ])),
                Text(CamdaNumberUtils.formatInt(g.totalQuantidade),
                    style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.green)),
                const SizedBox(width: 6),
                Icon(_expanded ? Icons.expand_less : Icons.expand_more, color: AppColors.textMuted, size: 18),
              ]),
            ),
          ),
          // Produtos expandidos
          if (_expanded) ...[
            const Divider(height: 1, color: AppColors.surfaceBorder),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 8, 14, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: g.produtos.map((p) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(children: [
                    const Icon(Icons.fiber_manual_record, color: AppColors.textDisabled, size: 8),
                    const SizedBox(width: 8),
                    Expanded(child: Text(p.produto, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary), maxLines: 2, overflow: TextOverflow.ellipsis)),
                  ]),
                )).toList(),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
