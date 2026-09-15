from __future__ import annotations

import argparse
import json
import sys

from sqlmodel import Session

from .crud import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    related_documents,
    set_related_documents,
    update_document,
)
from .database import engine, init_db
from .storage import read_document


def _json_document(session: Session, document, include_content: bool = True) -> dict:
    result = {
        "id": int(document.id),
        "name": document.name,
        "related_docs": [
            {"id": int(item.id), "name": item.name}
            for item in related_documents(session, int(document.id))
        ],
    }
    if include_content:
        result["content"] = read_document(document.name)
    return result


def _read_content(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as handle:
            return handle.read()
    if args.content is not None:
        return args.content
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sandbox.cli",
        description="Manage the sandbox document relationship dataset.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List documents")
    list_parser.add_argument("--query", help="Filter by name")

    create_parser = subparsers.add_parser("create", help="Create a document file")
    create_parser.add_argument("name", help="File name, for example report.md")
    create_parser.add_argument("--subfolder", help="Optional folder under documents/")
    create_parser.add_argument("--content", help="Document content")
    create_parser.add_argument("--file", help="Read content from an existing file")
    create_parser.add_argument("--related", nargs="*", type=int, default=[])

    show_parser = subparsers.add_parser("show", help="Show a document and its links")
    show_parser.add_argument("id", type=int)

    update_parser = subparsers.add_parser("update", help="Update a document")
    update_parser.add_argument("id", type=int)
    update_parser.add_argument("--name")
    update_parser.add_argument("--subfolder")
    update_parser.add_argument("--content")
    update_parser.add_argument("--file")
    update_parser.add_argument("--related", nargs="*", type=int)

    delete_parser = subparsers.add_parser("delete", help="Delete a document and its file")
    delete_parser.add_argument("id", type=int)

    link_parser = subparsers.add_parser("link", help="Link two documents")
    link_parser.add_argument("id", type=int)
    link_parser.add_argument("related_id", type=int)

    unlink_parser = subparsers.add_parser("unlink", help="Remove a relationship")
    unlink_parser.add_argument("id", type=int)
    unlink_parser.add_argument("related_id", type=int)
    return parser


def run(args: argparse.Namespace) -> dict | list[dict] | None:
    init_db()
    with Session(engine) as session:
        if args.command == "list":
            documents = list_documents(session, args.query)
            return [
                _json_document(session, doc, include_content=False)
                for doc in documents
            ]
        if args.command == "create":
            document = create_document(
                session,
                name=args.name,
                subfolder=args.subfolder,
                content=_read_content(args),
                related_ids=args.related,
            )
            return _json_document(session, document)
        if args.command == "show":
            return _json_document(session, get_document(session, args.id))
        if args.command == "update":
            has_content = args.content is not None or args.file is not None
            document = update_document(
                session,
                args.id,
                name=args.name,
                subfolder=args.subfolder,
                content=_read_content(args) if has_content else None,
                related_ids=args.related,
            )
            return _json_document(session, document)
        if args.command == "delete":
            delete_document(session, args.id)
            return None
        if args.command in {"link", "unlink"}:
            document = get_document(session, args.id)
            current = {int(item.id) for item in related_documents(session, args.id)}
            if args.command == "link":
                get_document(session, args.related_id)
                current.add(args.related_id)
            else:
                current.discard(args.related_id)
            set_related_documents(session, args.id, current)
            return _json_document(session, document)
    raise ValueError(f"Unknown command: {args.command}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as error:
        parser.error(str(error))
        return 2
    if result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
