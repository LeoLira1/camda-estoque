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
