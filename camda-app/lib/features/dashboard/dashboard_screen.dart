import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../core/utils/number_utils.dart';
import '../../data/models/produto.dart';
import '../../data/models/avaria.dart';
import '../../data/repositories/estoque_repository.dart';
import '../../data/repositories/avarias_repository.dart';
import '../../data/repositories/reposicao_repository.dart';
import '../../data/repositories/validade_repository.dart';
import '../../shared/widgets/stat_card.dart';
import '../../shared/widgets/glass_card.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _estoqueRepo = EstoqueRepository();
  final _avariasRepo = AvariasRepository();
  final _reposicaoRepo = ReposicaoRepository();
  final _validadeRepo = ValidadeRepository();

  EstoqueResumo? _estoqueResumo;
  ValidadeResumo? _validadeResumo;
  int _avariasAbertas = 0;
  int _reposicaoPendente = 0;
  bool _loading = true;
  String? _error;

  // Busca por palavra-chave no dashboard
  final _searchCtrl = TextEditingController();
  List<Produto> _produtosResultado = [];
  List<Avaria> _avariasResultado = [];
  String? _activeKeyword;
  bool _searchLoading = false;

  @override
  void initState() {
    super.initState();
    _loadData();
    _searchCtrl.addListener(_onSearchChanged);
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  String? _detectKeyword(String query) {
    if (query == 'falta' || query == 'faltando') return 'falta';
    if (query == 'sobra' || query == 'sobrando') return 'sobra';
    if (query == 'avaria' || query == 'avarias') return 'avaria';
    return null;
  }

  Future<void> _onSearchChanged() async {
    final query = _searchCtrl.text.trim().toLowerCase();
    final keyword = _detectKeyword(query);

    if (keyword == null) {
      setState(() { _activeKeyword = null; _produtosResultado = []; _avariasResultado = []; });
      return;
    }
    if (keyword == _activeKeyword) return;

    setState(() { _searchLoading = true; _activeKeyword = keyword; });

    try {
      if (keyword == 'avaria') {
        final av = await _avariasRepo.getAll(apenasAbertas: true);
        if (mounted) setState(() { _avariasResultado = av; _produtosResultado = []; _searchLoading = false; });
      } else {
        final pr = await _estoqueRepo.getAll(status: keyword);
        if (mounted) setState(() { _produtosResultado = pr; _avariasResultado = []; _searchLoading = false; });
      }
    } catch (_) {
      if (mounted) setState(() { _searchLoading = false; });
    }
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final results = await Future.wait([
        _estoqueRepo.getResumo(),
        _avariasRepo.countAbertas(),
        _reposicaoRepo.countPendentes(),
        _validadeRepo.getResumo(),
      ]);
      if (!mounted) return;
      setState(() {
        _estoqueResumo = results[0] as EstoqueResumo;
        _avariasAbertas = results[1] as int;
        _reposicaoPendente = results[2] as int;
        _validadeResumo = results[3] as ValidadeResumo;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: RefreshIndicator(
          color: AppColors.green,
          backgroundColor: AppColors.surface,
          onRefresh: _loadData,
          child: CustomScrollView(
            slivers: [
              SliverToBoxAdapter(child: _buildHeader()),
              if (_loading)
                const SliverFillRemaining(
                  child: lw.LoadingWidget(message: 'Carregando dados...'),
                )
              else if (_error != null)
                SliverFillRemaining(
                  child: lw.ErrorWidget(message: _error!, onRetry: _loadData),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 24),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      _buildStatCards(),
                      if (_activeKeyword != null) ...[
                        const SizedBox(height: 16),
                        _buildKeywordResults(),
                      ],
                      const SizedBox(height: 16),
                      _buildValidadeAlerts(),
                      const SizedBox(height: 16),
                      _buildRecentActivity(),
                    ]),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final now = CamdaDateUtils.nowBRT();
    final hora = CamdaDateUtils.formatTime(now);
    final diaNome = CamdaDateUtils.diaSemanaFull(now);
    final data = CamdaDateUtils.formatDate(now);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              ShaderMask(
                shaderCallback: (bounds) =>
                    AppColors.greenGradient.createShader(bounds),
                child: const Text(
                  'CAMDA Estoque',
                  style: TextStyle(
                    fontFamily: 'Outfit',
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ),
              const Spacer(),
              IconButton(
                onPressed: _loadData,
                icon: const Icon(Icons.refresh, color: AppColors.textMuted, size: 20),
                tooltip: 'Atualizar',
              ),
            ],
          ),
          Text(
            '$diaNome · $data · $hora',
            style: const TextStyle(
              fontFamily: 'JetBrainsMono',
              fontSize: 11,
              color: AppColors.textDisabled,
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _searchCtrl,
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
            decoration: InputDecoration(
              hintText: 'Digite: falta, sobra, avaria...',
              prefixIcon: const Icon(Icons.search, color: AppColors.textMuted, size: 18),
              suffixIcon: _searchCtrl.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear, color: AppColors.textMuted, size: 16),
                      onPressed: _searchCtrl.clear,
                    )
                  : null,
              isDense: true,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1, end: 0);
  }

  Widget _buildKeywordResults() {
    final (label, color, icon) = switch (_activeKeyword) {
      'falta'  => ('Produtos Faltando', AppColors.red, Icons.remove_circle_outline),
      'sobra'  => ('Produtos Sobrando', AppColors.amber, Icons.add_circle_outline),
      'avaria' => ('Avarias em Aberto', AppColors.statusAvaria, Icons.warning_amber_outlined),
      _        => ('Resultado', AppColors.blue, Icons.info_outline),
    };

    final isEmpty = _produtosResultado.isEmpty && _avariasResultado.isEmpty;

    return GlassCard(
      borderRadius: 14,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
              const Spacer(),
              if (_searchLoading)
                const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
              else
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${_activeKeyword == 'avaria' ? _avariasResultado.length : _produtosResultado.length} item(s)',
                    style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ),
          if (!_searchLoading) ...[
            const SizedBox(height: 10),
            if (isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Nenhum item encontrado.',
                  style: const TextStyle(fontSize: 13, color: AppColors.textMuted),
                ),
              )
            else if (_activeKeyword == 'avaria')
              ...(_avariasResultado.take(20).map((a) => _avariaRow(a, color)))
            else
              ...(_produtosResultado.take(20).map((p) => _produtoRow(p, color))),
            if ((_activeKeyword == 'avaria' ? _avariasResultado.length : _produtosResultado.length) > 20)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '+ mais itens. Acesse a tela de Estoque para ver todos.',
                  style: const TextStyle(fontSize: 11, color: AppColors.textDisabled, fontStyle: FontStyle.italic),
                ),
              ),
          ],
        ],
      ),
    ).animate().fadeIn(duration: 300.ms);
  }

  Widget _produtoRow(Produto p, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Container(
            width: 34, height: 34,
            decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
            child: Icon(Icons.inventory_2_outlined, color: color, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(p.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                Text('Cód: ${p.codigo}  ·  ${p.categoria}', style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(CamdaNumberUtils.formatInt(p.qtdSistema), style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: color)),
              if (p.temDivergencia)
                Text(CamdaNumberUtils.formatDiff(p.diferenca), style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, color: color.withOpacity(0.7))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _avariaRow(Avaria a, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Container(
            width: 34, height: 34,
            decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(8)),
            child: Icon(Icons.warning_amber_outlined, color: color, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(a.produto, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                Text(a.motivo.isNotEmpty ? a.motivo : 'Sem descrição', style: const TextStyle(fontSize: 10, color: AppColors.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text('${a.qtdAvariada}', style: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 15, fontWeight: FontWeight.w700, color: color)),
              const Text('avariado(s)', style: TextStyle(fontSize: 9, color: AppColors.textMuted)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatCards() {
    final resumo = _estoqueResumo;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            'Estoque',
            style: TextStyle(
              fontFamily: 'Outfit',
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppColors.textMuted,
              letterSpacing: 0.5,
            ),
          ),
        ),
        StatCardRow(cards: [
          StatCard(
            value: CamdaNumberUtils.formatInt(resumo?.total),
            label: 'Produtos',
            valueColor: AppColors.green,
          ),
          StatCard(
            value: CamdaNumberUtils.formatInt(resumo?.faltas),
            label: 'Faltas',
            valueColor: AppColors.red,
          ),
          StatCard(
            value: CamdaNumberUtils.formatInt(resumo?.sobras),
            label: 'Sobras',
            valueColor: AppColors.amber,
          ),
        ]),
        const SizedBox(height: 8),
        StatCardRow(cards: [
          StatCard(
            value: CamdaNumberUtils.formatInt(_avariasAbertas),
            label: 'Avarias',
            valueColor: AppColors.statusAvaria,
          ),
          StatCard(
            value: CamdaNumberUtils.formatInt(_reposicaoPendente),
            label: 'Repor Loja',
            valueColor: AppColors.blue,
          ),
          StatCard(
            value: CamdaNumberUtils.formatInt(_validadeResumo?.vencidos),
            label: 'Vencidos',
            valueColor: AppColors.red,
          ),
        ]),
      ],
    ).animate().fadeIn(duration: 500.ms, delay: 100.ms);
  }

  Widget _buildValidadeAlerts() {
    final resumo = _validadeResumo;
    if (resumo == null) return const SizedBox.shrink();

    final temAlertas = (resumo.vencidos + resumo.criticos + resumo.alertas) > 0;
    if (!temAlertas) return const SizedBox.shrink();

    return GlassCard(
      borderRadius: 14,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.event_busy_outlined, color: AppColors.amber, size: 18),
              const SizedBox(width: 8),
              const Text(
                'Alertas de Validade',
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(children: [
            _alertChip('Vencidos', resumo.vencidos, AppColors.red),
            const SizedBox(width: 8),
            _alertChip('Críticos (≤7d)', resumo.criticos, AppColors.statusAvaria),
            const SizedBox(width: 8),
            _alertChip('Alertas (≤30d)', resumo.alertas, AppColors.amber),
          ]),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _alertChip(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(
          children: [
            Text(
              count.toString(),
              style: TextStyle(
                fontFamily: 'JetBrainsMono',
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
            Text(
              label,
              style: const TextStyle(fontSize: 9, color: AppColors.textMuted),
              textAlign: TextAlign.center,
              maxLines: 2,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentActivity() {
    return GlassCard(
      borderRadius: 14,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.access_time_outlined, color: AppColors.blue, size: 18),
              SizedBox(width: 8),
              Text(
                'Atividade Recente',
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _activityItem(Icons.inventory_2_outlined, 'Estoque sincronizado com Turso', AppColors.green),
          _activityItem(Icons.warning_amber_outlined, 'Avarias aguardando resolução: $_avariasAbertas', AppColors.red),
          _activityItem(Icons.store_outlined, 'Itens para repor na loja: $_reposicaoPendente', AppColors.blue),
        ],
      ),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _activityItem(IconData icon, String text, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
