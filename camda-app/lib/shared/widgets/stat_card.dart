import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import 'glass_card.dart';

/// Card de KPI/estatística — réplica dos `.stat-card` do dashboard CAMDA.
class StatCard extends StatelessWidget {
  final String value;
  final String label;
  final Color valueColor;
  final IconData? icon;
  final VoidCallback? onTap;

  const StatCard({
    super.key,
    required this.value,
    required this.label,
    this.valueColor = AppColors.green,
    this.icon,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: SolidCard(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, color: valueColor, size: 16),
              const SizedBox(height: 4),
            ],
            Text(
              value,
              style: TextStyle(
                fontFamily: 'JetBrainsMono',
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: valueColor,
                letterSpacing: -0.5,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 3),
            Text(
              label.toUpperCase(),
              style: const TextStyle(
                fontSize: 9,
                color: AppColors.textMuted,
                letterSpacing: 1,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ),
      ),
    );
  }
}

/// Linha de stat cards.
class StatCardRow extends StatelessWidget {
  final List<StatCard> cards;

  const StatCardRow({super.key, required this.cards});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: cards
          .map((c) => Expanded(child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 3),
                child: c,
              )))
          .toList(),
    );
  }
}

/// Badge de status colorido (ok / falta / sobra / avaria).
class StatusBadge extends StatelessWidget {
  final String status;
  final bool compact;

  const StatusBadge({super.key, required this.status, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.statusColor(status);
    final label = compact ? _shortLabel(status) : status.toUpperCase();

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 6 : 8,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: compact ? 9 : 11,
          fontWeight: FontWeight.w700,
          color: color,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  String _shortLabel(String s) {
    switch (s.toLowerCase()) {
      case 'ok':
        return 'OK';
      case 'falta':
        return 'F';
      case 'sobra':
        return 'S';
      default:
        return s.substring(0, 1).toUpperCase();
    }
  }
}
