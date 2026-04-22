## Working agreements

- Before any modification, read and map the entire repository structure
- Identify all files and their responsibilities  
- Read all imports and dependencies before touching any file
- Never rename or remove functions without updating all references
- Preserve existing code style and patterns
- After modification, list which files were read and changed
- If unsure about any dependency, read more files before writing code
- Never assume — always verify in the codebase

## Princípios gerais

- Entregue funcionalidade real, não simulações visuais.
- Não substitua partes complexas do sistema por placeholders, cards estáticos, dados falsos ou elementos decorativos.
- Se um dashboard, app ou sistema já existe, preserve o comportamento funcional antes de tentar “embelezar”.
- Fidelidade funcional é mais importante que semelhança visual superficial.
- Nunca considere o trabalho concluído apenas porque a interface “parece pronta”.

## Regra crítica: não ser preguiçoso

- Não simplifique uma tarefa complexa sem avisar.
- Não omita partes importantes do projeto para terminar mais rápido.
- Não entregue versão reduzida fingindo que é clone completo.
- Não transforme uma aplicação real em landing page, mockup ou protótipo estático.
- Se algo não puder ser concluído, informe exatamente o que falta e por quê.

## Antes de começar qualquer projeto

Sempre siga esta sequência:

1. Mapear a arquitetura do projeto.
2. Identificar arquivos principais, dependências, fluxos e fontes de dados.
3. Identificar páginas, abas, widgets, filtros, tabelas, gráficos, APIs, estados e regras de negócio.
4. Explicar resumidamente a estrutura encontrada.
5. Só depois começar a alterar, recriar ou portar.

## Regras para clonagem, reconstrução ou refatoração

Se a tarefa for clonar, recriar, portar ou refazer um app:

- Primeiro inventarie tudo que existe.
- Liste os componentes reais do sistema.
- Preserve interações, filtros, carregamento de dados, tabelas, gráficos, métricas e fluxos do usuário.
- Não use componentes estáticos como substituto de lógica real.
- Não trate “clone” como apenas “aparência parecida”.
- Reproduza também a lógica, o comportamento e os estados da interface.
- Se houver ambiguidade, priorize comportamento real em vez de visual bonito.

## Regras para dashboards

Em dashboards, verificar obrigatoriamente:

- páginas
- abas
- cards
- KPIs
- filtros
- tabelas
- gráficos
- paginação
- ordenação
- busca
- expansão/colapso
- upload/download
- cache
- leitura de dados
- agregações
- regras condicionais
- responsividade, se aplicável

Nunca entregar apenas:
- meia dúzia de cards
- layout bonito sem dados reais
- gráfico fake
- tabela hardcoded
- navegação vazia

## Regra sobre dados

- Nunca invente dados.
- Nunca crie registros falsos para fingir funcionamento.
- Use sempre as fontes reais do projeto.
- Se os dados não estiverem acessíveis, explique isso claramente.
- Se precisar criar dados temporários para teste, marque explicitamente como mock temporário.

## Regra sobre código existente

- Respeite a estrutura do projeto.
- Evite reescrever tudo sem necessidade.
- Antes de apagar ou substituir arquivos, verifique se eles contêm lógica importante.
- Preserve nomes, convenções e organização quando isso ajudar manutenção.
- Não faça mudanças destrutivas sem necessidade clara.

## Regra sobre entrega completa

Quando o objetivo for um app utilizável, não pare no meio.

Considere a cadeia completa:
- código funcionando
- dependências corretas
- build configurada
- artefato gerado quando aplicável
- workflow de automação quando fizer sentido
- documentação mínima para rodar
- saída final clara para o usuário

## Regra para Android / APK / releases

Se o objetivo envolver app Android, APK ou entrega instalável:

- Não parar apenas no código-fonte.
- Configurar build funcional.
- Gerar APK ou AAB, quando viável.
- Criar workflow automatizado de build, se o repositório usar CI/CD.
- Publicar artefato em release, quando essa for a meta pedida.
- Só considerar concluído quando houver artefato final acessível ou quando houver bloqueio real claramente explicado.

## Regra para Streamlit

Se o projeto usar Streamlit:

- Identificar o arquivo principal de entrada.
- Identificar páginas adicionais.
- Identificar widgets, filtros, session state, cache, loaders e fontes de dados.
- Preservar tabelas, gráficos, métricas e interações reais.
- Não reduzir app Streamlit a cards estáticos.
- Garantir que a aplicação abra sem erro.

## Regra para inspeção inicial

Antes de implementar mudanças grandes, sempre responder internamente estas perguntas:

- Qual é o arquivo principal?
- Quais arquivos concentram a lógica?
- Quais partes são interface?
- Quais partes são dados?
- Quais partes são regras de negócio?
- O que é obrigatório preservar?
- O que ainda não entendi?

Se alguma dessas respostas estiver fraca, investigar mais antes de editar.

## Regra sobre comunicação de progresso

Ao trabalhar em tarefas grandes:

- mostrar o que já foi descoberto
- dizer o que está sendo preservado
- dizer o que ainda falta
- distinguir claramente entre concluído, parcial e pendente

Nunca dizer ou insinuar que terminou se ainda faltam partes relevantes.

## Regra sobre qualidade de conclusão

Ao finalizar, sempre entregar:

1. O que foi implementado.
2. O que foi preservado.
3. O que foi corrigido.
4. O que ainda falta.
5. Como rodar.
6. Como validar.
7. Quais arquivos concentram a lógica principal.

## Critério de aceite padrão

Uma tarefa só pode ser considerada concluída quando:

- a aplicação roda sem erro
- os dados reais são usados
- a lógica principal foi preservada
- as interações importantes funcionam
- não há substituição enganosa por elementos estáticos
- o resultado final está utilizável de verdade

## Proibições

Nunca:
- fingir que completou clone completo quando fez apenas layout
- inventar funcionamento inexistente
- esconder limitação atrás de interface bonita
- remover complexidade importante sem avisar
- trocar dados reais por hardcode sem avisar
- resumir projeto rico em uma versão rasa
- entregar “fachada” no lugar do produto

## Preferência de execução

Em caso de dúvida, seguir esta prioridade:

1. funcionalidade real
2. integridade dos dados
3. preservação da lógica
4. automação de entrega
5. refinamento visual

## Instrução final

Pense como alguém responsável por entregar um sistema utilizável de verdade, não apenas uma demonstração visual.
Se precisar escolher entre “parecer pronto” e “estar pronto”, escolha “estar pronto”.
