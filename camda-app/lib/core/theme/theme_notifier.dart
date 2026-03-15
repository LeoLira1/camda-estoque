import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeNotifier extends ValueNotifier<ThemeMode> {
  static final ThemeNotifier _instance = ThemeNotifier._();
  static ThemeNotifier get instance => _instance;

  static const _key = 'theme_mode';

  ThemeNotifier._() : super(ThemeMode.dark);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final dark = prefs.getBool(_key) ?? true;
    value = dark ? ThemeMode.dark : ThemeMode.light;
  }

  Future<void> toggle() async {
    value = value == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, value == ThemeMode.dark);
  }

  bool get isDark => value == ThemeMode.dark;
}
