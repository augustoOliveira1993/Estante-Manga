#!/usr/bin/env python3
"""Monta um PDF ou CBZ a partir de pastas de capítulos com imagens."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import xml.sax.saxutils
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


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
    if base.suffix.lower() in {".pdf", ".cbz"}:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um livro com os capítulos e páginas em ordem numérica."
    )
    parser.add_argument(
        "--origem",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="pasta com os capítulos (ou a pasta que contém uma única coleção)",
    )
    parser.add_argument(
        "--formato",
        choices=("cbz", "pdf", "ambos"),
        default="cbz",
        help="cbz não exige bibliotecas adicionais e pode ser convertido para Kindle (padrão: cbz)",
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
        base = (
            args.saida.expanduser()
            if args.saida
            else Path(__file__).resolve().parent / "saida" / chapter_root.name
        )
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
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
