import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/produto.dart';
import '../../data/repositories/estoque_repository.dart';
import '../../shared/widgets/stat_card.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class EstoqueScreen extends StatefulWidget {
  const EstoqueScreen({super.key});

  @override
  State<EstoqueScreen> createState() => _EstoqueScreenState();
}

class _EstoqueScreenState extends State<EstoqueScreen> {
  final _repo = EstoqueRepository();
  final _searchCtrl = TextEditingController();

  List<Produto> _all = [];
  List<Produto> _filtered = [];
  List<String> _categorias = [];
  String _categoriaFiltro = 'Todos';
  String _statusFiltro = 'Todos';
  bool _loading = true;
  String? _error;

  static const _statusOptions = ['Todos', 'ok', 'falta', 'sobra'];

  @override
  void initState() {
    super.initState();
    _searchCtrl.addListener(_applyFilter);
    _loadData();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final results = await Future.wait([
        _repo.getAll(),
        _repo.getCategorias(),
      ]);
      if (!mounted) return;
      setState(() {
        _all = results[0] as List<Produto>;
        _categorias = ['Todos', ...(results[1] as List<String>)];
        _loading = false;
      });
      _applyFilter();
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _applyFilter() {
    final query = _searchCtrl.text.trim().toLowerCase();
    setState(() {
      _filtered = _all.where((p) {
        final matchSearch = query.isEmpty ||
            p.produto.toLowerCase().contains(query) ||
            p.codigo.toLowerCase().contains(query) ||
            p.categoria.toLowerCase().contains(query);
        final matchCat = _categoriaFiltro == 'Todos' || p.categoria == _categoriaFiltro;
        final matchStatus = _statusFiltro == 'Todos' || p.status == _statusFiltro;
        return matchSearch && matchCat && matchStatus;
      }).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Estoque Mestre'),
        actions: [
          IconButton(
            onPressed: _loadData,
            icon: const Icon(Icons.refresh, size: 20),
            tooltip: 'Atualizar',
          ),
        ],
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando estoque...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : Column(
                  children: [
                    _buildFilters(),
                    _buildStatBar(),
                    Expanded(child: _buildList()),
                  ],
                ),
    );
  }

  Widget _buildFilters() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      child: Column(
        children: [
          // Busca
          TextField(
            controller: _searchCtrl,
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
            decoration: InputDecoration(
              hintText: 'Buscar produto, código ou categoria...',
              prefixIcon: const Icon(Icons.search, color: AppColors.textMuted, size: 18),
              suffixIcon: _searchCtrl.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, color: AppColors.textMuted, size: 16),
                      onPressed: () { _searchCtrl.clear(); _applyFilter(); },
                    )
                  : null,
              isDense: true,
            ),
          ),
          const SizedBox(height: 8),
          // Filtros de status e categoria
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                // Status chips
                ..._statusOptions.map((s) => Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ChoiceChip(
                        label: Text(_statusLabel(s)),
                        selected: _statusFiltro == s,
                        selectedColor: _statusChipColor(s),
                        onSelected: (_) => setState(() {
                          _statusFiltro = s;
                          _applyFilter();
                        }),
                        labelStyle: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: _statusFiltro == s ? Colors.white : AppColors.textMuted,
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      ),
                    )),
                const SizedBox(width: 6),
                // Categoria dropdown
                if (_categorias.length > 1)
                  DropdownButton<String>(
                    value: _categoriaFiltro,
                    dropdownColor: AppColors.surface,
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    underline: const SizedBox.shrink(),
                    icon: const Icon(Icons.arrow_drop_down, color: AppColors.textMuted, size: 18),
                    items: _categorias
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (v) => setState(() {
                      _categoriaFiltro = v!;
                      _applyFilter();
                    }),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatBar() {
    final faltas = _filtered.where((p) => p.status == 'falta').length;
    final sobras = _filtered.where((p) => p.status == 'sobra').length;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        children: [
          Text(
            '${_filtered.length} produto(s)',
            style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
          ),
          const Spacer(),
          if (faltas > 0)
            Text('$faltas falta(s)', style: const TextStyle(fontSize: 11, color: AppColors.red)),
          if (faltas > 0 && sobras > 0)
            const Text(' · ', style: TextStyle(fontSize: 11, color: AppColors.textDisabled)),
          if (sobras > 0)
            Text('$sobras sobra(s)', style: const TextStyle(fontSize: 11, color: AppColors.amber)),
        ],
      ),
    );
  }

  Widget _buildList() {
    if (_filtered.isEmpty) {
      return const lw.EmptyWidget(
        message: 'Nenhum produto encontrado.\nAjuste os filtros ou importe dados.',
        icon: Icons.inventory_2_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      itemCount: _filtered.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, index) {
        final p = _filtered[index];
        return _ProdutoTile(produto: p)
            .animate()
            .fadeIn(duration: 250.ms, delay: (index * 20).clamp(0, 400).ms);
      },
    );
  }

  String _statusLabel(String s) {
    switch (s) {
      case 'ok': return 'OK';
      case 'falta': return 'Falta';
      case 'sobra': return 'Sobra';
      default: return 'Todos';
    }
  }

  Color _statusChipColor(String s) {
    switch (s) {
      case 'ok': return AppColors.green;
      case 'falta': return AppColors.red;
      case 'sobra': return AppColors.amber;
      default: return AppColors.blue;
    }
  }
}

class _ProdutoTile extends StatelessWidget {
  final Produto produto;

  const _ProdutoTile({required this.produto});

  @override
  Widget build(BuildContext context) {
    final statusColor = AppColors.statusColor(produto.status);

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: produto.temDivergencia
              ? statusColor.withOpacity(0.3)
              : AppColors.surfaceBorder,
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.12),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(
            produto.isOk ? Icons.check_circle_outline : Icons.error_outline,
            color: statusColor,
            size: 20,
          ),
        ),
        title: Text(
          produto.produto,
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
            Text(
              produto.categoria,
              style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
            ),
            if (produto.observacoes.isNotEmpty)
              Text(
                produto.observacoes,
                style: const TextStyle(
                  fontSize: 10,
                  color: AppColors.textDisabled,
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
          ],
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              CamdaNumberUtils.formatInt(produto.qtdSistema),
              style: TextStyle(
                fontFamily: 'JetBrainsMono',
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: statusColor,
              ),
            ),
            if (produto.temDivergencia)
              Text(
                CamdaNumberUtils.formatDiff(produto.diferenca),
                style: TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 11,
                  color: statusColor.withOpacity(0.7),
                ),
              ),
            StatusBadge(status: produto.status, compact: true),
          ],
        ),
      ),
    );
  }
}
