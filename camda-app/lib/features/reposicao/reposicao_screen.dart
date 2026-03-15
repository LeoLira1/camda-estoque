import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/reposicao.dart';
import '../../data/repositories/reposicao_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class ReposicaoScreen extends StatefulWidget {
  const ReposicaoScreen({super.key});

  @override
  State<ReposicaoScreen> createState() => _ReposicaoScreenState();
}

class _ReposicaoScreenState extends State<ReposicaoScreen>
    with SingleTickerProviderStateMixin {
  final _repo = ReposicaoRepository();
  late TabController _tabController;

  List<Reposicao> _todos = [];
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
      setState(() { _todos = data; _loading = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _marcarReposto(Reposicao item) async {
    try {
      await _repo.marcarReposto(item.id);
      await _loadData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final pendentes = _todos.where((r) => r.pendente).toList();
    final repostos = _todos.where((r) => !r.pendente).toList();

    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Repor na Loja'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Pendentes (${_loading ? '...' : pendentes.length})'),
            Tab(text: 'Repostos (${_loading ? '...' : repostos.length})'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando reposições...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildList(pendentes, showRepor: true),
                    _buildList(repostos, showRepor: false),
                  ],
                ),
    );
  }

  Widget _buildList(List<Reposicao> items, {required bool showRepor}) {
    if (items.isEmpty) {
      return lw.EmptyWidget(
        message: showRepor
            ? 'Nenhum item pendente de reposição.'
            : 'Nenhum item reposto ainda.',
        icon: showRepor ? Icons.store_outlined : Icons.check_circle_outline,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) {
        final item = items[i];
        return _ReposicaoTile(
          item: item,
          showRepor: showRepor,
          onRepor: () => _marcarReposto(item),
        ).animate().fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }
}

class _InfoChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _InfoChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: RichText(
        text: TextSpan(
          children: [
            TextSpan(text: '$label: ', style: const TextStyle(fontFamily: 'Outfit', fontSize: 10, color: AppColors.textMuted)),
            TextSpan(text: value, style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, fontWeight: FontWeight.w700, color: color)),
          ],
        ),
      ),
    );
  }
}

class _ReposicaoTile extends StatelessWidget {
  final Reposicao item;
  final bool showRepor;
  final VoidCallback onRepor;

  const _ReposicaoTile({
    required this.item,
    required this.showRepor,
    required this.onRepor,
  });

  @override
  Widget build(BuildContext context) {
    final color = item.pendente ? AppColors.blue : AppColors.green;
    final dt = CamdaDateUtils.parseFlexible(item.criadoEm);
    final dataStr = dt != null ? CamdaDateUtils.formatDate(dt) : item.criadoEm;

    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.fromLTRB(14, 8, 10, 8),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            item.pendente ? Icons.store_outlined : Icons.check_circle_outline,
            color: color,
            size: 20,
          ),
        ),
        title: Text(
          item.produto,
          style: const TextStyle(
            fontFamily: 'Outfit',
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Text('Cód: ', style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, color: AppColors.textMuted)),
              Text(item.codigo.isNotEmpty ? item.codigo : '—',
                  style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.blue)),
              const Text(' · ', style: TextStyle(fontSize: 10, color: AppColors.textDisabled)),
              Flexible(child: Text(item.categoria, style: const TextStyle(fontSize: 11, color: AppColors.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis)),
            ]),
            const SizedBox(height: 2),
            Row(children: [
              _InfoChip(label: 'Vendido', value: '${item.qtdVendida} un.', color: AppColors.amber),
              const SizedBox(width: 8),
              _InfoChip(
                label: 'Estoque',
                value: '${item.qtdEstoque} un.',
                color: item.qtdEstoque > 0 ? AppColors.green : AppColors.red,
              ),
            ]),
            Text(dataStr, style: const TextStyle(fontSize: 10, color: AppColors.textDisabled)),
          ],
        ),
        trailing: showRepor
            ? IconButton(
                onPressed: onRepor,
                icon: const Icon(Icons.check_circle_outline, color: AppColors.green, size: 24),
                tooltip: 'Marcar como reposto',
              )
            : const Icon(Icons.check_circle, color: AppColors.green, size: 20),
      ),
    );
  }
}
