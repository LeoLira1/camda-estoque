/// Constantes globais do CAMDA App.
class AppConstants {
  AppConstants._();

  // ── App Info ───────────────────────────────────────────────────────────────
  static const String appName = 'CAMDA Estoque';
  static const String appVersion = '1.0.0';
  static const String appSubtitle = 'Gestão de Estoque Mestre';

  // ── Armazém ────────────────────────────────────────────────────────────────
  static const int numRacks = 10;
  static const int numColunas = 13;
  static const int numNiveis = 4;
  static const int totalCelulas = numRacks * 2 * numColunas * numNiveis; // 1.040

  // ── Validade ───────────────────────────────────────────────────────────────
  static const int diasAlertaVencimento = 30;
  static const int diasAlertaVencimentoCritico = 7;

  // ── Weather API ────────────────────────────────────────────────────────────
  static const double latQuirinopolis = -18.45;
  static const double lonQuirinopolis = -50.45;
  static const String weatherApiUrl = 'https://api.open-meteo.com/v1/forecast';
  static const int weatherCacheTtlMinutes = 30;

  // ── Turso API ──────────────────────────────────────────────────────────────
  static const int tursoTimeoutSeconds = 15;
  static const int maxRetries = 3;

  // ── Navegação ──────────────────────────────────────────────────────────────
  static const String routeLogin = '/login';
  static const String routeDashboard = '/dashboard';
  static const String routeEstoque = '/estoque';
  static const String routeAvarias = '/avarias';
  static const String routeValidade = '/validade';
  static const String routeReposicao = '/reposicao';
  static const String routeVendas = '/vendas';
  static const String routeMapa = '/mapa';

  // ── Cores padrão para produtos no mapa ────────────────────────────────────
  static const List<String> coresPadraoMapa = [
    '#4ade80', '#60a5fa', '#f59e0b', '#f87171',
    '#a78bfa', '#34d399', '#fb923c', '#e879f9',
    '#22d3ee', '#facc15', '#6ee7b7', '#fda4af',
  ];
}
