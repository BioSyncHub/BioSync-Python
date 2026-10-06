# BioSync

Aplicativo Windows com menu de configuracoes, indicador visual e assistencia de mira ajustavel.

## O que tem

- Ajuste do FOV e da velocidade de movimento.
- Escolha do ponto de mira: cabeca, peito ou barriga.
- Atalho de ativacao configuravel.
- Circulo do FOV com opcao de ocultar, mudar cor e opacidade.
- Pagina **Views** com caixas ESP, filtro por distancia aproximada, confidence/IOU, linhas, marcadores e zonas corporais.
- Perfis para salvar e carregar configuracoes.

## Modelos ONNX e configuracao visual

O motor le as classes e as dimensoes fixas de entrada do proprio metadata ONNX. Para modelos com varias classes, ajuste `target_classes` em `[AI options]` no `config.ini`, separando os nomes por virgula. Uma lista vazia ou ausente aceita todas as classes; modelos de classe unica usam automaticamente a classe disponivel. A classe `head` recebe prioridade quando o ponto de mira selecionado e cabeca; sem ela, o ponto usa o offset proporcional da caixa.

As opcoes de deteccao e visuais tambem podem ser definidas em `[AI options]` e `[Views]`. A pagina **Views** oferece os mesmos ajustes na interface, incluindo cores hexadecimais customizadas. **Aplicar** atualiza o motor e `profiles/active.json`; **Salvar perfil** guarda todos os ajustes de aim e Views juntos no perfil selecionado.

## Como abrir e usar

- Para a build de pasta, mantenha toda a pasta `dist\BioSync` junta e abra `dist\BioSync\BioSync.exe`.
- O menu principal nao requer Python instalado. Na primeira ativacao do motor ONNX integrado, o BioSync solicita Python 3.11 e as dependencias do runtime; se o Python Launcher/3.11 estiver ausente, o app oferece abrir a pagina oficial de download. Reinicie o BioSync depois de instalar o Python.
- Pressione `X` para mostrar ou ocultar o menu; `Esc` tambem o oculta.
- Ajuste as opcoes no menu e salve um perfil para reutiliza-las.
- A assistencia de mira so e ativada pelo atalho escolhido no menu.

## Limites e cuidados

- A deteccao pode errar ou nao encontrar alvos; nao ha garantia de precisao ou funcionamento em todos os PCs.
- O app nao e invisivel e nao evita anti-cheat, denuncias ou sancoes.
- Use somente em ambientes offline, privados e autorizados. Em jogos online, software que automatiza a mira pode violar as regras do jogo.
- A politica do RICOCHET pode aplicar restricoes de matchmaking, suspensoes, banimentos ou restricoes de hardware. Uma gravacao ou denuncia pode ser considerada; nenhuma configuracao impede sancoes.
- O BioSync nao e afiliado nem aprovado pela Activision.

Leia a [politica oficial de seguranca e aplicacao da Activision](https://support.activision.com/articles/call-of-duty-security-and-enforcement-policy).

O usuario e responsavel pelo uso e por seguir as regras aplicaveis. O software e fornecido sem garantia de deteccao correta ou ausencia de sancoes; este aviso nao afasta direitos ou responsabilidades que a lei nao permita excluir.