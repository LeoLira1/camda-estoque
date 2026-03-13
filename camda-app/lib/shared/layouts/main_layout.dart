import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../features/estoque/estoque_screen.dart';
import '../../features/avarias/avarias_screen.dart';
import '../../features/validade/validade_screen.dart';
import '../../features/reposicao/reposicao_screen.dart';
import '../../features/vendas/vendas_screen.dart';
import '../../features/mapa_visual/mapa_screen.dart';
import '../../features/dashboard/dashboard_screen.dart';
import '../../features/lancamentos/lancamentos_screen.dart';
import '../../features/contagem/contagem_screen.dart';
import '../../features/pendencias/pendencias_screen.dart';
import '../../features/principios_ativos/principios_ativos_screen.dart';

/// Layout principal com navegação adaptativa:
/// - Mobile (< 600px): BottomNavigationBar (4 fixas + "Mais")
/// - Tablet/Desktop (>= 600px): NavigationRail lateral com todas as telas
class MainLayout extends StatefulWidget {
  const MainLayout({super.key});

  @override
  State<MainLayout> createState() => _MainLayoutState();
}

class _MainLayoutState extends State<MainLayout> {
  int _selectedIndex = 0;

  static const _allScreens = [
    DashboardScreen(),
    EstoqueScreen(),
    MapaScreen(),
    AvariasScreen(),
    ValidadeScreen(),
    ReposicaoScreen(),
    VendasScreen(),
    LancamentosScreen(),
    ContagemScreen(),
    PendenciasScreen(),
    PrincipiosAtivosScreen(),
  ];

  static const _allItems = [
    _NavItem(icon: Icons.dashboard_outlined,      activeIcon: Icons.dashboard,      label: 'Dashboard'),
    _NavItem(icon: Icons.inventory_2_outlined,    activeIcon: Icons.inventory_2,    label: 'Estoque'),
    _NavItem(icon: Icons.map_outlined,            activeIcon: Icons.map,            label: 'Mapa'),
    _NavItem(icon: Icons.warning_amber_outlined,  activeIcon: Icons.warning_amber,  label: 'Avarias'),
    _NavItem(icon: Icons.event_outlined,          activeIcon: Icons.event,          label: 'Validade'),
    _NavItem(icon: Icons.store_outlined,          activeIcon: Icons.store,          label: 'Reposição'),
    _NavItem(icon: Icons.bar_chart_outlined,      activeIcon: Icons.bar_chart,      label: 'Vendas'),
    _NavItem(icon: Icons.receipt_long_outlined,   activeIcon: Icons.receipt_long,   label: 'Lançamentos'),
    _NavItem(icon: Icons.fact_check_outlined,     activeIcon: Icons.fact_check,     label: 'Contagem'),
    _NavItem(icon: Icons.photo_library_outlined,  activeIcon: Icons.photo_library,  label: 'Pendências'),
    _NavItem(icon: Icons.science_outlined,        activeIcon: Icons.science,        label: 'P. Ativos'),
  ];

  // Índices que aparecem diretamente no BottomNav (mobile)
  static const _bottomIndices = [0, 1, 2, 3];

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    if (width >= 600) {
      return _WideLayout(
        selectedIndex: _selectedIndex,
        onSelect: (i) => setState(() => _selectedIndex = i),
        items: _allItems,
        screens: _allScreens,
      );
    }
    return _MobileLayout(
      selectedIndex: _selectedIndex,
      onSelect: (i) => setState(() => _selectedIndex = i),
      items: _allItems,
      screens: _allScreens,
      bottomIndices: _bottomIndices,
    );
  }
}

// ── Mobile ────────────────────────────────────────────────────────────────────

