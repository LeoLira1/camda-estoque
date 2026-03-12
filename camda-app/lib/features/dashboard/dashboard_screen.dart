import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../core/utils/number_utils.dart';
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

  @override
  void initState() {
    super.initState();
    _loadData();
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
        ],
      ),
    ).animate().fadeIn(duration: 400.ms).slideY(begin: -0.1, end: 0);
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
