import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get darkTheme {
    const textTheme = TextTheme(
      // Titles — Outfit
      displayLarge: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 32,
        fontWeight: FontWeight.w900,
        color: AppColors.textPrimary,
        letterSpacing: -1,
      ),
      displayMedium: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 24,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
      ),
      headlineLarge: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
      ),
      headlineMedium: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      ),
      titleLarge: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: AppColors.textPrimary,
      ),
      titleMedium: TextStyle(
        fontFamily: 'Outfit',
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: AppColors.textPrimary,
      ),
      // Body — DM Sans fallback via system
      bodyLarge: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      ),
      bodyMedium: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
      ),
      bodySmall: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: AppColors.textMuted,
      ),
      // Monospace — JetBrains Mono
      labelLarge: TextStyle(
        fontFamily: 'JetBrainsMono',
        fontSize: 14,
        fontWeight: FontWeight.w700,
        color: AppColors.green,
        letterSpacing: 0.5,
      ),
      labelMedium: TextStyle(
        fontFamily: 'JetBrainsMono',
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: AppColors.textMuted,
      ),
      labelSmall: TextStyle(
        fontFamily: 'JetBrainsMono',
        fontSize: 10,
        fontWeight: FontWeight.w400,
        color: AppColors.textDisabled,
        letterSpacing: 1,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary: AppColors.green,
        secondary: AppColors.blue,
        tertiary: AppColors.purple,
        error: AppColors.red,
        surface: AppColors.surface,
        onSurface: AppColors.textPrimary,
        outline: AppColors.surfaceBorder,
      ),
      scaffoldBackgroundColor: AppColors.background,
      textTheme: textTheme,
      fontFamily: 'Outfit',

      // AppBar
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        scrolledUnderElevation: 0,
        systemOverlayStyle: SystemUiOverlayStyle.light,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: 'Outfit',
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: AppColors.textPrimary,
        ),
      ),

      // NavigationBar (bottom)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.green.withOpacity(0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.green, size: 24);
          }
          return const IconThemeData(color: AppColors.textMuted, size: 22);
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontFamily: 'Outfit',
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppColors.green,
            );
          }
          return const TextStyle(
            fontFamily: 'Outfit',
            fontSize: 11,
            color: AppColors.textMuted,
          );
        }),
        elevation: 8,
        shadowColor: Colors.black54,
      ),

      // NavigationRail (tablet/desktop)
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: AppColors.surface,
        selectedIconTheme: const IconThemeData(color: AppColors.green, size: 24),
        unselectedIconTheme: const IconThemeData(color: AppColors.textMuted, size: 22),
        selectedLabelTextStyle: const TextStyle(
          fontFamily: 'Outfit',
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: AppColors.green,
        ),
        unselectedLabelTextStyle: const TextStyle(
          fontFamily: 'Outfit',
          fontSize: 12,
          color: AppColors.textMuted,
        ),
        indicatorColor: AppColors.green.withOpacity(0.15),
      ),

      // Card
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: AppColors.surfaceBorder),
        ),
        margin: EdgeInsets.zero,
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.glassBackground,
        selectedColor: AppColors.green.withOpacity(0.2),
        labelStyle: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
        side: const BorderSide(color: AppColors.glassBorder),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),

      // Input decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.glassBackground,
        hintStyle: const TextStyle(color: AppColors.textDisabled, fontSize: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.glassBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.glassBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.green, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),

      // ElevatedButton
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green,
          foregroundColor: AppColors.background,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
          textStyle: const TextStyle(
            fontFamily: 'Outfit',
            fontSize: 15,
            fontWeight: FontWeight.w700,
            letterSpacing: 1,
          ),
        ),
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: AppColors.surfaceBorder,
        thickness: 1,
        space: 1,
      ),

      // SnackBar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.surface,
        contentTextStyle: const TextStyle(color: AppColors.textPrimary),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        behavior: SnackBarBehavior.floating,
      ),

      // TabBar
      tabBarTheme: TabBarThemeData(
        labelColor: AppColors.textPrimary,
        unselectedLabelColor: AppColors.textMuted,
        indicator: BoxDecoration(
          color: AppColors.glassBackgroundSelected,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.glassBorderSelected),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelStyle: const TextStyle(
          fontFamily: 'Outfit',
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: const TextStyle(
          fontFamily: 'Outfit',
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
        dividerColor: Colors.transparent,
      ),

      // Dialog
      dialogTheme: DialogThemeData(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: AppColors.glassBorder),
        ),
        titleTextStyle: const TextStyle(
          fontFamily: 'Outfit',
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: AppColors.textPrimary,
        ),
        contentTextStyle: const TextStyle(
          fontSize: 14,
          color: AppColors.textSecondary,
        ),
      ),

      // ProgressIndicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.green,
      ),
    );
  }

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.light(
        primary: AppColors.green,
        secondary: AppColors.blue,
        error: AppColors.red,
        surface: const Color(0xFFF5F7FA),
        onSurface: const Color(0xFF1A202C),
      ),
      scaffoldBackgroundColor: const Color(0xFFF0F4F8),
      fontFamily: 'Outfit',
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xFFF0F4F8),
        foregroundColor: Color(0xFF1A202C),
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          fontFamily: 'Outfit',
          fontSize: 18,
          fontWeight: FontWeight.w700,
          color: Color(0xFF1A202C),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: AppColors.green.withOpacity(0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: AppColors.green, size: 24);
          }
          return const IconThemeData(color: Color(0xFF64748B), size: 22);
        }),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: Colors.white,
        selectedIconTheme: const IconThemeData(color: AppColors.green, size: 24),
        unselectedIconTheme: const IconThemeData(color: Color(0xFF64748B), size: 22),
        indicatorColor: AppColors.green.withOpacity(0.15),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: Color(0xFFE2E8F0)),
        ),
        margin: EdgeInsets.zero,
      ),
      chipTheme: ChipThemeData(
        backgroundColor: const Color(0xFFEFF2F7),
        side: const BorderSide(color: Color(0xFFCBD5E0)),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFCBD5E0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFCBD5E0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.green, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.green,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
          textStyle: const TextStyle(fontFamily: 'Outfit', fontSize: 15, fontWeight: FontWeight.w700),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: AppColors.green),
    );
  }
}
