import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/mapa_posicao.dart';
import '../../data/models/produto.dart';
import '../../data/models/validade_lote.dart';
import '../../data/repositories/mapa_repository.dart';
import '../../data/repositories/estoque_repository.dart';
import '../../data/repositories/validade_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/glass_card.dart';

class MapaScreen extends StatefulWidget {
  const MapaScreen({super.key});

  @override
  State<MapaScreen> createState() => _MapaScreenState();
}

class _MapaScreenState extends State<MapaScreen>
    with SingleTickerProviderStateMixin {
  final _repo = MapaRepository();
  final _estoqueRepo = EstoqueRepository();
  final _validadeRepo = ValidadeRepository();
  late TabController _tabController;

  // Mapa data
  List<Rack> _racks = [];
  List<MapaPosicao> _todosPaletes = [];
  Map<String, int> _ocupacao = {};
  String? _selectedRack;
  String _selectedFace = 'A';
  String _searchQuery = '';
  List<MapaPosicao> _searchResults = [];
  bool _searching = false;
  final _searchCtrl = TextEditingController();

  // Info tab data
  List<Produto> _produtosFalta = [];
  List<Produto> _produtosSobra = [];
  List<ValidadeLote> _loteVencendo = [];
  List<Produto> _produtosParados = [];
  List<Produto> _estoqueCritico = [];

  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
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
      final results = await Future.wait([
        _repo.getRacks(),
        _repo.getTodosPaletes(),
        _repo.getOcupacao(),
        _estoqueRepo.getAll(status: 'falta'),
        _estoqueRepo.getAll(status: 'sobra'),
        _validadeRepo.getProximosAoVencer(dias: 30),
        _estoqueRepo.getParados(),
        _estoqueRepo.getCriticos(),
      ]);
      if (!mounted) return;
      setState(() {
        _racks = results[0] as List<Rack>;
        _todosPaletes = results[1] as List<MapaPosicao>;
        _ocupacao = results[2] as Map<String, int>;
        _produtosFalta = results[3] as List<Produto>;
        _produtosSobra = results[4] as List<Produto>;
        _loteVencendo = results[5] as List<ValidadeLote>;
        _produtosParados = results[6] as List<Produto>;
        _estoqueCritico = results[7] as List<Produto>;
        _selectedRack = _racks.isNotEmpty ? _racks.first.rackId : null;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _buscar(String query) async {
    if (query.trim().isEmpty) {
      setState(() { _searchResults = []; _searching = false; });
      return;
    }
    setState(() => _searching = true);
    try {
      final results = await _repo.buscarProduto(query);
      if (!mounted) return;
      setState(() { _searchResults = results; _searching = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _searching = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Mapa Visual'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Info'),
            Tab(text: 'Racks'),
            Tab(text: 'Buscar'),
            Tab(text: 'Ocupação'),
          ],
          padding: const EdgeInsets.symmetric(horizontal: 8),
        ),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando mapa...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildInfoTab(),
                    _buildRacksTab(),
                    _buildBuscarTab(),
                    _buildOcupacaoTab(),
                  ],
                ),
    );
  }

  // ── Aba Info ─────────────────────────────────────────────────────────────────

  Widget _buildInfoTab() {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _infoCard(
            title: 'Falta & Sobra',
            icon: Icons.swap_vert_circle_outlined,
            color: AppColors.red,
            badge: '${_produtosFalta.length + _produtosSobra.length}',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_produtosFalta.isNotEmpty) ...[
                  _infoSubHeader('Faltando', _produtosFalta.length, AppColors.red),
                  ..._produtosFalta.take(8).map((p) => _produtoRow(p, AppColors.red)),
                ],
                if (_produtosFalta.isNotEmpty && _produtosSobra.isNotEmpty)
                  const Divider(height: 16, color: AppColors.surfaceBorder),
                if (_produtosSobra.isNotEmpty) ...[
                  _infoSubHeader('Sobrando', _produtosSobra.length, AppColors.amber),
                  ..._produtosSobra.take(8).map((p) => _produtoRow(p, AppColors.amber)),
                ],
                if (_produtosFalta.isEmpty && _produtosSobra.isEmpty)
                  _emptyHint('Sem divergências de estoque'),
                _maisItens(_produtosFalta.length + _produtosSobra.length, 16),
              ],
            ),
          ),
          const SizedBox(height: 10),
          _infoCard(
            title: 'Vencendo em 30 dias',
            icon: Icons.event_busy_outlined,
            color: AppColors.statusAvaria,
            badge: '${_loteVencendo.length}',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_loteVencendo.isEmpty)
                  _emptyHint('Nenhum lote vencendo nos próximos 30 dias'),
                ..._loteVencendo.take(8).map((l) => _loteRow(l)),
                _maisItens(_loteVencendo.length, 8),
              ],
            ),
          ),
          const SizedBox(height: 10),
          _infoCard(
            title: 'Parados em Estoque',
            icon: Icons.hourglass_empty_outlined,
            color: AppColors.textMuted,
            badge: '${_produtosParados.length}',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_produtosParados.isEmpty)
                  _emptyHint('Nenhum produto parado'),
                ..._produtosParados.take(8).map((p) => _paradoRow(p)),
                _maisItens(_produtosParados.length, 8),
              ],
            ),
          ),
          const SizedBox(height: 10),
          _infoCard(
            title: 'Estoque Crítico',
            icon: Icons.warning_amber_outlined,
            color: AppColors.blue,
            badge: '${_estoqueCritico.length}',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_estoqueCritico.isEmpty)
                  _emptyHint('Nenhum produto em nível crítico'),
                ..._estoqueCritico.take(8).map((p) => _criticoRow(p)),
                _maisItens(_estoqueCritico.length, 8),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoCard({
    required String title,
    required IconData icon,
    required Color color,
    required String badge,
    required Widget child,
  }) {
    return GlassCard(
      borderRadius: 14,
      enableBlur: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontFamily: 'Outfit',
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: color,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(badge, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    ).animate().fadeIn(duration: 350.ms);
  }

  Widget _infoSubHeader(String label, int count, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(children: [
        Container(width: 3, height: 14, color: color, margin: const EdgeInsets.only(right: 6)),
        Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
        const SizedBox(width: 6),
        Text('($count)', style: const TextStyle(fontSize: 10, color: AppColors.textDisabled)),
      ]),
    );
  }

  Widget _emptyHint(String msg) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Text(msg, style: const TextStyle(fontSize: 12, color: AppColors.textMuted, fontStyle: FontStyle.italic)),
  );

  Widget _maisItens(int total, int shown) {
    if (total <= shown) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(
        '+ ${total - shown} itens. Acesse a tela correspondente para ver todos.',
        style: const TextStyle(fontSize: 10, color: AppColors.textDisabled, fontStyle: FontStyle.italic),
      ),
    );
  }

  Widget _produtoRow(Produto p, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Container(
          width: 30, height: 30,
          decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(7)),
          child: Icon(Icons.inventory_2_outlined, color: color, size: 15),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
            Text('${p.codigo}  ·  ${p.categoria}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
          ]),
        ),
        Text('${p.qtdSistema}', style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 14, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }

  Widget _loteRow(ValidadeLote l) {
    final dias = l.diasParaVencer;
    final color = l.isVencido ? AppColors.red : l.isCritico ? AppColors.statusAvaria : AppColors.amber;
    final diasLabel = l.isVencido ? 'Vencido há ${dias.abs()}d' : 'Vence em ${dias}d';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Container(
          width: 30, height: 30,
          decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(7)),
          child: Icon(Icons.event_outlined, color: color, size: 15),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
            Text('Lote: ${l.lote}  ·  ${l.grupo}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
          ]),
        ),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(diasLabel, style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, fontWeight: FontWeight.w600, color: color)),
          Text(CamdaDateUtils.formatDateStr(l.vencimento), style: const TextStyle(fontSize: 9, color: AppColors.textDisabled)),
        ]),
      ]),
    );
  }

  Widget _paradoRow(Produto p) {
    final ultimaContagem = p.ultimaContagem.isEmpty ? 'Nunca contado' : CamdaDateUtils.formatDateStr(p.ultimaContagem);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Container(
          width: 30, height: 30,
          decoration: BoxDecoration(color: AppColors.textMuted.withOpacity(0.1), borderRadius: BorderRadius.circular(7)),
          child: const Icon(Icons.hourglass_empty_outlined, color: AppColors.textMuted, size: 15),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(p.categoria, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
          ]),
        ),
        Text(ultimaContagem, style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 9, color: AppColors.textDisabled)),
      ]),
    );
  }

  Widget _criticoRow(Produto p) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Container(
          width: 30, height: 30,
          decoration: BoxDecoration(color: AppColors.blue.withOpacity(0.1), borderRadius: BorderRadius.circular(7)),
          child: const Icon(Icons.warning_amber_outlined, color: AppColors.blue, size: 15),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(p.categoria, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
          ]),
        ),
        Text('${p.qtdSistema}', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.blue)),
      ]),
    );
  }

  // ── Aba Racks ────────────────────────────────────────────────────────────────

  Widget _buildRacksTab() {
    return Column(
      children: [
        // Selector de rack
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _racks.map((r) => Padding(
                padding: const EdgeInsets.only(right: 6),
                child: ChoiceChip(
                  label: Text(r.nome, style: const TextStyle(fontSize: 12)),
                  selected: _selectedRack == r.rackId,
                  selectedColor: AppColors.green,
                  onSelected: (_) => setState(() => _selectedRack = r.rackId),
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                ),
              )).toList(),
            ),
          ),
        ),
        // Face selector
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          child: Row(
            children: [
              ChoiceChip(
                label: const Text('Frente (A)', style: TextStyle(fontSize: 12)),
                selected: _selectedFace == 'A',
                selectedColor: AppColors.blue,
                onSelected: (_) => setState(() => _selectedFace = 'A'),
              ),
              const SizedBox(width: 8),
              ChoiceChip(
                label: const Text('Fundo (B)', style: TextStyle(fontSize: 12)),
                selected: _selectedFace == 'B',
                selectedColor: AppColors.blue,
                onSelected: (_) => setState(() => _selectedFace = 'B'),
              ),
            ],
          ),
        ),
        // Grid do rack
        Expanded(
          child: _selectedRack != null
              ? _RackGrid(
                  rackId: _selectedRack!,
                  face: _selectedFace,
                  todosPaletes: _todosPaletes,
                )
              : const lw.EmptyWidget(message: 'Selecione um rack', icon: Icons.view_module_outlined),
        ),
      ],
    );
  }

  // ── Aba Buscar ───────────────────────────────────────────────────────────────

  Widget _buildBuscarTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchCtrl,
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
            decoration: InputDecoration(
              hintText: 'Buscar produto no armazém...',
              prefixIcon: _searching
                  ? const Padding(
                      padding: EdgeInsets.all(12),
                      child: SizedBox(
                        width: 18, height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, valueColor: AlwaysStoppedAnimation(AppColors.green)),
                      ),
                    )
                  : const Icon(Icons.search, color: AppColors.textMuted, size: 18),
              suffixIcon: _searchCtrl.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, size: 16, color: AppColors.textMuted),
                      onPressed: () { _searchCtrl.clear(); setState(() { _searchResults = []; }); },
                    )
                  : null,
            ),
            onChanged: (v) {
              setState(() => _searchQuery = v);
              Future.delayed(const Duration(milliseconds: 400), () {
                if (_searchQuery == v) _buscar(v);
              });
            },
          ),
        ),
        if (_searchResults.isEmpty && _searchCtrl.text.isNotEmpty && !_searching)
          const Expanded(child: lw.EmptyWidget(message: 'Produto não encontrado no mapa.', icon: Icons.search_off))
        else if (_searchResults.isEmpty)
          const Expanded(child: lw.EmptyWidget(message: 'Digite o nome do produto para buscar sua localização.', icon: Icons.map_outlined))
        else
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
              itemCount: _searchResults.length,
              separatorBuilder: (_, __) => const SizedBox(height: 6),
              itemBuilder: (context, i) {
                final pos = _searchResults[i];
                return _PosicaoCard(posicao: pos)
                    .animate()
                    .fadeIn(duration: 250.ms, delay: (i * 30).ms);
              },
            ),
          ),
      ],
    );
  }

  // ── Aba Ocupação ─────────────────────────────────────────────────────────────

  Widget _buildOcupacaoTab() {
    const totalPorFace = 13 * 4; // 52 células por face
    final totalOcupado = _ocupacao.values.fold(0, (a, b) => a + b);
    final totalCapacidade = _racks.length * 2 * totalPorFace;
    final pctGeral = totalCapacidade > 0 ? (totalOcupado / totalCapacidade * 100) : 0.0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        children: [
          // Resumo geral
          GlassCard(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  const Text('Ocupação Geral',
                      style: TextStyle(fontFamily: 'Outfit', fontSize: 15, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
                  Text(
                    '${pctGeral.toStringAsFixed(1)}%',
                    style: TextStyle(
                      fontFamily: 'JetBrainsMono',
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                      color: pctGeral > 80 ? AppColors.red : pctGeral > 50 ? AppColors.amber : AppColors.green,
                    ),
                  ),
                ]),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: pctGeral / 100,
                    minHeight: 8,
                    backgroundColor: AppColors.surfaceBorder,
                    valueColor: AlwaysStoppedAnimation(
                      pctGeral > 80 ? AppColors.red : pctGeral > 50 ? AppColors.amber : AppColors.green,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Text('$totalOcupado ocupadas', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                  Text('$totalCapacidade total', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                ]),
              ],
            ),
          ).animate().fadeIn(duration: 400.ms),
          const SizedBox(height: 12),
          // Por rack
          ..._racks.asMap().entries.map((e) {
            final rack = e.value;
            final ocA = _ocupacao['${rack.rackId}-A'] ?? 0;
            final ocB = _ocupacao['${rack.rackId}-B'] ?? 0;
            final total = rack.temFaceB ? totalPorFace * 2 : totalPorFace;
            final ocupado = ocA + ocB;
            final pct = total > 0 ? (ocupado / total * 100) : 0.0;

            return Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                child: Row(children: [
                  Container(
                    width: 36, height: 36,
                    decoration: BoxDecoration(
                      color: AppColors.green.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(child: Text(rack.nome,
                        style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 11, fontWeight: FontWeight.w700, color: AppColors.green))),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                        Text('A: $ocA  B: $ocB', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
                        Text('${pct.toStringAsFixed(0)}%',
                            style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 12, fontWeight: FontWeight.w600,
                                color: pct > 80 ? AppColors.red : AppColors.green)),
                      ]),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(3),
                        child: LinearProgressIndicator(
                          value: pct / 100,
                          minHeight: 5,
                          backgroundColor: AppColors.surfaceBorder,
                          valueColor: AlwaysStoppedAnimation(pct > 80 ? AppColors.red : AppColors.green),
                        ),
                      ),
                    ]),
                  ),
                ]),
              ).animate().fadeIn(duration: 250.ms, delay: (e.key * 30).ms),
            );
          }),
        ],
      ),
    );
  }
}

