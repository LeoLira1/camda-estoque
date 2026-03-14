import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:image_picker/image_picker.dart';
import '../../core/theme/app_colors.dart';
import '../../data/models/pendencia.dart';
import '../../data/repositories/pendencias_repository.dart';
import '../../shared/widgets/loading_widget.dart' as lw;

class PendenciasScreen extends StatefulWidget {
  const PendenciasScreen({super.key});

  @override
  State<PendenciasScreen> createState() => _PendenciasScreenState();
}

class _PendenciasScreenState extends State<PendenciasScreen> {
  final _repo = PendenciasRepository();
  final _picker = ImagePicker();

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

  Future<Uint8List?> _pickImage(ImageSource source) async {
    try {
      final xfile = await _picker.pickImage(
        source: source,
        imageQuality: 70,
        maxWidth: 1280,
        maxHeight: 1280,
      );
      if (xfile == null) return null;
      return await xfile.readAsBytes();
    } catch (e) {
      if (!mounted) return null;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro ao capturar imagem: $e'), backgroundColor: AppColors.red),
      );
      return null;
    }
  }

  Future<void> _adicionarPendencia() async {
    final obsCtrl = TextEditingController();
    Uint8List? imagemBytes;

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) {
          Future<void> capturar(ImageSource source) async {
            Navigator.pop(ctx); // fecha o sheet enquanto abre câmera
            final bytes = await _pickImage(source);
            if (!mounted) return;
            if (bytes != null) {
              // reabre o sheet com a imagem já selecionada
              imagemBytes = bytes;
              await _abrirFormulario(obsCtrl, imagemBytes);
            }
          }

          return Padding(
            padding: EdgeInsets.only(
              bottom: MediaQuery.of(ctx).viewInsets.bottom,
              left: 16, right: 16, top: 20,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Handle
                Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2)))),
                const SizedBox(height: 20),
                const Text('Nova Pendência', style: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                const SizedBox(height: 6),
                const Text('Escolha como adicionar a foto:', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                const SizedBox(height: 24),

                // Botões de captura
                Row(children: [
                  Expanded(
                    child: _SourceButton(
                      icon: Icons.camera_alt_outlined,
                      label: 'Câmera',
                      color: AppColors.blue,
                      onTap: () => capturar(ImageSource.camera),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _SourceButton(
                      icon: Icons.photo_library_outlined,
                      label: 'Galeria',
                      color: AppColors.purple,
                      onTap: () => capturar(ImageSource.gallery),
                    ),
                  ),
                ]),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }

  Future<void> _abrirFormulario(TextEditingController obsCtrl, Uint8List? imagemBytes) async {
    Uint8List? imagemAtual = imagemBytes;
    final obsCtrlLocal = obsCtrl.text.isEmpty ? obsCtrl : obsCtrl;

    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) {
          Future<void> trocarFoto(ImageSource source) async {
            Navigator.pop(ctx);
            final bytes = await _pickImage(source);
            if (bytes != null) {
              imagemAtual = bytes;
              await _abrirFormulario(obsCtrl, imagemAtual);
            }
          }

          return Padding(
            padding: EdgeInsets.only(
              bottom: MediaQuery.of(ctx).viewInsets.bottom,
              left: 16, right: 16, top: 20,
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(child: Container(width: 40, height: 4, decoration: BoxDecoration(color: AppColors.surfaceBorder, borderRadius: BorderRadius.circular(2)))),
                  const SizedBox(height: 16),
                  const Text('Confirmar Pendência', style: TextStyle(fontFamily: 'Outfit', fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary)),
                  const SizedBox(height: 14),

                  // Preview da imagem
                  if (imagemAtual != null) ...[
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: Stack(
                        children: [
                          Image.memory(
                            imagemAtual!,
                            width: double.infinity,
                            height: 200,
                            fit: BoxFit.cover,
                          ),
                          Positioned(
                            top: 8, right: 8,
                            child: GestureDetector(
                              onTap: () => showModalBottomSheet(
                                context: ctx,
                                backgroundColor: AppColors.surface,
                                shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
                                builder: (_) => Padding(
                                  padding: const EdgeInsets.all(16),
                                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                                    ListTile(leading: const Icon(Icons.camera_alt_outlined, color: AppColors.blue), title: const Text('Usar câmera', style: TextStyle(color: AppColors.textPrimary)), onTap: () { Navigator.pop(ctx); trocarFoto(ImageSource.camera); }),
                                    ListTile(leading: const Icon(Icons.photo_library_outlined, color: AppColors.purple), title: const Text('Escolher da galeria', style: TextStyle(color: AppColors.textPrimary)), onTap: () { Navigator.pop(ctx); trocarFoto(ImageSource.gallery); }),
                                  ]),
                                ),
                              ),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.black.withOpacity(0.6),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Row(mainAxisSize: MainAxisSize.min, children: [
                                  Icon(Icons.edit_outlined, color: Colors.white, size: 14),
                                  SizedBox(width: 4),
                                  Text('Trocar', style: TextStyle(color: Colors.white, fontSize: 12)),
                                ]),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],

                  // Observação
                  TextField(
                    controller: obsCtrlLocal,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Observação (opcional)',
                      hintText: 'Descreva o problema ou pendência...',
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 20),

                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: imagemAtual == null ? null : () async {
                        Navigator.pop(ctx);
                        try {
                          final b64 = base64Encode(imagemAtual!);
                          await _repo.inserir(
                            fotoBase64: b64,
                            observacao: obsCtrlLocal.text.trim(),
                          );
                          await _loadData();
                        } catch (e) {
                          if (!mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Erro: $e'), backgroundColor: AppColors.red),
                          );
                        }
                      },
                      icon: const Icon(Icons.save_outlined),
                      label: const Text('Registrar Pendência', style: TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          );
        },
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

class _SourceButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _SourceButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 20),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(children: [
          Icon(icon, color: color, size: 36),
          const SizedBox(height: 8),
          Text(label, style: TextStyle(fontFamily: 'Outfit', fontSize: 14, fontWeight: FontWeight.w600, color: color)),
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
