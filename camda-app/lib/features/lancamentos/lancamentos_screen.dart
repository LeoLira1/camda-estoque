import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/lancamento.dart';
import '../../data/models/produto.dart';
import '../../data/repositories/lancamentos_repository.dart';
import '../../data/repositories/estoque_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/stat_card.dart';
import '../../shared/widgets/glass_card.dart';

class LancamentosScreen extends StatefulWidget {
  const LancamentosScreen({super.key});

  @override
  State<LancamentosScreen> createState() => _LancamentosScreenState();
}

class _LancamentosScreenState extends State<LancamentosScreen>
    with SingleTickerProviderStateMixin {
  final _repo = LancamentosRepository();
  final _estoqueRepo = EstoqueRepository();
  late TabController _tabController;

  List<Lancamento> _lancamentos = [];
  List<Map<String, dynamic>> _resumoTipos = [];
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
      final results = await Future.wait([
        _repo.getAll(),
        _repo.getResumoTipos(),
      ]);
      if (!mounted) return;
      setState(() {
        _lancamentos = results[0] as List<Lancamento>;
        _resumoTipos = results[1] as List<Map<String, dynamic>>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _excluir(Lancamento l) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Confirmar exclusão'),
        content: Text('Excluir lançamento de "${l.produto}"?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.red, foregroundColor: Colors.white),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _repo.excluir(l.id);
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
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Lançamentos Manuais'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Histórico'),
            Tab(text: 'Resumo'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showNovoLancamento,
        backgroundColor: AppColors.green,
        foregroundColor: AppColors.background,
        icon: const Icon(Icons.add),
        label: const Text('Novo', style: TextStyle(fontWeight: FontWeight.w700)),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando lançamentos...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildHistorico(),
                    _buildResumo(),
                  ],
                ),
    );
  }

  Widget _buildHistorico() {
    if (_lancamentos.isEmpty) {
      return const lw.EmptyWidget(
        message: 'Nenhum lançamento registrado.\nUse o botão + para adicionar.',
        icon: Icons.receipt_long_outlined,
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 90),
      itemCount: _lancamentos.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, i) {
        final l = _lancamentos[i];
        return _LancamentoTile(
          lancamento: l,
          onDelete: () => _excluir(l),
        ).animate().fadeIn(duration: 250.ms, delay: (i * 20).clamp(0, 400).ms);
      },
    );
  }

  Widget _buildResumo() {
    final totalEntradas = _lancamentos.where((l) => l.tipo == 'entrada').fold(0, (s, l) => s + l.quantidade);
    final totalSaidas = _lancamentos.where((l) => l.tipo == 'saida').fold(0, (s, l) => s + l.quantidade);
    final totalAjustes = _lancamentos.where((l) => l.tipo == 'ajuste').fold(0, (s, l) => s + l.quantidade);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          StatCardRow(cards: [
            StatCard(value: CamdaNumberUtils.formatInt(_lancamentos.length), label: 'Total', valueColor: AppColors.blue),
            StatCard(value: CamdaNumberUtils.formatInt(totalEntradas), label: 'Entradas', valueColor: AppColors.green),
            StatCard(value: CamdaNumberUtils.formatInt(totalSaidas), label: 'Saídas', valueColor: AppColors.red),
          ]).animate().fadeIn(duration: 400.ms),
          const SizedBox(height: 12),
          if (_resumoTipos.isNotEmpty)
            GlassCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Por tipo', style: TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                  const SizedBox(height: 12),
                  ..._resumoTipos.map((r) {
                    final tipo = r['tipo']?.toString() ?? '';
                    final totalRegs = r['total_registros'] as int? ?? 0;
                    final totalQtd = r['total_quantidade'] as int? ?? 0;
                    final color = _tipoColor(tipo);
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(children: [
                        Container(
                          width: 8, height: 8,
                          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
                        ),
                        const SizedBox(width: 10),
                        Expanded(child: Text(_tipoLabel(tipo), style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w600))),
                        Text('$totalRegs reg.', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                        const SizedBox(width: 12),
                        Text(CamdaNumberUtils.formatInt(totalQtd), style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 14, fontWeight: FontWeight.w700, color: color)),
                      ]),
                    );
                  }),
                ],
              ),
            ).animate().fadeIn(duration: 400.ms, delay: 100.ms),
        ],
      ),
    );
  }

  void _showNovoLancamento() {
    final codigoCtrl = TextEditingController();
    final produtoCtrl = TextEditingController();
    final categoriaCtrl = TextEditingController();
    final motivoCtrl = TextEditingController();
    int quantidade = 1;
    String tipo = 'entrada';
    List<Produto> _sugestoes = [];
    bool _buscando = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(builder: (ctx, setS) {
        Future<void> buscarProduto(String query) async {
          if (query.length < 2) { setS(() => _sugestoes = []); return; }
          setS(() => _buscando = true);
          try {
            final prods = await _estoqueRepo.getAll();
            final lower = query.toLowerCase();
            setS(() {
              _sugestoes = prods.where((p) =>
                p.produto.toLowerCase().contains(lower) ||
                p.codigo.toLowerCase().contains(lower)
              ).take(5).toList();
              _buscando = false;
            });
          } catch (_) { setS(() => _buscando = false); }
        }

        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(ctx).viewInsets.bottom,
            left: 16, right: 16, top: 20,
          ),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                // Handle
                Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2)))),
                const SizedBox(height: 16),
                const Text('Novo Lançamento', style: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                const SizedBox(height: 16),

                // Tipo
                Row(children: ['entrada', 'saida', 'ajuste'].map((t) => Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(_tipoLabel(t), style: const TextStyle(fontSize: 12)),
                    selected: tipo == t,
                    selectedColor: _tipoColor(t),
                    onSelected: (_) => setS(() => tipo = t),
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                  ),
                )).toList()),
                const SizedBox(height: 12),

                // Produto (com autocomplete)
                TextField(
                  controller: produtoCtrl,
                  decoration: const InputDecoration(labelText: 'Produto', isDense: true),
                  onChanged: (v) => buscarProduto(v),
                ),
                if (_buscando) const LinearProgressIndicator(color: AppColors.green, minHeight: 2),
                if (_sugestoes.isNotEmpty)
                  Container(
                    decoration: BoxDecoration(color: AppColors.surfaceVariant, borderRadius: BorderRadius.circular(8)),
                    child: Column(children: _sugestoes.map((p) => ListTile(
                      dense: true,
                      title: Text(p.produto, style: const TextStyle(fontSize: 12, color: AppColors.textPrimary)),
                      subtitle: Text('${p.codigo} · ${p.categoria}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
                      onTap: () {
                        codigoCtrl.text = p.codigo;
                        produtoCtrl.text = p.produto;
                        categoriaCtrl.text = p.categoria;
                        setS(() => _sugestoes = []);
                      },
                    )).toList()),
                  ),
                const SizedBox(height: 8),

                Row(children: [
                  Expanded(child: TextField(controller: codigoCtrl, decoration: const InputDecoration(labelText: 'Código', isDense: true))),
                  const SizedBox(width: 8),
                  Expanded(child: TextField(controller: categoriaCtrl, decoration: const InputDecoration(labelText: 'Categoria', isDense: true))),
                ]),
                const SizedBox(height: 12),

                // Quantidade
                Row(children: [
                  const Text('Quantidade:', style: TextStyle(color: AppColors.textSecondary, fontSize: 14)),
                  const Spacer(),
                  IconButton(onPressed: () => setS(() => quantidade = (quantidade - 1).clamp(1, 99999)), icon: const Icon(Icons.remove_circle_outline, size: 22, color: AppColors.textMuted)),
                  Text('$quantidade', style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 20, fontWeight: FontWeight.w700, color: _tipoColor(tipo))),
                  IconButton(onPressed: () => setS(() => quantidade++), icon: const Icon(Icons.add_circle_outline, size: 22, color: AppColors.textMuted)),
                ]),
                const SizedBox(height: 8),
                TextField(controller: motivoCtrl, maxLines: 2, decoration: const InputDecoration(labelText: 'Motivo (opcional)', isDense: true)),
                const SizedBox(height: 20),

                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () async {
                      if (produtoCtrl.text.trim().isEmpty) return;
                      Navigator.pop(ctx);
                      try {
                        await _repo.inserir(
                          codigo: codigoCtrl.text.trim(),
                          produto: produtoCtrl.text.trim(),
                          categoria: categoriaCtrl.text.trim(),
                          tipo: tipo,
                          quantidade: quantidade,
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
                    style: ElevatedButton.styleFrom(backgroundColor: _tipoColor(tipo), foregroundColor: Colors.white),
                    child: Text('Registrar ${_tipoLabel(tipo).toUpperCase()}',
                        style: const TextStyle(fontWeight: FontWeight.w700, letterSpacing: 1)),
                  ),
                ),
                const SizedBox(height: 20),
              ],
            ),
          ),
        );
      }),
    );
  }

  Color _tipoColor(String tipo) {
    switch (tipo) {
      case 'entrada': return AppColors.green;
      case 'saida': return AppColors.red;
      case 'ajuste': return AppColors.amber;
      default: return AppColors.blue;
    }
  }

  String _tipoLabel(String tipo) {
    switch (tipo) {
      case 'entrada': return 'Entrada';
      case 'saida': return 'Saída';
      case 'ajuste': return 'Ajuste';
      default: return tipo;
    }
  }
}