class _MobileLayout extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onSelect;
  final List<_NavItem> items;
  final List<Widget> screens;
  final List<int> bottomIndices;

  const _MobileLayout({
    required this.selectedIndex,
    required this.onSelect,
    required this.items,
    required this.screens,
    required this.bottomIndices,
  });

  int get _bottomSel {
    final idx = bottomIndices.indexOf(selectedIndex);
    // "Mais" tab = último índice
    return idx >= 0 ? idx : bottomIndices.length;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: IndexedStack(index: selectedIndex, children: screens),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          border: Border(top: BorderSide(color: AppColors.surfaceBorder)),
        ),
        child: NavigationBar(
          selectedIndex: _bottomSel.clamp(0, bottomIndices.length),
          onDestinationSelected: (i) {
            if (i < bottomIndices.length) {
              onSelect(bottomIndices[i]);
            } else {
              _openMais(context);
            }
          },
          backgroundColor: Colors.transparent,
          elevation: 0,
          height: 64,
          labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
          destinations: [
            ...bottomIndices.map((i) => NavigationDestination(
              icon: Icon(items[i].icon),
              selectedIcon: Icon(items[i].activeIcon),
              label: items[i].label,
            )),
            const NavigationDestination(
              icon: Icon(Icons.grid_view_outlined),
              selectedIcon: Icon(Icons.grid_view),
              label: 'Mais',
            ),
          ],
        ),
      ),
    );
  }

  void _openMais(BuildContext context) {
    final secondary = [for (int i = 0; i < items.length; i++) if (!bottomIndices.contains(i)) i];
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 12),
          Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2))),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            child: Row(children: [
              const Text('Mais', style: TextStyle(fontFamily: 'Outfit', fontSize: 16, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
            ]),
          ),
          const Divider(height: 1),
          ...secondary.map((i) => ListTile(
            leading: Icon(
              selectedIndex == i ? items[i].activeIcon : items[i].icon,
              color: selectedIndex == i ? AppColors.green : AppColors.textMuted,
              size: 22,
            ),
            title: Text(
              items[i].label,
              style: TextStyle(
                fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w500,
                color: selectedIndex == i ? AppColors.green : AppColors.textPrimary,
              ),
            ),
            trailing: selectedIndex == i ? const Icon(Icons.check, color: AppColors.green, size: 18) : null,
            onTap: () { Navigator.pop(context); onSelect(i); },
          )),
          const SizedBox(height: 16),
        ],
      ),
    );
  }
}

// ── Wide (tablet/desktop) ─────────────────────────────────────────────────────

class _WideLayout extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onSelect;
  final List<_NavItem> items;
  final List<Widget> screens;

  const _WideLayout({
    required this.selectedIndex,
    required this.onSelect,
    required this.items,
    required this.screens,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Row(
        children: [
          Container(
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(right: BorderSide(color: AppColors.surfaceBorder)),
            ),
            child: SingleChildScrollView(
              child: IntrinsicHeight(
                child: NavigationRail(
                  selectedIndex: selectedIndex,
                  onDestinationSelected: onSelect,
                  backgroundColor: Colors.transparent,
                  labelType: NavigationRailLabelType.all,
                  minWidth: 72,
                  leading: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Container(
                      width: 36, height: 36,
                      decoration: BoxDecoration(
                        color: AppColors.green.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppColors.green.withOpacity(0.3)),
                      ),
                      child: const Icon(Icons.eco_outlined, color: AppColors.green, size: 20),
                    ),
                  ),
                  destinations: items.map((d) => NavigationRailDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.activeIcon),
                    label: Text(d.label, maxLines: 1, overflow: TextOverflow.ellipsis),
                    padding: const EdgeInsets.symmetric(vertical: 2),
                  )).toList(),
                ),
              ),
            ),
          ),
          Expanded(
            child: IndexedStack(index: selectedIndex, children: screens),
          ),
        ],
      ),
    );
  }
}

class _NavItem {
  final IconData icon;
  final IconData activeIcon;
  final String label;
  const _NavItem({required this.icon, required this.activeIcon, required this.label});
}
