import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';

/// Notifier global para alternar entre modo escuro e claro.
final themeNotifier = ValueNotifier<ThemeMode>(ThemeMode.dark);

class AppTheme {
  AppTheme._();

  static ThemeData get darkTheme => _build(Brightness.dark);
  static ThemeData get lightTheme => _build(Brightness.light);

  static ThemeData _build(Brightness brightness) {
    final isDark = brightness == Brightness.dark;

    // ── Paleta base ────────────────────────────────────────────────────────────
    final bgColor       = isDark ? const Color(0xFF0A0F1A) : const Color(0xFFF0F4F8);
    final surfaceColor  = isDark ? const Color(0xFF111827) : const Color(0xFFFFFFFF);
    final surfaceVarClr = isDark ? const Color(0xFF1A2332) : const Color(0xFFE8F0F7);
    final borderColor   = isDark ? const Color(0xFF1E293B) : const Color(0xFFCBD5E1);
    final onSurface     = isDark ? const Color(0xFFE0E6ED) : const Color(0xFF0A1628);
    final onSurfaceVar  = isDark ? const Color(0xFF7BAFD4) : const Color(0xFF3A6291);
    final mutedColor    = isDark ? const Color(0xFF64748B) : const Color(0xFF8A9BB0);

    final textTheme = TextTheme(
      displayLarge: TextStyle(fontFamily: 'Outfit', fontSize: 32, fontWeight: FontWeight.w900, color: onSurface, letterSpacing: -1),
      displayMedium: TextStyle(fontFamily: 'Outfit', fontSize: 24, fontWeight: FontWeight.w700, color: onSurface),
      headlineLarge: TextStyle(fontFamily: 'Outfit', fontSize: 20, fontWeight: FontWeight.w700, color: onSurface),
      headlineMedium: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w600, color: onSurface),
      titleLarge: TextStyle(fontFamily: 'Outfit', fontSize: 16, fontWeight: FontWeight.w600, color: onSurface),
      titleMedium: TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w500, color: onSurface),
      bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: onSurface),
      bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w400, color: onSurfaceVar),
      bodySmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: mutedColor),
      labelLarge: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 14, fontWeight: FontWeight.w700, color: AppColors.green, letterSpacing: 0.5),
      labelMedium: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 12, fontWeight: FontWeight.w400, color: mutedColor),
      labelSmall: TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, fontWeight: FontWeight.w400, color: mutedColor, letterSpacing: 1),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: (isDark ? const ColorScheme.dark() : const ColorScheme.light()).copyWith(
        primary: AppColors.green,
        onPrimary: isDark ? const Color(0xFF0A0F1A) : Colors.white,
        secondary: AppColors.blue,
        onSecondary: Colors.white,
        tertiary: AppColors.purple,
        onTertiary: Colors.white,
        error: AppColors.red,
        onError: Colors.white,
        surface: surfaceColor,
        onSurface: onSurface,
        onSurfaceVariant: onSurfaceVar,
        outline: borderColor,
        outlineVariant: borderColor.withOpacity(0.5),
      ),
      scaffoldBackgroundColor: bgColor,
      textTheme: textTheme,
      fontFamily: 'Outfit',

      // AppBar
      appBarTheme: AppBarTheme(
        backgroundColor: bgColor,
        foregroundColor: onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        systemOverlayStyle: isDark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
        centerTitle: false,
        titleTextStyle: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: onSurface),
      ),

      // NavigationBar (bottom)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surfaceColor,
        indicatorColor: AppColors.green.withOpacity(0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.green, size: 24);
          }
          return IconThemeData(color: mutedColor, size: 22);
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(fontFamily: 'Outfit', fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.green);
          }
          return TextStyle(fontFamily: 'Outfit', fontSize: 11, color: mutedColor);
        }),
        elevation: 8,
        shadowColor: Colors.black54,
      ),

      // NavigationRail (tablet/desktop)
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: surfaceColor,
        selectedIconTheme: const IconThemeData(color: AppColors.green, size: 24),
        unselectedIconTheme: IconThemeData(color: mutedColor, size: 22),
        selectedLabelTextStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.green),
        unselectedLabelTextStyle: TextStyle(fontFamily: 'Outfit', fontSize: 12, color: mutedColor),
        indicatorColor: AppColors.green.withOpacity(0.15),
      ),

      // Card
      cardTheme: CardTheme(
        color: surfaceColor,
        elevation: isDark ? 0 : 2,
        shadowColor: isDark ? null : Colors.black12,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: borderColor),
        ),
        margin: EdgeInsets.zero,
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: isDark ? const Color(0x0AFFFFFF) : const Color(0xFFF0F4F8),
        selectedColor: AppColors.green.withOpacity(0.2),
        labelStyle: TextStyle(fontSize: 12, color: onSurfaceVar),
        side: BorderSide(color: isDark ? const Color(0x14FFFFFF) : borderColor),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),

      // Input decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: isDark ? const Color(0x0AFFFFFF) : const Color(0xFFF8FAFC),
        hintStyle: TextStyle(color: mutedColor, fontSize: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: borderColor),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: borderColor),
        ),
        focusedBorder: const OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          borderSide: BorderSide(color: AppColors.green, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),

      // ElevatedButton
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green,
          foregroundColor: isDark ? const Color(0xFF0A0F1A) : Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
          textStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 15, fontWeight: FontWeight.w700, letterSpacing: 1),
        ),
      ),

      // Divider
      dividerTheme: DividerThemeData(color: borderColor, thickness: 1, space: 1),

      // SnackBar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: surfaceColor,
        contentTextStyle: TextStyle(color: onSurface),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        behavior: SnackBarBehavior.floating,
      ),

      // TabBar
      tabBarTheme: TabBarTheme(
        labelColor: onSurface,
        unselectedLabelColor: mutedColor,
        indicator: BoxDecoration(
          color: isDark ? const Color(0x29FFFFFF) : const Color(0xFFE2F4EC),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: isDark ? const Color(0x597BAFD4) : AppColors.green.withOpacity(0.4)),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 13, fontWeight: FontWeight.w500),
        dividerColor: Colors.transparent,
      ),

      // Dialog
      dialogTheme: DialogTheme(
        backgroundColor: surfaceColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: BorderSide(color: isDark ? const Color(0x14FFFFFF) : borderColor),
        ),
        titleTextStyle: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: onSurface),
        contentTextStyle: TextStyle(fontSize: 14, color: onSurfaceVar),
      ),

      // ProgressIndicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.green),
    );
  }
}
