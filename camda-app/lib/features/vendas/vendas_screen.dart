import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:fl_chart/fl_chart.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/venda.dart';
import '../../data/repositories/vendas_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/glass_card.dart';

class VendasScreen extends StatefulWidget {
  const VendasScreen({super.key});

  @override
  State<VendasScreen> createState() => _VendasScreenState();
}

class _VendasScreenState extends State<VendasScreen>
    with SingleTickerProviderStateMixin {
  final _repo = VendasRepository();
  late TabController _tabController;

  List<Venda> _vendas = [];
  List<Map<String, dynamic>> _porGrupo = [];
  List<Map<String, dynamic>> _topProdutos = [];
  List<String> _grupos = [];
  String _grupoFiltro = 'Todos';
  bool _loading = true;
  String? _error;

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
        _repo.getVendasPorGrupo(),
        _repo.getTopProdutos(limit: 15),
      ]);
      if (!mounted) return;
      setState(() {
        _vendas = results[0] as List<Venda>;
        _grupos = ['Todos', ...(results[1] as List<String>)];
        _porGrupo = results[2] as List<Map<String, dynamic>>;
        _topProdutos = results[3] as List<Map<String, dynamic>>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<Venda> get _filteredVendas {
    if (_grupoFiltro == 'Todos') return _vendas;
    return _vendas.where((v) => v.grupo == _grupoFiltro).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Vendas'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Por Grupo'),
            Tab(text: 'Top Produtos'),
            Tab(text: 'Lista'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando vendas...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildPorGrupoTab(),
                    _buildTopProdutosTab(),
                    _buildListaTab(),
                  ],
                ),
    );
  }

  Widget _buildPorGrupoTab() {
    if (_porGrupo.isEmpty) {
      return const lw.EmptyWidget(
        message: 'Nenhum dado de vendas disponível.',
        icon: Icons.bar_chart_outlined,
      );
    }

    final maxVal = _porGrupo.fold<int>(
      1,
      (m, e) => (e['total_vendido'] as int? ?? 0) > m ? (e['total_vendido'] as int? ?? 0) : m,
    );

    final colors = [
      AppColors.green, AppColors.blue, AppColors.amber,
      AppColors.purple, AppColors.cyan, AppColors.statusAvaria,
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          // Gráfico de barras
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Vendas por Grupo',
                    style: TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                const SizedBox(height: 16),
                SizedBox(
                  height: 220,
                  child: BarChart(
                    BarChartData(
                      backgroundColor: Colors.transparent,
                      gridData: FlGridData(
                        show: true,
                        drawVerticalLine: false,
                        getDrawingHorizontalLine: (_) => FlLine(
                          color: AppColors.surfaceBorder,
                          strokeWidth: 1,
                        ),
                      ),
                      borderData: FlBorderData(show: false),
                      titlesData: FlTitlesData(
                        leftTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            reservedSize: 40,
                            getTitlesWidget: (v, meta) => Text(
                              CamdaNumberUtils.formatInt(v),
                              style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
                            ),
                          ),
                        ),
                        rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        bottomTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            getTitlesWidget: (v, meta) {
                              final idx = v.toInt();
                              if (idx < 0 || idx >= _porGrupo.length) return const SizedBox.shrink();
                              final grupo = (_porGrupo[idx]['grupo'] as String? ?? '');
                              return Padding(
                                padding: const EdgeInsets.only(top: 4),
                                child: Text(
                                  grupo.length > 8 ? grupo.substring(0, 8) : grupo,
                                  style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
                                ),
                              );
                            },
                          ),
                        ),
                      ),
                      barGroups: _porGrupo.asMap().entries.map((e) {
                        final color = colors[e.key % colors.length];
                        return BarChartGroupData(
                          x: e.key,
                          barRods: [
                            BarChartRodData(
                              toY: (e.value['total_vendido'] as int? ?? 0).toDouble(),
                              color: color,
                              width: 18,
                              borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                            ),
                          ],
                        );
                      }).toList(),
                      maxY: maxVal.toDouble() * 1.2,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          // Cards de grupo
          ..._porGrupo.asMap().entries.map((e) {
            final color = colors[e.key % colors.length];
            final total = e.value['total_vendido'] as int? ?? 0;
            final prods = e.value['produtos'] as int? ?? 0;
            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _GrupoCard(
                grupo: e.value['grupo'] as String? ?? '',
                totalVendido: total,
                produtos: prods,
                color: color,
              ).animate().fadeIn(duration: 250.ms, delay: (e.key * 50).ms),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildTopProdutosTab() {
    if (_topProdutos.isEmpty) {
      return const lw.EmptyWidget(message: 'Nenhum dado de top produtos.', icon: Icons.star_outline);
    }

    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: _topProdutos.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) {
        final item = _topProdutos[i];
        final total = item['total_vendido'] as int? ?? 0;
        final produto = item['produto'] as String? ?? '';
        final grupo = item['grupo'] as String? ?? '';

        return Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.surfaceBorder),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.green.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Center(
                  child: Text(
                    '${i + 1}',
                    style: const TextStyle(
                      fontFamily: 'JetBrainsMono',
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppColors.green,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(produto,
                        style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                        maxLines: 2, overflow: TextOverflow.ellipsis),
                    Text(grupo, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                  ],
                ),
              ),
              Text(
                CamdaNumberUtils.formatInt(total),
                style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.green),
              ),
            ],
          ),
        ).animate().fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }

  Widget _buildListaTab() {
    final filtered = _filteredVendas;

    return Column(
      children: [
        if (_grupos.length > 1)
          Padding(
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
          ),
        Expanded(
          child: filtered.isEmpty
              ? const lw.EmptyWidget(message: 'Nenhuma venda encontrada.', icon: Icons.bar_chart_outlined)
              : ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 4),
                  itemBuilder: (context, i) {
                    final v = filtered[i];
                    return Container(
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppColors.surfaceBorder),
                      ),
                      child: ListTile(
                        dense: true,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                        title: Text(v.produto,
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                            maxLines: 2, overflow: TextOverflow.ellipsis),
                        subtitle: Text(v.grupo, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                        trailing: Text(
                          CamdaNumberUtils.formatInt(v.qtdVendida),
                          style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.green),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _GrupoCard extends StatelessWidget {
  final String grupo;
  final int totalVendido;
  final int produtos;
  final Color color;

  const _GrupoCard({
    required this.grupo,
    required this.totalVendido,
    required this.produtos,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 40,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(grupo,
                    style: const TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                Text('$produtos produto(s)', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
              ],
            ),
          ),
          Text(
            CamdaNumberUtils.formatInt(totalVendido),
            style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 18, fontWeight: FontWeight.w700, color: color),
          ),
        ],
      ),
    );
  }
}
