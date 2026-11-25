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
└── saida/                    # resultados gerados; ignorada pelo Git
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

## Gerar os dois formatos

```powershell
python .\gerar_book.py --formato ambos
```

Sem `--formato`, o script gera somente CBZ. A criação de PDF requer Pillow e ReportLab; o CBZ usa apenas bibliotecas incluídas no Python.

## Usar outra coleção ou definir o destino

`--origem` aponta para a pasta da coleção. `--saida` define um caminho-base para os arquivos; o script acrescenta `.cbz` e/ou `.pdf`.

```powershell
python .\gerar_book.py --origem "D:\Mangas\One Piece [pt-br]" --formato ambos --saida "D:\Livros\One Piece"
```

Sem `--saida`, os arquivos são salvos em `saida/`, que está ignorada pelo Git. Para a coleção incluída, os nomes são `saida/One Piece [pt-br].cbz` e `saida/One Piece [pt-br].pdf`.

Se usar `--saida`, mantenha o caminho dentro de `saida/` para que o Git continue ignorando o resultado. Um caminho personalizado fora dessa pasta não é coberto por essa regra.

## Problemas comuns

| Mensagem ou situação | O que fazer |
| --- | --- |
| Nenhuma pasta de capítulo encontrada | Confira se cada pasta tem o número do capítulo no nome e contém imagens diretamente nela. |
| Erro de dependência ao gerar PDF | Execute `python -m pip install Pillow reportlab`. |
| A coleção está em `.7z` | Extraia o arquivo antes de executar o script. |
| Mais de uma coleção encontrada | Informe a coleção desejada com `--origem`. |
