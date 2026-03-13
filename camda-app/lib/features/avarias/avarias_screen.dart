import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/avaria.dart';
import '../../data/repositories/avarias_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/glass_card.dart';

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
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, i) {
        final avaria = items[i];
        return _AvariaCard(
          avaria: avaria,
          showResolve: showResolve,
          onResolve: () => _resolver(avaria),
        ).animate().fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }

  void _showRegistrarDialog() {
    final codigoCtrl = TextEditingController();
    final produtoCtrl = TextEditingController();
    final motivoCtrl = TextEditingController();
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
                Row(children: [
                  const Text('Quantidade:', style: TextStyle(color: AppColors.textSecondary)),
                  const Spacer(),
                  IconButton(
                    onPressed: () => setDialogState(() => qtd = (qtd - 1).clamp(1, 9999)),
                    icon: const Icon(Icons.remove, size: 18),
                  ),
                  Text('$qtd', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.red)),
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
                try {
                  await _repo.registrar(
                    codigo: codigoCtrl.text.trim(),
                    produto: produtoCtrl.text.trim(),
                    qtd: qtd,
                    motivo: motivoCtrl.text.trim(),
                  );
                  await _loadData();
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
                  );
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: AppColors.red, foregroundColor: Colors.white),
              child: const Text('Registrar'),
            ),
          ],
        );
      }),
    );
  }
}

class _AvariaCard extends StatelessWidget {
  final Avaria avaria;
  final bool showResolve;
  final VoidCallback onResolve;

  const _AvariaCard({
    required this.avaria,
    required this.showResolve,
    required this.onResolve,
  });

  @override
  Widget build(BuildContext context) {
    final color = avaria.isAberta ? AppColors.red : AppColors.green;
    final dt = CamdaDateUtils.parseFlexible(avaria.registradoEm);
    final dataStr = dt != null ? CamdaDateUtils.formatDate(dt) : avaria.registradoEm;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Expanded(
              child: Text(
                avaria.produto,
                style: const TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                '${avaria.qtdAvariada} un.',
                style: TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
            ),
          ]),
          const SizedBox(height: 4),
          Text(avaria.codigo, style: const TextStyle(fontSize: 11, color: AppColors.textMuted, fontFamily: 'JetBrainsMono')),
          if (avaria.motivo.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(avaria.motivo, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          ],
          const SizedBox(height: 8),
          Row(children: [
            Text(dataStr, style: const TextStyle(fontSize: 10, color: AppColors.textDisabled)),
            const Spacer(),
            if (showResolve)
              TextButton.icon(
                onPressed: onResolve,
                icon: const Icon(Icons.check, size: 14),
                label: const Text('Resolver', style: TextStyle(fontSize: 12)),
                style: TextButton.styleFrom(
                  foregroundColor: AppColors.green,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
          ]),
        ],
      ),
    );
  }
}