class _LancamentoTile extends StatelessWidget {
  final Lancamento lancamento;
  final VoidCallback onDelete;

  const _LancamentoTile({required this.lancamento, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    Color color;
    IconData icon;
    String prefixo;
    switch (lancamento.tipo) {
      case 'entrada': color = AppColors.green; icon = Icons.add_circle_outline; prefixo = '+'; break;
      case 'saida':   color = AppColors.red;   icon = Icons.remove_circle_outline; prefixo = '-'; break;
      default:        color = AppColors.amber; icon = Icons.tune_outlined; prefixo = '±';
    }

    final dt = CamdaDateUtils.parseFlexible(lancamento.registradoEm);
    final dataStr = dt != null ? CamdaDateUtils.formatDateTime(dt) : lancamento.registradoEm;

    return Dismissible(
      key: ValueKey(lancamento.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        onDelete();
        return false;
      },
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        decoration: BoxDecoration(color: AppColors.red.withOpacity(0.2), borderRadius: BorderRadius.circular(12)),
        child: const Icon(Icons.delete_outline, color: AppColors.red),
      ),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          leading: Container(
            width: 40, height: 40,
            decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
            child: Icon(icon, color: color, size: 20),
          ),
          title: Text(lancamento.produto,
              style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
              maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (lancamento.motivo.isNotEmpty)
              Text(lancamento.motivo, style: const TextStyle(fontSize: 11, color: AppColors.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(dataStr, style: const TextStyle(fontSize: 10, color: AppColors.textDisabled)),
          ]),
          trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(
              '$prefixo${CamdaNumberUtils.formatInt(lancamento.quantidade)}',
              style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 16, fontWeight: FontWeight.w700, color: color),
            ),
            Text(lancamento.categoria, style: const TextStyle(fontSize: 9, color: AppColors.textDisabled)),
          ]),
        ),
      ),
    );
  }
}