// ── Componentes do Mapa ────────────────────────────────────────────────────────

/// Grid visual de um rack (13 colunas × 4 níveis).
class _RackGrid extends StatelessWidget {
  final String rackId;
  final String face;
  final List<MapaPosicao> todosPaletes;

  const _RackGrid({
    required this.rackId,
    required this.face,
    required this.todosPaletes,
  });

  @override
  Widget build(BuildContext context) {
    final paletesMap = <String, MapaPosicao>{};
    for (final p in todosPaletes) {
      if (p.rua == rackId && p.face == face) {
        paletesMap[p.posKey] = p;
      }
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Legenda
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              _legendItem(AppColors.green.withOpacity(0.3), 'Ocupado'),
              const SizedBox(width: 12),
              _legendItem(AppColors.surfaceBorder, 'Vazio'),
            ]),
          ),
          // Níveis (4 → 1, de cima para baixo)
          ...List.generate(AppConstants.numNiveis, (nIdx) {
            final nivel = AppConstants.numNiveis - nIdx; // 4, 3, 2, 1
            return Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Row(
                children: [
                  // Label do nível
                  SizedBox(
                    width: 24,
                    child: Text('N$nivel',
                        style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 9, color: AppColors.textMuted)),
                  ),
                  // 13 colunas
                  ...List.generate(AppConstants.numColunas, (cIdx) {
                    final coluna = cIdx + 1;
                    final posKey = '$rackId-$face-C$coluna-N$nivel';
                    final palete = paletesMap[posKey];
                    return _CelulaWidget(posKey: posKey, palete: palete);
                  }),
                ],
              ),
            );
          }),
          // Eixo das colunas
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 24),
            child: Row(
              children: List.generate(AppConstants.numColunas, (i) => Expanded(
                child: Text(
                  'C${i + 1}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 7, color: AppColors.textDisabled),
                ),
              )),
            ),
          ),
        ],
      ),
    );
  }

  Widget _legendItem(Color color, String label) {
    return Row(children: [
      Container(width: 14, height: 14, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
      const SizedBox(width: 4),
      Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
    ]);
  }
}

