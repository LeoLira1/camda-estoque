import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/date_utils.dart';
import '../../data/models/pendencia.dart';
import '../../data/repositories/pendencias_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;
import '../../shared/widgets/glass_card.dart';

class PendenciasScreen extends StatefulWidget {
  const PendenciasScreen({super.key});

  @override
  State<PendenciasScreen> createState() => _PendenciasScreenState();
}

class _PendenciasScreenState extends State<PendenciasScreen> {
  final _repo = PendenciasRepository();

  List<Pendencia> _pendencias = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _repo.getAll();
      if (!mounted) return;
      setState(() { _pendencias = data; _loading = false; });
    } catch (e) {
      if (!mounted) return;
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _deletar(Pendencia p) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Excluir pendência?'),
        content: Text('Registrada em ${p.dataRegistro}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.red, foregroundColor: Colors.white),
            child: const Text('Excluir'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _repo.deletar(p.id);
      await _loadData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
      );
    }
  }

  Future<void> _adicionarPendencia() async {
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(height: 12),
          Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2))),
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text('Nova Pendência', style: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
          ),
          ListTile(
            leading: const Icon(Icons.camera_alt_outlined, color: AppColors.green),
            title: const Text('Tirar foto', style: TextStyle(color: AppColors.textPrimary)),
            onTap: () => Navigator.pop(_, ImageSource.camera),
          ),
          ListTile(
            leading: const Icon(Icons.photo_library_outlined, color: AppColors.blue),
            title: const Text('Escolher da galeria', style: TextStyle(color: AppColors.textPrimary)),
            onTap: () => Navigator.pop(_, ImageSource.gallery),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );

    if (source == null) return;

    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: source,
      maxWidth: 1280,
      maxHeight: 1280,
      imageQuality: 75,
    );
    if (picked == null) return;

    final bytes = await picked.readAsBytes();
    final b64 = base64Encode(bytes);

    if (!mounted) return;
    final obsCtrl = TextEditingController();

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(ctx).viewInsets.bottom,
          left: 16, right: 16, top: 20,
        ),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2)))),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Image.memory(bytes, height: 180, width: double.infinity, fit: BoxFit.cover),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: obsCtrl,
            maxLines: 2,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Observação (opcional)', isDense: true),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () async {
                Navigator.pop(ctx);
                try {
                  await _repo.inserir(fotoBase64: b64, observacao: obsCtrl.text.trim());
                  await _loadData();
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
                  );
                }
              },
              child: const Text('Registrar Pendência'),
            ),
          ),
          const SizedBox(height: 20),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Pendências de Entrega'),
        actions: [
          IconButton(onPressed: _loadData, icon: const Icon(Icons.refresh, size: 20)),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _adicionarPendencia,
        backgroundColor: AppColors.blue,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add_a_photo_outlined),
      ),
      body: _loading
          ? const lw.LoadingWidget(message: 'Carregando pendências...')
          : _error != null
              ? lw.ErrorWidget(message: _error!, onRetry: _loadData)
              : _pendencias.isEmpty
                  ? const lw.EmptyWidget(
                      message: 'Nenhuma pendência registrada.\nUse o botão + para fotografar.',
                      icon: Icons.image_not_supported_outlined,
                    )
                  : _buildGrid(),
    );
  }

  Widget _buildGrid() {
    return GridView.builder(
      padding: const EdgeInsets.all(12),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
        childAspectRatio: 0.78,
      ),
      itemCount: _pendencias.length,
      itemBuilder: (context, i) {
        final p = _pendencias[i];
        return _PendenciaCard(
          pendencia: p,
          diasDesde: _repo.diasDesde(p.dataRegistro),
          onDelete: () => _deletar(p),
          onTap: () => _showFoto(p),
        ).animate().fadeIn(duration: 300.ms, delay: (i * 40).clamp(0, 400).ms);
      },
    );
  }

  void _showFoto(Pendencia p) {
    Uint8List? bytes;
    try {
      bytes = base64Decode(p.fotoBase64);
    } catch (_) {}

    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (bytes != null)
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
              child: Image.memory(bytes, fit: BoxFit.cover),
            )
          else
            Container(
              height: 200,
              decoration: const BoxDecoration(
                color: AppColors.surfaceVariant,
                borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
              ),
              child: const Center(child: Icon(Icons.image_not_supported_outlined, color: AppColors.textMuted, size: 48)),
            ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              if (p.observacao.isNotEmpty)
                Text(p.observacao, style: const TextStyle(fontSize: 14, color: AppColors.textPrimary)),
              const SizedBox(height: 4),
              Text('Registrado: ${p.dataRegistro}', style: const TextStyle(fontSize: 11, color: AppColors.textMuted)),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Fechar'),
                ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _PendenciaCard extends StatelessWidget {
  final Pendencia pendencia;
  final int diasDesde;
  final VoidCallback onDelete;
  final VoidCallback onTap;

  const _PendenciaCard({
    required this.pendencia,
    required this.diasDesde,
    required this.onDelete,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    Uint8List? bytes;
    try { bytes = base64Decode(pendencia.fotoBase64); } catch (_) {}

    final isAtrasado = diasDesde > 5;
    final borderColor = isAtrasado ? AppColors.red : AppColors.surfaceBorder;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: borderColor.withOpacity(isAtrasado ? 0.5 : 0.3)),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // Foto
          Expanded(
            child: Stack(fit: StackFit.expand, children: [
              if (bytes != null)
                Image.memory(bytes, fit: BoxFit.cover)
              else
                Container(
                  color: AppColors.surfaceVariant,
                  child: const Icon(Icons.image_outlined, color: AppColors.textMuted, size: 36),
                ),
              // Badge dias
              Positioned(
                top: 6, right: 6,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (isAtrasado ? AppColors.red : AppColors.blue).withOpacity(0.85),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${diasDesde}d',
                    style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 10, fontWeight: FontWeight.w700, color: Colors.white),
                  ),
                ),
              ),
            ]),
          ),
          // Info
          Padding(
            padding: const EdgeInsets.all(8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(pendencia.dataRegistro,
                  style: const TextStyle(fontFamily: 'JetBrainsMono', fontSize: 9, color: AppColors.textMuted)),
              if (pendencia.observacao.isNotEmpty)
                Text(pendencia.observacao,
                    style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                    maxLines: 2, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 4),
              GestureDetector(
                onTap: onDelete,
                child: const Row(children: [
                  Icon(Icons.delete_outline, color: AppColors.red, size: 14),
                  SizedBox(width: 4),
                  Text('Excluir', style: TextStyle(fontSize: 10, color: AppColors.red)),
                ]),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}
