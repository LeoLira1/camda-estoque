import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../shared/layouts/main_layout.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _senhaController = TextEditingController();
  bool _loading = false;
  bool _error = false;
  bool _obscure = true;

  String get _password => dotenv.env['CAMDA_PASSWORD'] ?? 'forca';

  @override
  void dispose() {
    _senhaController.dispose();
    super.dispose();
  }

  void _login() {
    setState(() => _loading = true);
    Future.delayed(const Duration(milliseconds: 400), () {
      if (!mounted) return;
      if (_senhaController.text.trim() == _password) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const MainLayout()),
        );
      } else {
        setState(() {
          _loading = false;
          _error = true;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final now = CamdaDateUtils.nowBRT();
    final hora = CamdaDateUtils.formatTime(now);
    final diaNome = CamdaDateUtils.diaSemanaFull(now);
    final data = CamdaDateUtils.formatDate(now);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Fundo com gradiente
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF0A0F1A), Color(0xFF111827)],
              ),
            ),
          ),
          // Círculos decorativos (glassmorphism bg)
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 400,
              height: 400,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.green.withOpacity(0.04),
              ),
            ),
          ),
          Positioned(
            bottom: -150,
            left: -100,
            child: Container(
              width: 500,
              height: 500,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.blue.withOpacity(0.04),
              ),
            ),
          ),
          // Conteúdo
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 380),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _buildWeatherCard(diaNome, data, hora),
                    const SizedBox(height: 24),
                    _buildLoginCard(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeatherCard(String diaNome, String data, String hora) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(28),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF0F2027), Color(0xFF2C5364)],
            ),
            borderRadius: BorderRadius.circular(28),
            border: Border.all(color: Colors.white.withOpacity(0.12)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.55),
                blurRadius: 64,
                offset: const Offset(0, 24),
              ),
            ],
          ),
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              // Cabeçalho
              Row(
                children: [
                  Text(
                    '$diaNome · $data · $hora',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.55),
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              // Logo / título
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: AppColors.green.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppColors.green.withOpacity(0.3)),
                ),
                child: const Icon(
                  Icons.eco_outlined,
                  color: AppColors.green,
                  size: 40,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'CAMDA',
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 36,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  letterSpacing: -1,
                ),
              ),
              Text(
                'Estoque Mestre',
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                  color: Colors.white.withOpacity(0.55),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '📍 Quirinópolis, GO',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.35),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLoginCard() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withOpacity(0.12)),
          ),
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              TextField(
                controller: _senhaController,
                obscureText: _obscure,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  letterSpacing: 2,
                ),
                decoration: InputDecoration(
                  hintText: '🔑 Senha de acesso',
                  hintStyle: TextStyle(
                    color: Colors.white.withOpacity(0.35),
                    letterSpacing: 1,
                    fontSize: 14,
                  ),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                      color: Colors.white.withOpacity(0.4),
                      size: 18,
                    ),
                    onPressed: () => setState(() => _obscure = !_obscure),
                  ),
                  filled: true,
                  fillColor: Colors.white.withOpacity(0.08),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(30),
                    borderSide: BorderSide(color: Colors.white.withOpacity(0.22)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(30),
                    borderSide: const BorderSide(color: AppColors.green, width: 1.5),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                ),
                onSubmitted: (_) => _login(),
              ),
              if (_error) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.red.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.red.withOpacity(0.3)),
                  ),
                  child: const Text(
                    '❌ Senha incorreta',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.statusAvaria, fontSize: 13),
                  ),
                ),
              ],
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _loading ? null : _login,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white.withOpacity(0.12),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    side: BorderSide(color: Colors.white.withOpacity(0.28)),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: _loading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Text(
                          'ENTRAR',
                          style: TextStyle(
                            fontFamily: 'Outfit',
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 2,
                          ),
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
