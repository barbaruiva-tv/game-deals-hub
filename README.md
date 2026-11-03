# Game Deals Hub

Dashboard de ofertas de jogos de PC para o Brasil.

## Configuração

1. Em **Settings > Secrets and variables > Actions**, crie o segredo `ITAD_API_KEY` com a chave do IsThereAnyDeal. Não compartilhe a chave em chats nem no código.
2. Em **Actions**, execute manualmente `Atualizar ofertas` para validar a integração.
3. Em **Settings > Pages**, selecione **Deploy from a branch**, branch `main`, pasta `/ (root)`.

A atualização é agendada diariamente às 11:15 UTC (08:15 em Brasília), sujeita a atrasos do GitHub Actions. Os preços devem ser verificados na loja antes da compra.

**Limitações:** a API pode não cobrir todas as promoções das quatro lojas; cupons e mínimos históricos não são afirmados sem fonte verificável. Nenhum preço de exemplo é apresentado como oferta real.
