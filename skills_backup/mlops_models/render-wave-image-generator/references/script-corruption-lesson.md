# Lição: Corrupção por Patches Acumulados

## Contexto
Durante a sessão de 2026-05-07, o script `generate_image.py` foi corrigido múltiplas vezes via patches incrementais. Cada patch corrigia um problema mas introduzia corrupção estrutural:

- Indentação inconsistente (blocos `for`/`try` mal alinhados)
- Código duplicado (3 linhas `requests.post()` idênticas consecutivas)
- `except` sem `try` correspondente
- Parsing de `history['outputs']` iterando sobre strings em vez de dicts

## Sintomas de Script Corrompido
- `IndentationError` ou estruturas de controlo mal formadas
- Código que "parece" correcto mas o Python rejeita
- Múltiplas declarações da mesma linha
- Mix de tabs e spaces
- Referências a variáveis que não existem no scope

## Regra de Ouro
> **Se um script foi patchado 2+ vezes e continua com erros estruturais, NÃO aplique mais patches. Reescreva o ficheiro inteiro do zero.**

## Porquê Reescrever?
- Patches são lineares — cada um assume que o anterior está correcto
- Quando um patch falha parcialmente, o estado intermédio é "meio aplicado"
- Analisar o que está "meio aplicado" consome mais tempo do que reescrever
- Reescrever garante coerência estrutural total

## Como Reescrever de Forma Segura
1. Ler o ficheiro original APENAS para extrair a lógica/intenção
2. Ler o workflow JSON para confirmar node IDs
3. Escrever o novo script numa localização temporária
4. Validar sintaxe com `python -m py_compile`
5. Testar com um prompt simples
6. Só depois substituir o ficheiro original

## Lição da Sessão
O script foi reescrito em 10 minutos e funcionou à primeira. Os patches anteriores consumiram 45+ minutos e produziram corrupção progressiva.
