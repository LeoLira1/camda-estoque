import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/login_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Carrega variáveis de ambiente
  try {
    await dotenv.load(fileName: '.env');
  } catch (_) {
    // Em desenvolvimento sem .env, variáveis virão do ambiente
    debugPrint('[CAMDA] .env não encontrado — usando variáveis de sistema');
  }

  // Inicializa locale pt_BR para intl
  await initializeDateFormatting('pt_BR', null);

  // Força orientação portrait+landscape (adapta para tablet)
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Barra de status transparente
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: Colors.transparent,
  ));

  runApp(const CamdaApp());
}

class CamdaApp extends StatelessWidget {
  const CamdaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CAMDA Estoque',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const LoginScreen(),
      builder: (context, child) {
        // Garante que o texto não escale além do razoável
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
