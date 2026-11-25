# Estante Mangá

O **Estante Mangá** organiza páginas de mangá em ordem de leitura e monta um arquivo único em **CBZ** ou **PDF** usando `gerar_book.py`.

## Estrutura do projeto

```text
classificar-manga-pasta/
├── gerar_book.py             # script de geração
├── COMO_GERAR_BOOK.md        # este guia
├── .gitignore                # exclui resultados locais do Git
├── One Piece [pt-br].7z      # arquivo compactado original
├── One Piece [pt-br]/        # coleção extraída, uma pasta por capítulo
└── saida/                    # resultados gerados por execução; ignorada pelo Git
    └── 2026-11-25_14-30-00/
        └── One Piece [pt-br].cbz
```

O script e o guia ficam na pasta principal. Mantenha a coleção extraída em uma pasta própria; o arquivo `.7z` não é extraído automaticamente.

## Como a ordem é definida

- O número no nome de cada pasta define a ordem dos capítulos, por exemplo, `Capítulo 9` antes de `Capítulo 10`.
- O número no nome de cada imagem define a ordem das páginas.
- As imagens precisam estar diretamente dentro da pasta do capítulo.
- Pastas sem número ou sem imagens são ignoradas.
- O CBZ inclui a indicação de leitura da direita para a esquerda e uma lista dos intervalos de páginas por capítulo.

Extensões de imagem aceitas: `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tif` e `.tiff`.

## Início rápido no Windows

Abra o PowerShell na pasta principal do projeto. Para gerar um CBZ:

```powershell
python .\gerar_book.py --formato cbz
```

O script encontra automaticamente a pasta `One Piece [pt-br]` incluída no projeto. O CBZ pode ser usado como fonte em um conversor de quadrinhos para Kindle.

## Gerar PDF

Instale as bibliotecas necessárias uma vez:

```powershell
python -m pip install Pillow reportlab
```

Depois gere o PDF:

```powershell
python .\gerar_book.py --formato pdf
```

## Gerar EPUB para mangá

O EPUB usa uma página fixa por imagem e define a leitura da direita para a esquerda. Instale Pillow para ler as dimensões das páginas e converter imagens BMP/TIFF para PNG:

```powershell
python -m pip install Pillow
python .\gerar_book.py --formato epub
```

O EPUB é gerado em `saida/AAAA-MM-DD_HH-MM-SS/<nome da coleção>.epub`. Para Kindle, envie o EPUB pelo serviço **Enviar para o Kindle**, que faz a conversão para o formato de leitura do aparelho.

## Gerar os dois formatos

```powershell
python .\gerar_book.py --formato ambos
```

Sem `--formato`, o script gera somente CBZ. PDF requer Pillow e ReportLab; EPUB requer Pillow; CBZ usa apenas bibliotecas incluídas no Python. `--formato ambos` gera CBZ e PDF.

## Usar outra coleção ou definir o destino

`--origem` pode apontar para uma coleção com vários capítulos ou diretamente para uma pasta de capítulo com imagens. `--saida` define o nome e o local-base dos arquivos; o script cria dentro do local uma pasta com data e horário (`AAAA-MM-DD_HH-MM-SS`) e acrescenta a extensão do formato escolhido.

```powershell
python .\gerar_book.py --origem "D:\Mangas\One Piece [pt-br]" --formato ambos --saida "D:\Livros\One Piece"
```

Sem `--saida`, os arquivos são salvos em `saida/AAAA-MM-DD_HH-MM-SS/`, que está ignorada pelo Git. Para a coleção incluída, os nomes ficam como `saida/2026-11-25_14-30-00/One Piece [pt-br].cbz` e `saida/2026-11-25_14-30-00/One Piece [pt-br].pdf` (com a data e o horário reais da execução). Se duas execuções começarem no mesmo segundo, a segunda pasta recebe um sufixo numérico.

Com `--saida`, o horário é criado dentro da pasta indicada pelo caminho-base. Por exemplo, `--saida "D:\Livros\One Piece"` gera o arquivo em `D:\Livros\AAAA-MM-DD_HH-MM-SS\One Piece.cbz`. Mantenha o caminho-base dentro de `saida/` para que o Git continue ignorando o resultado; caminhos personalizados fora dela não são cobertos por essa regra.

## Problemas comuns

| Mensagem ou situação | O que fazer |
| --- | --- |
| Nenhuma pasta de capítulo encontrada | Confira se cada pasta tem o número do capítulo no nome e contém imagens diretamente nela. |
| Erro de dependência ao gerar PDF | Execute `python -m pip install Pillow reportlab`. |
| A coleção está em `.7z` | Extraia o arquivo antes de executar o script. |
| Mais de uma coleção encontrada | Informe a coleção desejada com `--origem`. |
