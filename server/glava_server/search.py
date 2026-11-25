"""Поиск по утверждениям: без учёта регистра и «ё», все слова запроса должны встретиться."""

from collections.abc import Iterator, Sequence
from typing import Any

from glava_server.jsonstore import rows
from glava_server.repository import ChapterInfo, Repository
from glava_server.schemas import FoundClaim

MIN_QUERY = 2


def normalized(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def _found(chapter_id: str, node: dict[str, Any], claim: dict[str, Any]) -> FoundClaim:
    page = claim.get("page_pdf")
    return FoundClaim(chapter=chapter_id, node_id=node["id"], node_title=str(node.get("title") or node["id"]), claim_id=str(claim.get("id") or ""),
                      text=str(claim.get("text") or ""), quote=str(claim.get("quote") or ""), page_pdf=page if isinstance(page, int) else None)


def _claims(repository: Repository, chapters: Sequence[ChapterInfo]) -> Iterator[FoundClaim]:
    for chapter in chapters:
        for node in repository.nodes(chapter.id):
            yield from (_found(chapter.id, node, claim) for claim in rows(node.get("claims")))


def search_claims(repository: Repository, chapters: Sequence[ChapterInfo], query: str) -> list[FoundClaim]:
    words = normalized(query).split()

    def matches(claim: FoundClaim) -> bool:
        text = normalized(f"{claim.text} {claim.quote}")
        return all(word in text for word in words)

    return [c for c in _claims(repository, chapters) if matches(c)]
