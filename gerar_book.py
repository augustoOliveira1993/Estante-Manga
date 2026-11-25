#!/usr/bin/env python3
"""Monta um PDF ou CBZ a partir de pastas de capítulos com imagens."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
import os
import re
import sys
import tempfile
import xml.sax.saxutils
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
CHAPTER_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class Chapter:
    path: Path
    number: Decimal
    pages: list[Path]


def natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    """Ordena nomes com números como 2, 10 e 100, em vez de texto."""
    pieces = re.split(r"(\d+)", value)
    return tuple((0, int(piece)) if piece.isdigit() else (1, piece.casefold()) for piece in pieces)


def chapter_number(name: str) -> Decimal | None:
    match = CHAPTER_NUMBER.search(name)
    if not match:
        return None
    try:
        return Decimal(match.group().replace(",", "."))
    except InvalidOperation:
        return None


def chapters_in(folder: Path) -> list[Chapter]:
    chapters: list[Chapter] = []
    try:
        children = list(folder.iterdir())
    except OSError as error:
        raise RuntimeError(f"Não foi possível ler a pasta {folder}: {error}") from error

    for child in children:
        if not child.is_dir():
            continue
        number = chapter_number(child.name)
        if number is None:
            continue
        try:
            pages = [
                item for item in child.iterdir()
                if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
            ]
        except OSError as error:
            raise RuntimeError(f"Não foi possível ler o capítulo {child}: {error}") from error
        if pages:
            pages.sort(key=lambda item: (natural_key(item.name), item.name.casefold()))
            chapters.append(Chapter(child, number, pages))

    chapters.sort(key=lambda item: (item.number, item.path.name.casefold()))
    return chapters


def discover_chapters(source: Path) -> tuple[Path, list[Chapter]]:
    source = source.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"A origem não é uma pasta: {source}")

    chapters = chapters_in(source)
    if chapters:
        return source, chapters

    single_chapter_number = chapter_number(source.name)
    if single_chapter_number is not None:
        pages = [
            item for item in source.iterdir()
            if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if pages:
            pages.sort(key=lambda item: (natural_key(item.name), item.name.casefold()))
            return source, [Chapter(source, single_chapter_number, pages)]

    nested_roots: list[tuple[Path, list[Chapter]]] = []
    for child in source.iterdir():
        if child.is_dir():
            child_chapters = chapters_in(child)
            if child_chapters:
                nested_roots.append((child, child_chapters))

    if len(nested_roots) == 1:
        return nested_roots[0]
    if len(nested_roots) > 1:
        largest = max(len(chapters) for _, chapters in nested_roots)
        matches = [(root, chapters) for root, chapters in nested_roots if len(chapters) == largest]
        if len(matches) == 1:
            return matches[0]
        choices = ", ".join(str(root) for root, _ in matches)
        raise ValueError(f"Há mais de uma coleção possível ({choices}). Use --origem para escolher uma.")

    raise ValueError(
        f"Não encontrei pastas de capítulos numeradas dentro de {source}. "
        "Use --origem apontando para a pasta que contém os capítulos."
    )


def output_path(base: Path, suffix: str) -> Path:
    if base.suffix.lower() in {".pdf", ".cbz", ".epub"}:
        base = base.with_suffix("")
    return base.with_name(base.name + suffix)


def temporary_output(final_path: Path) -> Path:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=final_path.stem + "_",
        suffix=final_path.suffix + ".tmp",
        dir=final_path.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def create_run_directory(parent: Path) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_directory = parent / timestamp
    suffix = 1
    while True:
        try:
            run_directory.mkdir(parents=True, exist_ok=False)
            return run_directory
        except FileExistsError:
            run_directory = parent / f"{timestamp}_{suffix:02d}"
            suffix += 1


def make_comic_info(title: str, chapters: list[Chapter], total_pages: int) -> str:
    page = 0
    ranges: list[str] = []
    for chapter in chapters:
        first = page + 1
        page += len(chapter.pages)
        ranges.append(f"{chapter.path.name}: páginas {first}–{page}")

    notes = "\n".join(ranges)
    safe_title = xml.sax.saxutils.escape(title)
    safe_notes = xml.sax.saxutils.escape(notes)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<ComicInfo>\n"
        f"  <Title>{safe_title}</Title>\n"
        f"  <Series>{safe_title}</Series>\n"
        f"  <PageCount>{total_pages}</PageCount>\n"
        "  <LanguageISO>pt</LanguageISO>\n"
        "  <Manga>YesAndRightToLeft</Manga>\n"
        f"  <Notes>{safe_notes}</Notes>\n"
        "</ComicInfo>\n"
    )


def create_cbz(chapters: list[Chapter], destination: Path, title: str) -> None:
    temp_path = temporary_output(destination)
    page_count = 0
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for chapter in chapters:
                for page in chapter.pages:
                    page_count += 1
                    archive.write(page, arcname=f"{page_count:06d}{page.suffix.lower()}")
            archive.writestr("ComicInfo.xml", make_comic_info(title, chapters, page_count))
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def create_pdf(chapters: list[Chapter], destination: Path) -> None:
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError as error:
        raise RuntimeError(
            "Para gerar PDF, instale as dependências com: "
            "python -m pip install Pillow reportlab"
        ) from error

    temp_path = temporary_output(destination)
    try:
        document = canvas.Canvas(str(temp_path), pageCompression=1)
        for chapter in chapters:
            for page in chapter.pages:
                try:
                    with Image.open(page) as original:
                        width, height = original.size
                        scale = 792 / max(width, height)
                        page_width, page_height = width * scale, height * scale
                        if page.suffix.lower() in {".jpg", ".jpeg"}:
                            image = str(page)
                        elif "A" in original.getbands():
                            rgba = original.convert("RGBA")
                            image = Image.new("RGB", rgba.size, "white")
                            image.paste(rgba, mask=rgba.getchannel("A"))
                        else:
                            image = original.convert("RGB")
                        document.setPageSize((page_width, page_height))
                        document.drawImage(
                            image if isinstance(image, str) else ImageReader(image),
                            0,
                            0,
                            width=page_width,
                            height=page_height,
                        )
                        document.showPage()
                except Exception as error:
                    raise RuntimeError(f"Falha ao incluir a imagem {page}: {error}") from error
        document.save()
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def create_epub(chapters: list[Chapter], destination: Path, title: str) -> None:
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Para gerar EPUB, instale a dependência com: python -m pip install Pillow"
        ) from error

    temp_path = temporary_output(destination)
    manifest_items: list[str] = []
    spine_items: list[str] = []
    navigation_items: list[str] = []
    page_number = 0

    try:
        with zipfile.ZipFile(temp_path, "w") as archive:
            mimetype = zipfile.ZipInfo("mimetype")
            mimetype.compress_type = zipfile.ZIP_STORED
            archive.writestr(mimetype, "application/epub+zip")
            archive.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<container version="1.0" '
                'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                'media-type="application/oebps-package+xml"/></rootfiles></container>',
            )

            for chapter in chapters:
                first_page = page_number + 1
                for source in chapter.pages:
                    page_number += 1
                    extension = source.suffix.lower()
                    image_extension = ".png" if extension in {".bmp", ".tif", ".tiff"} else extension
                    image_media_type = {
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".png": "image/png",
                        ".webp": "image/webp",
                    }[image_extension]
                    image_name = f"{page_number:06d}{image_extension}"
                    image_href = f"images/{image_name}"

                    try:
                        with Image.open(source) as image:
                            width, height = image.size
                            if extension in {".bmp", ".tif", ".tiff"}:
                                mode = "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
                                converted = image.convert(mode)
                                buffer = BytesIO()
                                converted.save(buffer, format="PNG")
                                archive.writestr(f"OEBPS/{image_href}", buffer.getvalue())
                            else:
                                archive.write(source, arcname=f"OEBPS/{image_href}")
                    except Exception as error:
                        raise RuntimeError(
                            f"Falha ao incluir a imagem {source} no EPUB: {error}"
                        ) from error

                    page_id = f"page-{page_number:06d}"
                    image_id = f"image-{page_number:06d}"
                    page_href = f"pages/{page_number:06d}.xhtml"
                    manifest_items.append(
                        f'<item id="{image_id}" href="{image_href}" '
                        f'media-type="{image_media_type}"/>'
                    )
                    manifest_items.append(
                        f'<item id="{page_id}" href="{page_href}" '
                        'media-type="application/xhtml+xml"/>'
                    )
                    spine_items.append(f'<itemref idref="{page_id}"/>')
                    archive.writestr(
                        f"OEBPS/{page_href}",
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="pt-BR">'
                        '<head><title>Página '
                        f'{page_number}</title><meta charset="UTF-8"/>'
                        f'<meta name="viewport" content="width={width}, height={height}"/>'
                        '<link rel="stylesheet" type="text/css" href="../styles/book.css"/>'
                        '</head><body><img src="../'
                        f'{image_href}" alt="Página {page_number} do mangá"/></body></html>',
                    )

                navigation_items.append(
                    f'<li><a href="pages/{first_page:06d}.xhtml">'
                    f'{xml.sax.saxutils.escape(chapter.path.name)}</a></li>'
                )

            archive.writestr(
                "OEBPS/styles/book.css",
                "html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; "
                "background: #000; } img { display: block; width: 100%; height: 100%; }",
            )
            archive.writestr(
                "OEBPS/nav.xhtml",
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" '
                'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="pt-BR">'
                '<head><title>Sumário</title></head><body><nav epub:type="toc" id="toc">'
                '<h1>Sumário</h1><ol>'
                + "".join(navigation_items)
                + "</ol></nav></body></html>",
            )

            modified = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            escaped_title = xml.sax.saxutils.escape(title)
            package = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<package xmlns="http://www.idpf.org/2007/opf" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0" '
                'unique-identifier="pub-id" '
                'prefix="rendition: http://www.idpf.org/vocab/rendition/#">'
                '<metadata><dc:identifier id="pub-id">urn:uuid:'
                f'{uuid4()}</dc:identifier><dc:title>{escaped_title}</dc:title>'
                '<dc:language>pt-BR</dc:language>'
                f'<meta property="dcterms:modified">{modified}</meta>'
                '<meta property="rendition:layout">pre-paginated</meta></metadata>'
                '<manifest><item id="nav" href="nav.xhtml" '
                'media-type="application/xhtml+xml" properties="nav"/>'
                '<item id="css" href="styles/book.css" media-type="text/css"/>'
                + "".join(manifest_items)
                + '</manifest><spine page-progression-direction="rtl">'
                + "".join(spine_items)
                + "</spine></package>"
            )
            archive.writestr("OEBPS/content.opf", package)

        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um livro com os capítulos e páginas em ordem numérica."
    )
    parser.add_argument(
        "--origem",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="pasta com capítulos, uma coleção, ou um único capítulo com imagens",
    )
    parser.add_argument(
        "--formato",
        choices=("cbz", "pdf", "epub", "ambos"),
        default="cbz",
        help="formato de saída (EPUB exige Pillow; padrão: cbz)",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        help="caminho-base do resultado, sem extensão (padrão: nome da coleção)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        chapter_root, chapters = discover_chapters(args.origem)
        total_pages = sum(len(chapter.pages) for chapter in chapters)
        if args.saida:
            requested_base = args.saida.expanduser()
            run_directory = create_run_directory(requested_base.parent)
            base = run_directory / requested_base.name
        else:
            output_root = Path(__file__).resolve().parent / "saida"
            run_directory = create_run_directory(output_root)
            base = run_directory / chapter_root.name
        print(
            f"Coleção: {chapter_root.name} | "
            f"{len(chapters)} capítulos | {total_pages} páginas"
        )
        print(f"Ordem: {chapters[0].path.name} → {chapters[-1].path.name}")

        if args.formato in {"cbz", "ambos"}:
            destination = output_path(base, ".cbz")
            create_cbz(chapters, destination, chapter_root.name)
            print(f"CBZ criado: {destination}")

        if args.formato in {"pdf", "ambos"}:
            destination = output_path(base, ".pdf")
            create_pdf(chapters, destination)
            print(f"PDF criado: {destination}")

        if args.formato == "epub":
            destination = output_path(base, ".epub")
            create_epub(chapters, destination, chapter_root.name)
            print(f"EPUB criado: {destination}")
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
