import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/number_utils.dart';
import '../../core/services/cache_service.dart';
import '../../data/models/produto.dart';
import '../../data/repositories/estoque_repository.dart';
import '../../data/models/avaria.dart';
import '../../data/repositories/avarias_repository.dart';
import '../../shared/widgets/stat_card.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class EstoqueScreen extends StatefulWidget {
  const EstoqueScreen({super.key});

  @override
  State<EstoqueScreen> createState() => _EstoqueScreenState();
}

class _EstoqueScreenState extends State<EstoqueScreen> {
  final _repo = EstoqueRepository();
  final _avariasRepo = AvariasRepository();
  final _searchCtrl = TextEditingController();

  List<Produto> _all = [];
  List<Produto> _filtered = [];
  List<String> _categorias = [];
  String _categoriaFiltro = 'Todos';
  String _statusFiltro = 'Todos';
  bool _loading = true;
  String? _error;
  bool _isOffline = false;
  Set<String> _avariaCodigos = {};
  Set<String> _divFaltaCodigos = {};
  Set<String> _divSobraCodigos = {};

  static const _statusOptions = ['Todos', 'ok', 'falta', 'sobra'];

  /// Palavras-chave que ativam filtro automático por status/avaria.
  static const _keywordFalta = {'falta', 'faltando'};
  static const _keywordSobra = {'sobra', 'sobrando'};
  static const _keywordAvaria = {'avaria', 'avarias'};

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
        _avariasRepo.getAll(apenasAbertas: true),
        _repo.getDivergenciaCodigos(status: 'falta'),
        _repo.getDivergenciaCodigos(status: 'sobra'),
      ]);
      if (!mounted) return;
      final avarias = results[2] as List<Avaria>;
      setState(() {
        _all = results[0] as List<Produto>;
        _categorias = ['Todos', ...(results[1] as List<String>)];
        _avariaCodigos = avarias.map((a) => a.codigo).toSet();
        _divFaltaCodigos = results[3] as Set<String>;
        _divSobraCodigos = results[4] as Set<String>;
        _loading = false;
        _isOffline = CacheService.isOffline;
      });
      _applyFilter();
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  /// Retorna o modo de filtro ativado pela palavra-chave digitada, ou null.
  /// 'falta' | 'sobra' | 'avaria' | null
  String? _detectKeyword(String query) {
    if (_keywordFalta.contains(query)) return 'falta';
    if (_keywordSobra.contains(query)) return 'sobra';
    if (_keywordAvaria.contains(query)) return 'avaria';
    return null;
  }

  void _applyFilter() {
    final query = _searchCtrl.text.trim().toLowerCase();
    final keyword = _detectKeyword(query);
    setState(() {
      _filtered = _all.where((p) {
        // Atalho por palavra-chave — ignora filtros de chip/categoria
        if (keyword == 'falta') return p.status == 'falta' || _divFaltaCodigos.contains(p.codigo);
        if (keyword == 'sobra') return p.status == 'sobra' || _divSobraCodigos.contains(p.codigo);
        if (keyword == 'avaria') return _avariaCodigos.contains(p.codigo);

        final matchSearch = query.isEmpty ||
            p.produto.toLowerCase().contains(query) ||
            p.codigo.toLowerCase().contains(query) ||
            p.categoria.toLowerCase().contains(query);
        final matchCat = _categoriaFiltro == 'Todos' || p.categoria == _categoriaFiltro;
        final matchStatus = _statusFiltro == 'Todos' ||
            p.status == _statusFiltro ||
            (_statusFiltro == 'falta' && _divFaltaCodigos.contains(p.codigo)) ||
            (_statusFiltro == 'sobra' && _divSobraCodigos.contains(p.codigo));
        return matchSearch && matchCat && matchStatus;
      }).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
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
                    if (_isOffline) _buildOfflineBanner(),
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
              hintText: 'Buscar ou digitar: falta, sobra, avaria...',
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
          _buildKeywordBanner(),
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

  Widget _buildKeywordBanner() {
    final keyword = _detectKeyword(_searchCtrl.text.trim().toLowerCase());
    if (keyword == null) return const SizedBox.shrink();

    final (label, color, icon) = switch (keyword) {
      'falta'  => ('Mostrando produtos faltando', AppColors.red, Icons.remove_circle_outline),
      'sobra'  => ('Mostrando produtos sobrando', AppColors.amber, Icons.add_circle_outline),
      'avaria' => ('Mostrando produtos com avaria', AppColors.statusAvaria, Icons.warning_amber_outlined),
      _        => ('', AppColors.blue, Icons.info_outline),
    };

    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.10),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 14),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
            ),
            const Spacer(),
            Text(
              '${_filtered.length} produto(s)',
              style: TextStyle(fontSize: 11, color: color.withOpacity(0.8)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOfflineBanner() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      color: AppColors.amber.withOpacity(0.12),
      child: Row(children: [
        const Icon(Icons.cloud_off_outlined, color: AppColors.amber, size: 16),
        const SizedBox(width: 8),
        const Expanded(
          child: Text(
            'Modo offline — dados em cache local',
            style: TextStyle(fontSize: 12, color: AppColors.amber, fontWeight: FontWeight.w500),
          ),
        ),
        GestureDetector(
          onTap: _loadData,
          child: const Text('Tentar novamente', style: TextStyle(fontSize: 11, color: AppColors.amber, decoration: TextDecoration.underline)),
        ),
      ]),
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
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: produto.temDivergencia
              ? statusColor.withOpacity(0.3)
              : Theme.of(context).colorScheme.outline,
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
          style: TextStyle(
            fontFamily: 'Outfit',
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: Theme.of(context).colorScheme.onSurface,
          ),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Text(
                'Cód: ',
                style: const TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 10,
                  color: AppColors.textMuted,
                ),
              ),
              Text(
                produto.codigo,
                style: const TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  color: AppColors.blue,
                ),
              ),
              if (produto.categoria.isNotEmpty) ...[
                const Text(' · ', style: TextStyle(fontSize: 10, color: AppColors.textDisabled)),
                Flexible(
                  child: Text(
                    produto.categoria,
                    style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ]),
            if (produto.nota.isNotEmpty)
              Text(
                produto.nota,
                style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                  color: AppColors.blue,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
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
