import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../../core/theme/app_colors.dart';
import '../../features/estoque/estoque_screen.dart';
import '../../features/avarias/avarias_screen.dart';
import '../../features/validade/validade_screen.dart';
import '../../features/reposicao/reposicao_screen.dart';
import '../../features/vendas/vendas_screen.dart';
import '../../features/mapa_visual/mapa_screen.dart';
import '../../features/dashboard/dashboard_screen.dart';

/// Layout principal do app com navegação adaptativa:
/// - Mobile/portrait: BottomNavigationBar
/// - Tablet/desktop (≥ 600px): NavigationRail lateral
class MainLayout extends StatefulWidget {
  const MainLayout({super.key});

  @override
  State<MainLayout> createState() => _MainLayoutState();
}

class _MainLayoutState extends State<MainLayout> {
  int _selectedIndex = 0;

  static const _destinations = [
    _NavItem(icon: Icons.dashboard_outlined, activeIcon: Icons.dashboard, label: 'Dashboard'),
    _NavItem(icon: Icons.inventory_2_outlined, activeIcon: Icons.inventory_2, label: 'Estoque'),
    _NavItem(icon: Icons.warning_amber_outlined, activeIcon: Icons.warning_amber, label: 'Avarias'),
    _NavItem(icon: Icons.event_outlined, activeIcon: Icons.event, label: 'Validade'),
    _NavItem(icon: Icons.store_outlined, activeIcon: Icons.store, label: 'Reposição'),
    _NavItem(icon: Icons.bar_chart_outlined, activeIcon: Icons.bar_chart, label: 'Vendas'),
    _NavItem(icon: Icons.map_outlined, activeIcon: Icons.map, label: 'Mapa'),
  ];

  static const _screens = [
    DashboardScreen(),
    EstoqueScreen(),
    AvariasScreen(),
    ValidadeScreen(),
    ReposicaoScreen(),
    VendasScreen(),
    MapaScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final isWide = width >= 600;

    if (isWide) {
      return _WideLayout(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        destinations: _destinations,
        screens: _screens,
      );
    }

    return _MobileLayout(
      selectedIndex: _selectedIndex,
      onDestinationSelected: (i) => setState(() => _selectedIndex = i),
      destinations: _destinations,
      screens: _screens,
    );
  }
}

// ── Mobile Layout ─────────────────────────────────────────────────────────────

class _MobileLayout extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final List<_NavItem> destinations;
  final List<Widget> screens;

  const _MobileLayout({
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.destinations,
    required this.screens,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: IndexedStack(
        index: selectedIndex,
        children: screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppColors.surface,
          border: Border(top: BorderSide(color: AppColors.surfaceBorder)),
        ),
        child: NavigationBar(
          selectedIndex: selectedIndex,
          onDestinationSelected: onDestinationSelected,
          backgroundColor: Colors.transparent,
          elevation: 0,
          height: 64,
          labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
          destinations: destinations
              .map((d) => NavigationDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.activeIcon),
                    label: d.label,
                  ))
              .toList(),
        ),
      ),
    );
  }
}

// ── Wide Layout (tablet/desktop) ──────────────────────────────────────────────

class _WideLayout extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;
  final List<_NavItem> destinations;
  final List<Widget> screens;

  const _WideLayout({
    required this.selectedIndex,
    required this.onDestinationSelected,
    required this.destinations,
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
            child: NavigationRail(
              selectedIndex: selectedIndex,
              onDestinationSelected: onDestinationSelected,
              backgroundColor: Colors.transparent,
              labelType: NavigationRailLabelType.all,
              minWidth: 72,
              destinations: destinations
                  .map((d) => NavigationRailDestination(
                        icon: Icon(d.icon),
                        selectedIcon: Icon(d.activeIcon),
                        label: Text(d.label),
                        padding: const EdgeInsets.symmetric(vertical: 4),
                      ))
                  .toList(),
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Column(
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: AppColors.green.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppColors.green.withOpacity(0.3)),
                      ),
                      child: const Icon(
                        Icons.eco_outlined,
                        color: AppColors.green,
                        size: 20,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: IndexedStack(
              index: selectedIndex,
              children: screens,
            ),
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

  const _NavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });
}
