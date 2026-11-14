-- ============================================================
-- Sugestão de índices para reduzir Rows Read no Turso/libSQL
-- Gerado a partir de auditoria de queries em app_turso.py
-- Todos já aplicados automaticamente via _get_connection()
-- ============================================================

-- vendas_historico: filtros e JOINs mais pesados da aplicação
CREATE INDEX IF NOT EXISTS idx_vh_codigo
    ON vendas_historico(codigo);

CREATE INDEX IF NOT EXISTS idx_vh_data
    ON vendas_historico(data_upload);

-- Composto usado em CTAs de get_ultima_venda_por_produto e get_vendas_historico
CREATE INDEX IF NOT EXISTS idx_vh_codigo_data
    ON vendas_historico(codigo, data_upload);

-- divergencias: filtros de busca e reconciliação
CREATE INDEX IF NOT EXISTS idx_div_codigo
    ON divergencias(codigo);

CREATE INDEX IF NOT EXISTS idx_div_criado
    ON divergencias(criado_em);

-- validade_lotes: alertas de vencimento e produtos parados
CREATE INDEX IF NOT EXISTS idx_vl_produto
    ON validade_lotes(produto);

CREATE INDEX IF NOT EXISTS idx_vl_vencimento
    ON validade_lotes(vencimento);

-- reposicao_loja: filtro principal da aba "Repor na Loja"
CREATE INDEX IF NOT EXISTS idx_reposto
    ON reposicao_loja(reposto);

-- avarias: filtro de status (aberto/resolvido)
CREATE INDEX IF NOT EXISTS idx_av_status
    ON avarias(status);

-- contagem_itens: lookup por código
CREATE INDEX IF NOT EXISTS idx_ci_codigo
    ON contagem_itens(codigo);

-- mapa_posicoes: render por rack (rua × face)
CREATE INDEX IF NOT EXISTS idx_mapa_pos_rua
    ON mapa_posicoes(rua, face);

-- ============================================================
-- Auditoria de row reads (11/2026) — EXPLAIN QUERY PLAN no app e no MCP
-- Só conta leitura o que roda NO TURSO: escritas (UPDATE/DELETE varrem a
-- tabela para achar as linhas), leituras dentro de transação de escrita e
-- tudo que o MCP camda-mcp consulta por HTTP. As leituras normais do app
-- saem da réplica local e não gastam cota.
-- Criar índice em tabela existente custa UMA varredura dela (uma vez só).
-- ============================================================

-- variacao_estoque não tinha índice nenhum e cresce a cada upload
CREATE INDEX IF NOT EXISTS idx_ve_detectado
    ON variacao_estoque(detectado_em);
CREATE INDEX IF NOT EXISTS idx_ve_status_det
    ON variacao_estoque(status, detectado_em);

-- DELETE ... WHERE data_disparo < ? (limpeza dos alertas)
CREATE INDEX IF NOT EXISTS idx_ad_data
    ON alertas_disparados(data_disparo);

-- DELETE/SELECT ... WHERE data_ref = ? (upload e conferência GV)
CREATE INDEX IF NOT EXISTS idx_fgv_data_ref
    ON faturamento_gv(data_ref);

-- DELETE ... WHERE data_referencia = ? (reimportar MATR480)
CREATE INDEX IF NOT EXISTS idx_mt_data_ref
    ON materiais_terceiros(data_referencia);

-- históricos consultados por período pelo MCP
CREATE INDEX IF NOT EXISTS idx_hd_criado
    ON historico_divergencias(criado_em);
CREATE INDEX IF NOT EXISTS idx_lm_registrado
    ON lancamentos_manuais(registrado_em);
CREATE INDEX IF NOT EXISTS idx_ret_ter_reg
    ON retiradas_terceiros(registrado_em);

-- UPDATE/DELETE ... WHERE data_contagem=? AND produto_id=? a cada contagem
CREATE INDEX IF NOT EXISTS idx_cicli_prod_data
    ON inventario_cicli(produto_id, data_contagem);

-- subconsulta de fotos por avaria (ver_avarias do MCP) e exclusão de avaria
CREATE INDEX IF NOT EXISTS idx_af_avaria
    ON avaria_fotos(avaria_id);
CREATE INDEX IF NOT EXISTS idx_au_avaria
    ON avaria_unidades(avaria_id);

CREATE INDEX IF NOT EXISTS idx_pa_produto
    ON principios_ativos(produto);

-- Índices de EXPRESSÃO: o MCP filtra por UPPER(TRIM(codigo)), que anula os
-- índices simples em codigo. ATENÇÃO: com idx_vh_cod_norm o SQLite prefere
-- varrer esse índice inteiro em "WHERE data_upload >= ? GROUP BY
-- UPPER(TRIM(codigo))"; nessas consultas o MCP agrupa por UPPER(TRIM(+codigo))
-- para continuar entrando pelo período (idx_vh_data).
CREATE INDEX IF NOT EXISTS idx_vh_cod_norm
    ON vendas_historico(UPPER(TRIM(codigo)), data_upload);
CREATE INDEX IF NOT EXISTS idx_em_cod_norm
    ON estoque_mestre(UPPER(TRIM(codigo)));
CREATE INDEX IF NOT EXISTS idx_div_cod_norm
    ON divergencias(UPPER(TRIM(codigo)));
