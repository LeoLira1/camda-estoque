import 'dart:ui';
import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';

/// Card com efeito glassmorphism — fiel ao visual do dashboard CAMDA.
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double borderRadius;
  final double backgroundOpacity;
  final double borderOpacity;
  final double blurSigma;
  final Color? backgroundColor;
  final Color? borderColor;
  final VoidCallback? onTap;
  final double? width;
  final double? height;
  final Gradient? gradient;
  /// Desativa o BackdropFilter blur. Use false em listas roláveis para evitar
  /// flicker no mobile (BackdropFilter cria camada de compositing por frame).
  final bool enableBlur;

  const GlassCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 14,
    this.backgroundOpacity = 0.06,
    this.borderOpacity = 0.10,
    this.blurSigma = 10,
    this.backgroundColor,
    this.borderColor,
    this.onTap,
    this.width,
    this.height,
    this.gradient,
    this.enableBlur = true,
  });

  @override
  Widget build(BuildContext context) {
    final bg = backgroundColor ?? Colors.white;
    final bd = borderColor ?? Colors.white;

    final container = Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        gradient: gradient,
        color: gradient == null ? bg.withOpacity(backgroundOpacity) : null,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(
          color: bd.withOpacity(borderOpacity),
          width: 1,
        ),
      ),
      padding: padding,
      child: child,
    );

    Widget card;
    if (enableBlur) {
      card = ClipRRect(
        borderRadius: BorderRadius.circular(borderRadius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blurSigma, sigmaY: blurSigma),
          child: container,
        ),
      );
    } else {
      card = container;
    }

    if (onTap != null) {
      card = GestureDetector(onTap: onTap, child: card);
    }

    return card;
  }
}

/// Card sólido estilo CAMDA (sem blur, mas com bordas glassmorphism).
class SolidCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double borderRadius;
  final Gradient? gradient;
  final Color? color;
  final VoidCallback? onTap;
  final double? width;
  final double? height;

  const SolidCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderRadius = 12,
    this.gradient,
    this.color,
    this.onTap,
    this.width,
    this.height,
  });

  @override
  Widget build(BuildContext context) {
    Widget card = Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        gradient: gradient ?? AppColors.surfaceGradient,
        color: gradient == null && color != null ? color : null,
        borderRadius: BorderRadius.circular(borderRadius),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      padding: padding,
      child: child,
    );

    if (onTap != null) {
      card = GestureDetector(
        onTap: onTap,
        child: AnimatedScale(
          scale: 1.0,
          duration: const Duration(milliseconds: 150),
          child: card,
        ),
      );
    }

    return card;
  }
}
