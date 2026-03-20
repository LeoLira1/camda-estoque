import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/validade_lote.dart';
import '../../data/repositories/validade_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/stat_card.dart';

// Opções de filtro de dias
enum _DiasFiltro {
  todos,
  vencidos,
  ate30,
  ate60,
  ate90,
  ok,
}

extension _DiasFiltroLabel on _DiasFiltro {
  String get label {
    switch (this) {
      case _DiasFiltro.todos:   return 'Todos';
      case _DiasFiltro.vencidos: return 'Vencidos';
      case _DiasFiltro.ate30:   return '≤ 30 dias';
      case _DiasFiltro.ate60:   return '≤ 60 dias';
      case _DiasFiltro.ate90:   return '≤ 90 dias';
      case _DiasFiltro.ok:      return 'OK (> 90 dias)';
    }
  }

  Color get color {
    switch (this) {
      case _DiasFiltro.todos:    return AppColors.textMuted;
      case _DiasFiltro.vencidos: return AppColors.red;
      case _DiasFiltro.ate30:    return AppColors.amber;
      case _DiasFiltro.ate60:    return const Color(0xFFFFCC44);
      case _DiasFiltro.ate90:    return AppColors.cyan;
      case _DiasFiltro.ok:       return AppColors.green;
    }
  }
}

class ValidadeScreen extends StatefulWidget {
  const ValidadeScreen({super.key});

  @override
  State<ValidadeScreen> createState() => _ValidadeScreenState();
}

class _ValidadeScreenState extends State<ValidadeScreen> {
  final _repo = ValidadeRepository();

  List<ValidadeLote> _todos = [];
  List<String> _grupos = [];
  String _grupoFiltro = 'Todos';
  _DiasFiltro _diasFiltro = _DiasFiltro.todos;
  ValidadeResumo? _resumo;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
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

  List<ValidadeLote> get _filtered {
    var list = _grupoFiltro == 'Todos'
        ? _todos
        : _todos.where((l) => l.grupo == _grupoFiltro).toList();

    switch (_diasFiltro) {
      case _DiasFiltro.todos:
        return list;
      case _DiasFiltro.vencidos:
        return list.where((l) => l.isVencido).toList();
      case _DiasFiltro.ate30:
        return list
            .where((l) => !l.isVencido && l.diasParaVencer <= 30)
            .toList()
          ..sort((a, b) => a.diasParaVencer.compareTo(b.diasParaVencer));
      case _DiasFiltro.ate60:
        return list
            .where((l) => !l.isVencido && l.diasParaVencer <= 60)
            .toList()
          ..sort((a, b) => a.diasParaVencer.compareTo(b.diasParaVencer));
      case _DiasFiltro.ate90:
        return list
            .where((l) => !l.isVencido && l.diasParaVencer <= 90)
            .toList()
          ..sort((a, b) => a.diasParaVencer.compareTo(b.diasParaVencer));
      case _DiasFiltro.ok:
        return list.where((l) => !l.isVencido && l.diasParaVencer > 90).toList();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text('Validade de Lotes'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando validade...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : Column(
                  children: [
                    if (_resumo != null) _buildResumoBar(),
                    _buildFilters(),
                    Expanded(child: _buildList()),
                  ],
                ),
    );
  }

  Widget _buildResumoBar() {
    final r = _resumo!;
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: StatCardRow(cards: [
        StatCard(value: r.vencidos.toString(), label: 'Vencidos', valueColor: AppColors.red),
        StatCard(value: r.criticos.toString(), label: 'Críticos', valueColor: AppColors.statusAvaria),
        StatCard(value: r.alertas.toString(), label: 'Alertas', valueColor: AppColors.amber),
        StatCard(
          value: (r.total - r.vencidos - r.criticos - r.alertas).toString(),
          label: 'OK',
          valueColor: AppColors.green,
        ),
      ]),
    );
  }

  Widget _buildFilters() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
      child: Row(
        children: [
          Expanded(child: _buildDiasDropdown()),
          const SizedBox(width: 10),
          if (_grupos.length > 1) Expanded(child: _buildCategoriaDropdown()),
        ],
      ),
    );
  }

  Widget _buildDiasDropdown() {
    final color = _diasFiltro.color;
    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<_DiasFiltro>(
          value: _diasFiltro,
          isExpanded: true,
          icon: Icon(Icons.keyboard_arrow_down, size: 18, color: color),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: color,
            fontFamily: 'Outfit',
          ),
          dropdownColor: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(10),
          items: _DiasFiltro.values.map((f) {
            return DropdownMenuItem(
              value: f,
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(
                      color: f.color,
                      shape: BoxShape.circle,
                    ),
                  ),
                  Text(f.label, style: TextStyle(color: f.color, fontSize: 12)),
                ],
              ),
            );
          }).toList(),
          onChanged: (v) {
            if (v != null) setState(() => _diasFiltro = v);
          },
        ),
      ),
    );
  }

  Widget _buildCategoriaDropdown() {
    return Container(
      height: 40,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: _grupoFiltro == 'Todos'
              ? AppColors.textDisabled.withOpacity(0.4)
              : AppColors.blue.withOpacity(0.5),
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _grupoFiltro,
          isExpanded: true,
          icon: Icon(
            Icons.keyboard_arrow_down,
            size: 18,
            color: _grupoFiltro == 'Todos' ? AppColors.textMuted : AppColors.blue,
          ),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: _grupoFiltro == 'Todos' ? AppColors.textMuted : AppColors.blue,
            fontFamily: 'Outfit',
          ),
          dropdownColor: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(10),
          items: _grupos.map((g) {
            final isSelected = g == _grupoFiltro;
            return DropdownMenuItem(
              value: g,
              child: Text(
                g,
                style: TextStyle(
                  color: isSelected ? AppColors.blue : AppColors.textMuted,
                  fontSize: 12,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            );
          }).toList(),
          onChanged: (v) {
            if (v != null) setState(() => _grupoFiltro = v);
          },
        ),
      ),
    );
  }

  Widget _buildList() {
    final items = _filtered;
    if (items.isEmpty) {
      return lw.EmptyWidget(
        message: 'Nenhum lote encontrado para os filtros selecionados.',
        icon: Icons.event_available_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
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
    } else if (lote.diasParaVencer <= 7) {
      statusColor = AppColors.statusAvaria;
      statusText = '${lote.diasParaVencer}d';
    } else if (lote.diasParaVencer <= 30) {
      statusColor = AppColors.amber;
      statusText = '${lote.diasParaVencer}d';
    } else if (lote.diasParaVencer <= 60) {
      statusColor = const Color(0xFFFFCC44);
      statusText = '${lote.diasParaVencer}d';
    } else if (lote.diasParaVencer <= 90) {
      statusColor = AppColors.cyan;
      statusText = '${lote.diasParaVencer}d';
    } else {
      statusColor = AppColors.green;
      statusText = '${lote.diasParaVencer}d';
    }

    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
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
                  style: TextStyle(
                    fontFamily: 'Outfit',
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface,
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
                style: TextStyle(
                  fontFamily: 'JetBrainsMono',
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: Theme.of(context).colorScheme.onSurface,
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