class _CelulaWidget extends StatelessWidget {
  final String posKey;
  final MapaPosicao? palete;

  const _CelulaWidget({required this.posKey, this.palete});

  @override
  Widget build(BuildContext context) {
    final isOcupada = palete != null;
    final color = isOcupada ? palete!.cor : null;

    return Expanded(
      child: GestureDetector(
        onTap: isOcupada ? () => _showDetails(context, palete!) : null,
        child: Container(
          margin: const EdgeInsets.all(1),
          height: 32,
          decoration: BoxDecoration(
            color: isOcupada
                ? color!.withOpacity(0.35)
                : AppColors.surfaceBorder.withOpacity(0.3),
            borderRadius: BorderRadius.circular(3),
            border: Border.all(
              color: isOcupada ? color!.withOpacity(0.7) : AppColors.surfaceBorder,
              width: 0.5,
            ),
          ),
        ),
      ),
    );
  }

  void _showDetails(BuildContext context, MapaPosicao p) {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(p.produto ?? 'Produto', style: const TextStyle(fontFamily: 'Outfit', fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
            const SizedBox(height: 8),
            Text('Posição: ${p.posKey}', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 12, color: AppColors.textMuted)),
            if (p.quantidade != null) Text('Quantidade: ${p.quantidade} ${p.unidade ?? ''}', style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
            if (p.atualizado != null) Text('Atualizado: ${p.atualizado}', style: const TextStyle(fontSize: 11, color: AppColors.textDisabled)),
          ],
        ),
      ),
    );
  }
}

class _PosicaoCard extends StatelessWidget {
  final MapaPosicao posicao;

  const _PosicaoCard({required this.posicao});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: posicao.cor.withOpacity(0.3)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 44, height: 44,
            decoration: BoxDecoration(color: posicao.cor.withOpacity(0.2), borderRadius: BorderRadius.circular(10)),
            child: Icon(Icons.inventory_2_outlined, color: posicao.cor, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(posicao.produto ?? '', style: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 2, overflow: TextOverflow.ellipsis),
              Text(posicao.posKey, style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 11, color: AppColors.textMuted)),
            ]),
          ),
          if (posicao.quantidade != null)
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('${posicao.quantidade}', style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
              Text(posicao.unidade ?? '', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
            ]),
        ],
      ),
    );
  }
}
