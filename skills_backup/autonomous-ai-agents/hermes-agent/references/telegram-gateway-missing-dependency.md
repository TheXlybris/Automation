# Telegram Gateway: \"python-telegram-bot not installed\"

## Sintoma

Gateway arranca mas os logs mostram:
```
WARNING gateway.run: Telegram: python-telegram-bot not installed
WARNING gateway.run: No adapter available for telegram
WARNING gateway.run: No adapter could be created for any of the 1 configured platform(s).
INFO gateway.run: Channel directory built: 0 target(s)
```

O `hermes gateway status` mostra o serviço ativo, mas `send_message` retorna `No messaging platforms connected`.

## Causa Raiz

O pacote `python-telegram-bot` não está no ambiente Python onde o gateway corre. O pacote `hermes-agent` base NÃO inclui esta dependência — só vem via extra `[messaging]`.

```bash
pip show hermes-agent
# Mostra: Requires: croniter, fire, httpx, jinja2, openai, prompt_toolkit, ...
# NÃO inclui python-telegram-bot
```

O METADATA do Hermes mostra:
```
Requires-Dist: python-telegram-bot[webhooks]==22.6; extra == "messaging"
```

## Fix

### Ubuntu 24.04+ (PEP 668 — externamente gerido)

```bash
# Usar --break-system-packages é seguro porque o Hermes já está instalado globalmente
export PIP_BREAK_SYSTEM_PACKAGES=1
pip install --user "python-telegram-bot[webhooks]==22.6"
# Ou equivalente:
PIP_BREAK_SYSTEM_PACKAGES=1 pip install --user "python-telegram-bot[webhooks]==22.6"
```

### Reiniciar gateway

```bash
systemctl --user restart hermes-gateway
```

### Verificar

```bash
tail -20 ~/.hermes/logs/gateway.log
```

Deve aparecer:
```
INFO gateway.run: Telegram connected
INFO gateway.run: Channel directory built: 1 target(s)
```

## O que NÃO fazer

- **Não** reinstalar o `hermes-agent` todo — instalar apenas a dependência em falta é suficiente.
- **Não** usar `pipx` ou criar um `venv` novo — o gateway do Hermes está ligado ao Python do sistema (`/usr/bin/python3`) e um venv novo não resolve o problema.
- **Não** correr `hermes gateway setup` — o setup é um wizard de credenciais, NÃO instala pacotes Python.

## Diagnóstico rápido

```bash
# 1. Verificar se o pacote está instalado no Python do gateway
/usr/bin/python3 -c "import telegram" 2>/dev/null && echo "OK" || echo "FALTA"

# 2. Verificar estado do gateway
hermes gateway status

# 3. Verificar logs por "not installed"
grep -i "telegram.*not installed\|no adapter" ~/.hermes/logs/gateway.log | tail -5
```

## Contexto

Esta falha ocorre tipicamente após:
- Migração de uma máquina para outra (ex: WSL → VM) onde as dependências extras não foram transferidas.
- Instalação limpa do `hermes-agent` sem o extra `[messaging]`.
- Atualização do Python/sistema que removeu o `python-telegram-bot`.
