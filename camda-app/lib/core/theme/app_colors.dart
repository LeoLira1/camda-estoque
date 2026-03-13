import 'package:flutter/material.dart';

/// Paleta de cores fiel ao dashboard CAMDA (Streamlit dark glassmorphism theme).
class AppColors {
  AppColors._();

  // ── Background ─────────────────────────────────────────────────────────────
  static const Color background = Color(0xFF0A0F1A);
  static const Color surface = Color(0xFF111827);
  static const Color surfaceVariant = Color(0xFF1A2332);
  static const Color surfaceBorder = Color(0xFF1E293B);

  // ── Glassmorphism ──────────────────────────────────────────────────────────
  static const Color glassBackground = Color(0x0AFFFFFF); // rgba(255,255,255,0.04)
  static const Color glassBorder = Color(0x14FFFFFF);     // rgba(255,255,255,0.08)
  static const Color glassBackgroundSelected = Color(0x29FFFFFF);
  static const Color glassBorderSelected = Color(0x597BAFD4);

  // ── Accent / Status ────────────────────────────────────────────────────────
  static const Color green = Color(0xFF00D68F);      // #00d68f — primário verde
  static const Color greenDark = Color(0xFF00B887);
  static const Color blue = Color(0xFF3B82F6);       // #3b82f6
  static const Color red = Color(0xFFFF4757);        // #ff4757
  static const Color amber = Color(0xFFFFA502);      // #ffa502
  static const Color purple = Color(0xFFA55EEA);     // #a55eea
  static const Color cyan = Color(0xFF00C4FF);       // #00c4ff

  // ── Text ───────────────────────────────────────────────────────────────────
  static const Color textPrimary = Color(0xFFE0E6ED);
  static const Color textSecondary = Color(0xFF7BAFD4);
  static const Color textMuted = Color(0xFF64748B);
  static const Color textDisabled = Color(0xFF4A5568);

  // ── Status colors ──────────────────────────────────────────────────────────
  static const Color statusOk = green;
  static const Color statusFalta = red;
  static const Color statusSobra = amber;
  static const Color statusAvaria = Color(0xFFFF6B7A);

  // ── Gradients ──────────────────────────────────────────────────────────────
  static const LinearGradient greenGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [green, greenDark],
  );

  static const LinearGradient surfaceGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [surface, surfaceVariant],
  );

  static const LinearGradient blueGreenGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF00E5A0), Color(0xFF00C4FF)],
  );

  // ── Chip / Card helpers ────────────────────────────────────────────────────
  static Color statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'ok':
        return green;
      case 'falta':
        return red;
      case 'sobra':
        return amber;
      case 'avaria':
        return statusAvaria;
      default:
        return textMuted;
    }
  }
}
