#!/usr/bin/env python3
"""Prepare a small reproducible real-text MIRACL corpus; does not launch eval."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import logging
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(EVAL_DIR))

from corpus import RESTRICTED_DOC_IDS  # noqa: E402
from dataset import load_golden_dataset  # noqa: E402

logger = logging.getLogger("eval.prepare_miracl")

TOPICS_REVISION = "5be20db"
CORPUS_REVISION = "a7362f0b9d54dce8a8af3cd42a8cf2a5ef570475"
LANGUAGES = ("en", "ru")
DEFAULT_QUERIES_PER_LANGUAGE = 20
DEFAULT_MAX_ARTICLE_ID = 500_000
DEFAULT_NEGATIVES_PER_QUERY = 3
MIRACL_DATASET_URL = "https://huggingface.co/datasets/miracl/miracl/resolve"
MIRACL_CORPUS_URL = "https://huggingface.co/datasets/miracl/miracl-corpus/resolve"
USER_AGENT = "Docwise-RAG-Eval/1.0 (local research evaluation)"
DOCID_RE = re.compile(r"^(?P<article>[0-9]+)#(?P<passage>[0-9]+)$")


class PreparationError(RuntimeError):
    """Raised when the pinned source cannot produce a complete subset."""


def _request(url: str, *, timeout: int = 120):
    return urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def _download_bytes(url: str) -> bytes:
    try:
        with _request(url) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise PreparationError("Could not download a pinned MIRACL metadata file") from exc


def _download_topics_and_qrels(
    output_dir: Path, lang: str
) -> tuple[dict[str, str], dict[str, list[tuple[str, int]]]]:
    source_dir = output_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    base = f"miracl-v1.0-{lang}"
    topics_rel = f"{base}/topics/topics.miracl-v1.0-{lang}-dev.tsv"
    qrels_rel = f"{base}/qrels/qrels.miracl-v1.0-{lang}-dev.tsv"
    topics_path = source_dir / f"{lang}-dev-topics.tsv"
    qrels_path = source_dir / f"{lang}-dev-qrels.tsv"
    if not topics_path.exists():
        topics_path.write_bytes(
            _download_bytes(f"{MIRACL_DATASET_URL}/{TOPICS_REVISION}/{topics_rel}?download=true")
        )
    if not qrels_path.exists():
        qrels_path.write_bytes(
            _download_bytes(f"{MIRACL_DATASET_URL}/{TOPICS_REVISION}/{qrels_rel}?download=true")
        )

    topics: dict[str, str] = {}
    for line in topics_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 1)
        if len(fields) != 2 or not fields[0] or not fields[1].strip():
            raise PreparationError(f"Malformed MIRACL topic row for {lang}")
        topics[fields[0]] = fields[1].strip()

    qrels: dict[str, list[tuple[str, int]]] = {qid: [] for qid in topics}
    for line in qrels_path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 4:
            raise PreparationError(f"Malformed MIRACL qrel row for {lang}")
        qid, _iteration, docid, raw_relevance = fields
        if qid not in qrels:
            continue
        if DOCID_RE.fullmatch(docid) is None:
            raise PreparationError(f"Malformed MIRACL passage id for {lang}")
        relevance = int(raw_relevance)
        if relevance not in {0, 1}:
            raise PreparationError(f"Unexpected MIRACL relevance label for {lang}")
        qrels[qid].append((docid, relevance))
    return topics, qrels


def _article_id(docid: str) -> int:
    match = DOCID_RE.fullmatch(docid)
    if match is None:
        raise PreparationError("Malformed MIRACL passage id")
    return int(match.group("article"))


def _passage_index(docid: str) -> int:
    match = DOCID_RE.fullmatch(docid)
    if match is None:
        raise PreparationError("Malformed MIRACL passage id")
    return int(match.group("passage"))


def _select_cases(
    lang: str,
    topics: dict[str, str],
    qrels: dict[str, list[tuple[str, int]]],
    *,
    count: int,
    max_article_id: int,
    negatives_per_query: int,
    sample_seed: str,
) -> list[dict[str, object]]:
    candidates: list[tuple[str, str, list[str]]] = []
    for qid, question in topics.items():
        rows = qrels[qid]
        positives = [docid for docid, relevance in rows if relevance == 1]
        if len(positives) != 1 or _article_id(positives[0]) > max_article_id:
            continue
        positive = positives[0]
        negative_ids = sorted(
            {
                docid
                for docid, relevance in rows
                if relevance == 0
                and docid != positive
                and _article_id(docid) <= max_article_id
            },
            key=lambda docid: (_article_id(docid), _passage_index(docid)),
        )
        if len(negative_ids) < min(2, negatives_per_query):
            continue
        candidates.append((qid, positive, negative_ids[:negatives_per_query]))

    candidates.sort(
        key=lambda row: hashlib.sha256(f"{sample_seed}:{lang}:{row[0]}".encode()).hexdigest()
    )
    if len(candidates) < count:
        raise PreparationError(
            f"Only {len(candidates)} eligible {lang} topics; requested {count}. "
            "Increase max article ID or reduce sample size."
        )

    return [
        {
            "language": lang,
            "query_id": qid,
            "question": topics[qid],
            "positive_docid": positive,
            "negative_docids": negatives,
        }
        for qid, positive, negatives in candidates[:count]
    ]


def _dataset_files(revision: str) -> list[str]:
    next_url: str | None = (
        f"https://huggingface.co/api/datasets/miracl/miracl-corpus/tree/{revision}"
        "?recursive=true&expand=true"
    )
    paths: list[str] = []
    while next_url:
        try:
            with _request(next_url) as response:
                rows = json.load(response)
                link = response.headers.get("Link", "")
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PreparationError("Could not list pinned MIRACL corpus shards") from exc
        paths.extend(
            row["path"]
            for row in rows
            if isinstance(row, dict) and str(row.get("path", "")).endswith(".jsonl.gz")
        )
        next_url = link[1:link.index(">")] if 'rel="next"' in link else None
    return paths


def _shard_number(path: str) -> int:
    match = re.search(r"/docs-(\d+)\.jsonl\.gz$", path)
    if match is None:
        raise PreparationError("Unexpected MIRACL corpus shard path")
    return int(match.group(1))


def _collect_passages(
    lang: str,
    selected: list[dict[str, object]],
    *,
    revision: str,
) -> dict[str, dict[str, str]]:
    wanted = {
        str(docid)
        for case in selected
        for docid in [case["positive_docid"], *case["negative_docids"]]
    }
    max_target_article = max(_article_id(docid) for docid in wanted)
    paths = [
        path
        for path in _dataset_files(revision)
        if path.startswith(f"miracl-corpus-v1.0-{lang}/")
    ]
    paths.sort(key=_shard_number)
    if not paths:
        raise PreparationError(f"No pinned corpus shards found for {lang}")

    found: dict[str, dict[str, str]] = {}
    last_article = -1
    for path in paths:
        url = f"{MIRACL_CORPUS_URL}/{revision}/{path}?download=true"
        logger.info("Scanning MIRACL %s shard docs-%s", lang, _shard_number(path))
        stop_after_shard = False
        try:
            with _request(url) as response:
                with gzip.GzipFile(fileobj=response, mode="rb") as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        docid = str(row.get("docid", ""))
                        article = _article_id(docid)
                        if article < last_article:
                            raise PreparationError(
                                "MIRACL corpus ordering changed; bounded streaming scan is unsafe"
                            )
                        last_article = article
                        if article > max_target_article:
                            stop_after_shard = True
                            break
                        if docid in wanted:
                            title = str(row.get("title", "")).strip()
                            text = " ".join(str(row.get("text", "")).split())
                            if not title or not text:
                                raise PreparationError("MIRACL selected passage is empty")
                            found[docid] = {"title": title, "text": text}
                            if len(found) == len(wanted):
                                stop_after_shard = True
                                break
            if stop_after_shard:
                break
        except PreparationError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise PreparationError(f"Could not scan pinned MIRACL shard {path}") from exc

    missing = sorted(wanted - set(found))
    if missing:
        raise PreparationError(
            f"MIRACL corpus is missing {len(missing)} selected passages; no evaluation set was written"
        )
    return found


def _document_uuid(lang: str, article_id: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://{lang}.wikipedia.org/?curid={article_id}"))


def _build_docx(lang: str, article_id: int, title: str, passages: dict[str, dict[str, str]]) -> bytes:
    from io import BytesIO
    from docx import Document

    doc = Document()
    doc.core_properties.title = f"MIRACL {lang.upper()} — {title}"
    doc.core_properties.subject = "Selected human-judged Wikipedia passages from MIRACL"
    doc.core_properties.comments = (
        f"Source: https://{lang}.wikipedia.org/?curid={article_id}; "
        "Wikipedia text is CC BY-SA 4.0 (GFDL may also apply). "
        "Original passages are grouped by article without paraphrasing."
    )
    for docid, item in sorted(passages.items(), key=lambda pair: _passage_index(pair[0])):
        doc.add_heading(f"MIRACL passage {docid}", level=1)
        doc.add_paragraph(item["text"])
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


def prepare(
    *,
    output_dir: Path,
    queries_per_language: int = DEFAULT_QUERIES_PER_LANGUAGE,
    max_article_id: int = DEFAULT_MAX_ARTICLE_ID,
    negatives_per_query: int = DEFAULT_NEGATIVES_PER_QUERY,
    sample_seed: str = "docwise-2026-10",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_by_language: dict[str, list[dict[str, object]]] = {}
    passages_by_language: dict[str, dict[str, dict[str, str]]] = {}
    for lang in LANGUAGES:
        topics, qrels = _download_topics_and_qrels(output_dir, lang)
        selected = _select_cases(
            lang,
            topics,
            qrels,
            count=queries_per_language,
            max_article_id=max_article_id,
            negatives_per_query=negatives_per_query,
            sample_seed=sample_seed,
        )
        selected_by_language[lang] = selected
        passages_by_language[lang] = _collect_passages(lang, selected, revision=CORPUS_REVISION)

    articles: dict[tuple[str, int], dict[str, object]] = {}
    for lang in LANGUAGES:
        for docid, passage in passages_by_language[lang].items():
            article_id = _article_id(docid)
            article = articles.setdefault(
                (lang, article_id), {"title": passage["title"], "passages": {}, "docids": set()}
            )
            if article["title"] != passage["title"]:
                raise PreparationError("One MIRACL article ID maps to multiple titles")
            article["passages"][docid] = passage
            article["docids"].add(docid)

    documents_dir = output_dir / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    manifest_documents: list[dict[str, object]] = []
    for (lang, article_id), article in sorted(articles.items()):
        identifier = _document_uuid(lang, article_id)
        filename = f"{identifier}.docx"
        data = _build_docx(lang, article_id, str(article["title"]), article["passages"])
        relative_path = f"documents/{filename}"
        (documents_dir / filename).write_bytes(data)
        manifest_documents.append(
            {
                "id": identifier,
                "title": f"MIRACL {lang.upper()} — {article['title']}",
                "filename": filename,
                "relative_path": relative_path,
                "sha256": hashlib.sha256(data).hexdigest(),
                "access_roles": ["all"],
                "language": lang,
                "wikipedia_page_id": article_id,
                "source_url": f"https://{lang}.wikipedia.org/?curid={article_id}",
                "source_license": "CC BY-SA 4.0; GFDL may also apply",
                "miracl_docids": sorted(article["docids"]),
            }
        )

    article_uuid = {
        (str(document["language"]), int(document["wikipedia_page_id"])): str(document["id"])
        for document in manifest_documents
    }
    selected_cases: list[dict[str, object]] = []
    for lang in LANGUAGES:
        for case in selected_by_language[lang]:
            positive_docid = str(case["positive_docid"])
            article_id = _article_id(positive_docid)
            selected_case = {
                **case,
                "id": f"miracl-{lang}-{case['query_id']}",
                "target_doc_id": article_uuid[(lang, article_id)],
                "target_section": f"MIRACL passage {positive_docid}",
                "ground_truth_answer": passages_by_language[lang][positive_docid]["text"],
                "must_not_doc_ids": list(RESTRICTED_DOC_IDS),
                "eval_user_email": None,
                "kind": "positive",
                "source_dataset": "MIRACL v1.0 dev",
                "source_qid": str(case["query_id"]),
            }
            selected_cases.append(selected_case)

    base_path = EVAL_DIR / "golden_dataset.json"
    base = json.loads(base_path.read_text(encoding="utf-8"))
    combined = {
        "eval_user_email": base["eval_user_email"],
        "items": [*base["items"], *selected_cases],
    }
    combined_path = output_dir / "golden_dataset.json"
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest: dict[str, object] = {
        "source": "MIRACL v1.0 dev topics and human qrels; English and Russian Wikipedia passages",
        "prepared_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topics_qrels_revision": TOPICS_REVISION,
        "corpus_revision": CORPUS_REVISION,
        "metadata_sha256": {
            f"{lang}_{kind}": hashlib.sha256(
                (output_dir / "source" / f"{lang}-dev-{kind}.tsv").read_bytes()
            ).hexdigest()
            for lang in LANGUAGES
            for kind in ("topics", "qrels")
        },
        "query_selection": {
            "languages": list(LANGUAGES),
            "queries_per_language": queries_per_language,
            "max_wikipedia_article_id": max_article_id,
            "negative_passages_per_query": negatives_per_query,
            "stable_sample_seed": sample_seed,
            "eligibility": "exactly one positive passage and at least two judged negatives within the article-ID bound",
        },
        "licenses": {
            "miracl_metadata": "Apache-2.0 (Hugging Face dataset card); MIRACL paper CC BY 4.0",
            "wikipedia_text": "CC BY-SA 4.0; GFDL may also apply",
            "transformations": "Original text grouped by article into DOCX passage sections without paraphrasing",
        },
        "combined_golden_dataset": combined_path.name,
        "documents": manifest_documents,
        "selected_queries": [
            {
                "id": case["id"],
                "language": case["language"],
                "source_qid": case["source_qid"],
                "question": case["question"],
                "positive_docid": case["positive_docid"],
                "negative_docids": case["negative_docids"],
            }
            for case in selected_cases
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=EVAL_DIR / "local_data" / "miracl")
    parser.add_argument("--queries-per-language", type=int, default=DEFAULT_QUERIES_PER_LANGUAGE)
    parser.add_argument("--max-article-id", type=int, default=DEFAULT_MAX_ARTICLE_ID)
    parser.add_argument("--negatives-per-query", type=int, default=DEFAULT_NEGATIVES_PER_QUERY)
    parser.add_argument("--sample-seed", default="docwise-2026-10")
    args = parser.parse_args(argv)
    if args.queries_per_language < 1 or args.max_article_id < 1 or args.negatives_per_query < 2:
        parser.error("sample size and article ID bound must be positive; use at least two negatives")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        manifest = prepare(
            output_dir=args.output_dir,
            queries_per_language=args.queries_per_language,
            max_article_id=args.max_article_id,
            negatives_per_query=args.negatives_per_query,
            sample_seed=args.sample_seed,
        )
        dataset = load_golden_dataset(args.output_dir / "golden_dataset.json")
    except (PreparationError, ValueError, OSError) as exc:
        logger.error("MIRACL preparation failed: %s", exc)
        return 2
    logger.info(
        "Prepared %s real MIRACL cases across %s documents; combined dataset has %s cases",
        len(manifest["selected_queries"]),
        len(manifest["documents"]),
        len(dataset.items),
    )
    logger.info("Prepared files under %s; no evaluation was launched", args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
