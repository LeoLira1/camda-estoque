import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/theme_notifier.dart';
import 'features/auth/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Carrega variáveis de ambiente
  try {
    await dotenv.load(fileName: '.env');
  } catch (_) {
    debugPrint('[CAMDA] .env não encontrado — usando variáveis de sistema');
  }

  // Inicializa locale pt_BR para intl
  await initializeDateFormatting('pt_BR', null);

  // Carrega preferência de tema
  await ThemeNotifier.instance.load();

  // Força orientação portrait+landscape (adapta para tablet)
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: Colors.transparent,
  ));

  runApp(const CamdaApp());
}

class CamdaApp extends StatefulWidget {
  const CamdaApp({super.key});

  @override
  State<CamdaApp> createState() => _CamdaAppState();
}

class _CamdaAppState extends State<CamdaApp> {
  @override
  void initState() {
    super.initState();
    ThemeNotifier.instance.addListener(_onThemeChange);
  }

  @override
  void dispose() {
    ThemeNotifier.instance.removeListener(_onThemeChange);
    super.dispose();
  }

  void _onThemeChange() => setState(() {});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CAMDA Estoque',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeNotifier.instance.value,
      home: const LoginScreen(),
      builder: (context, child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(
              MediaQuery.of(context).textScaler.scale(1.0).clamp(0.85, 1.25),
            ),
          ),
          child: child!,
        );
      },
    );
  }
}
