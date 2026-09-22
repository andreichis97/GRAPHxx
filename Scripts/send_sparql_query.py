"""Execute SPARQL directly against GraphDB, without an LLM.

Usage: python send_sparql_query.py --request-file sparql_query_request.txt
The UTF-8 request contains a repository name on line 1 and complete SPARQL below.
Results overwrite sparql_query_results.txt beside this script. Supports SPARQL
1.1 query and update forms, including semicolon-separated update operations.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate
from SPARQLWrapper import INSERT, JSON, POST, RDFXML, SPARQLWrapper

RESULTS_PATH = Path(__file__).resolve().with_name("sparql_query_results.txt")


def save_result(text: str) -> bool:
    try:
        RESULTS_PATH.write_text(text + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        print(f"ERROR: Cannot write {RESULTS_PATH}: {exc}", file=sys.stderr)
        return False


class ResultParser(argparse.ArgumentParser):
    def error(self, message):
        save_result(f"ERROR: {message}")
        super().error(message)


def read_request(path: str) -> tuple[str, str]:
    text = Path(path).read_text(encoding="utf-8-sig")
    repository, separator, query = text.partition("\n")
    repository = repository.strip()
    if not separator or not query.strip():
        raise ValueError("Enter a repository on line 1 and the complete SPARQL query below it.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", repository):
        raise ValueError("Repository names may contain only letters, digits, underscores and hyphens.")
    return repository, query


def classify(query: str) -> str:
    """Parse syntax, including comments/PREFIX/BASE, instead of guessing keywords."""
    try:
        parsed = parseQuery(query)
        return {"SelectQuery": "SELECT", "AskQuery": "ASK",
                "ConstructQuery": "CONSTRUCT", "DescribeQuery": "DESCRIBE"}[parsed[1].name]
    except Exception:
        pass
    try:
        parsed = parseUpdate(query)
        if "request" not in parsed or len(parsed["request"]) == 0:
            raise ValueError("Empty update")
        return "UPDATE"
    except Exception as exc:
        raise ValueError("Invalid SPARQL 1.1 query or update. Check syntax, prefixes and braces.") from exc


def format_binding(binding: dict | None) -> str:
    if binding is None:
        return "(unbound)"
    kind, value = binding["type"], binding["value"]
    if kind == "uri":
        return URIRef(value).n3()
    if kind == "bnode":
        return BNode(value).n3()
    if kind in ("literal", "typed-literal"):
        datatype = binding.get("datatype")
        return Literal(value, lang=binding.get("xml:lang"),
                       datatype=URIRef(datatype) if datatype else None, normalize=False).n3()
    raise ValueError(f"Unsupported result term type: {kind}")


def format_select(data: dict) -> str:
    variables = data["head"]["vars"]
    rows = data["results"]["bindings"]
    lines = [f"Rows returned: {len(rows)}"]
    if not rows:
        lines.append("No matching results.")
    # Record layout keeps long URIs and multiline literals readable without truncation.
    for index, row in enumerate(rows, 1):
        lines.append(f"\nResult {index}")
        for variable in variables:
            value = format_binding(row.get(variable)).replace("\n", "\n    ")
            lines.append(f"  {variable}: {value}")
    return "\n".join(lines)


def execute(repository: str, query: str, server_url: str, timeout: int) -> str:
    form = classify(query)
    endpoint = f"{server_url.rstrip('/')}/repositories/{repository}"
    client = SPARQLWrapper(endpoint, updateEndpoint=endpoint + "/statements")
    client.setMethod(POST)
    client.setTimeout(timeout)
    client.setQuery(query)
    # Explicit classification avoids wrapper keyword heuristics misrouting WITH,
    # comments, strings containing keywords, and compound update requests.
    client.queryType = INSERT if form == "UPDATE" else form
    if form != "UPDATE":
        client.setReturnFormat(JSON if form in ("SELECT", "ASK") else RDFXML)
    header = f"Repository: {repository}\nOperation: {form}\n"
    try:
        response = client.query()
        try:
            if form == "UPDATE":
                response.response.read()
                return header + "\nUpdate request completed successfully.\nThe server does not report an affected-triple count."
            data = response.convert()
        finally:
            response.response.close()
    except Exception as exc:
        detail = str(exc).strip() or type(exc).__name__
        if form == "UPDATE":
            detail += ("\nIf the connection failed after submission, the update may have been applied. "
                       "Check repository state before resubmitting. No automatic retry was performed.")
        raise RuntimeError(header + "\n" + detail) from exc
    if form == "SELECT":
        return header + "\n" + format_select(data)
    if form == "ASK":
        answer = data["boolean"]
        if not isinstance(answer, bool):
            raise ValueError("The server returned an invalid ASK response.")
        return header + ("\nAnswer: YES (true)" if answer else "\nAnswer: NO (false)")
    if not isinstance(data, Graph):
        raise ValueError("The server did not return an RDF graph.")
    triples = sorted(" ".join(term.n3() for term in triple) + " ." for triple in data)
    return header + f"\nTriples returned: {len(triples)}\n\n" + (
        "\n".join(triples) if triples else "The result graph is empty.")


def main() -> int:
    parser = ResultParser(description=__doc__)
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--server-url", default="http://localhost:7200")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        if args.timeout < 1:
            raise ValueError("Timeout must be positive.")
        repository, query = read_request(args.request_file)
        output = execute(repository, query, args.server_url, args.timeout)
        success = True
    except Exception as exc:
        output = f"ERROR: {str(exc).strip() or type(exc).__name__}"
        success = False
    saved = save_result(output)
    print(output)
    return 0 if success and saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
