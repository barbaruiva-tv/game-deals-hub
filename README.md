# Game Deals Hub

Dashboard de ofertas de jogos de PC para o Brasil.

## Configuração

1. Em **Settings > Secrets and variables > Actions**, crie o segredo `ITAD_API_KEY` com a chave do IsThereAnyDeal. Não compartilhe a chave em chats nem no código.
2. Em **Actions**, execute manualmente `Atualizar ofertas` para validar a integração.
3. Em **Settings > Pages**, selecione **Deploy from a branch**, branch `main`, pasta `/ (root)`.

A atualização é agendada diariamente às 11:15 UTC (08:15 em Brasília), sujeita a atrasos do GitHub Actions. Os preços devem ser verificados na loja antes da compra.

**Limitações:** a API pode não cobrir todas as promoções das quatro lojas; cupons e mínimos históricos não são afirmados sem fonte verificável. Nenhum preço de exemplo é apresentado como oferta real.

## Filtros de gênero e ano (RAWG)

A integração é opcional e requer uma chave RAWG própria. Obtenha em https://rawg.io/apidocs e crie o segredo de Actions `RAWG_API_KEY` em Settings > Secrets and variables > Actions. Nunca coloque a chave em arquivos públicos.

O coletor `enrich.py` consulta até 80 títulos novos por execução, guarda resultados em `metadata_cache.json` e só aceita correspondência exata normalizada e única. DLCs, bundles e jogos sem correspondência podem ficar sem gênero/ano. Os filtros ficam desabilitados enquanto não existirem metadados confirmados.

Confira os termos de licença RAWG para seu uso: o plano gratuito é indicado para projetos pessoais/não comerciais e exige atribuição com link. Projetos comerciais precisam de autorização/plano apropriado. Fonte: https://rawg.io/apidocs
