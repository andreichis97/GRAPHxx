#!/usr/bin/env python3
"""Convert Turtle or TriG RDF fragments to the GRAPHxx line transport format."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Literal as TypingLiteral, Sequence
from urllib.parse import urlsplit

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import OWL, RDF, RDFS, XSD
from rdflib.term import Identifier, Node
from rdflib.util import from_n3

CONVERTER_SCHEMA_REVISION = "ATTRIBUTE_AND_EDGE_NODE_GRAPHXX_CLASS_V2"
#PROPERTY_GRAPHXX_CLASS = "ThingIdentifier"
PROPERTY_GRAPHXX_CLASS = "Property"
ABSENT_VALUE = "-"
FIELD_SEPARATOR = "|"
CANONICAL_RDF_PREFIX = "rdf:"
CANONICAL_RDF_NAMESPACE = str(RDF)
INTERNAL_BNODE_LABEL_PREDICATE = URIRef(
    "urn:graphxx:internal:explicit-bnode-label"
)

SPECIAL_CONNECTOR_KINDS: dict[URIRef, str] = {
    RDF.type: "TYPE",
    RDFS.domain: "DOMAIN",
    RDFS.range: "RANGE",
    RDFS.subPropertyOf: "SUBPROPERTY",
    RDFS.subClassOf: "SUBCLASS",
    OWL.sameAs: "SAME_AS",
}

PROPERTY_TYPE_OBJECTS = {
    RDF.Property,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
}

CLASS_TYPE_OBJECTS = {OWL.Class, RDFS.Class}
CONTAINER_TYPE_OBJECTS = {RDF.Bag, RDF.Seq, RDF.Alt}
OWL_CLASS_CONSTRUCT_PREDICATES = {
    OWL.unionOf,
    OWL.intersectionOf,
    OWL.complementOf,
    OWL.oneOf,
    OWL.equivalentClass,
    OWL.disjointWith,
    OWL.disjointUnionOf,
}

# XML Schema 1.0/1.1 built-in datatypes commonly exposed by RDFLib.
RECOGNIZED_XSD_DATATYPES = {
    URIRef(str(XSD) + local)
    for local in {
        "anyAtomicType",
        "anySimpleType",
        "anyType",
        "anyURI",
        "base64Binary",
        "boolean",
        "byte",
        "date",
        "dateTime",
        "dateTimeStamp",
        "dayTimeDuration",
        "decimal",
        "double",
        "duration",
        "ENTITIES",
        "ENTITY",
        "float",
        "gDay",
        "gMonth",
        "gMonthDay",
        "gYear",
        "gYearMonth",
        "hexBinary",
        "ID",
        "IDREF",
        "IDREFS",
        "int",
        "integer",
        "language",
        "long",
        "Name",
        "NCName",
        "negativeInteger",
        "NMTOKEN",
        "NMTOKENS",
        "nonNegativeInteger",
        "nonPositiveInteger",
        "normalizedString",
        "NOTATION",
        "positiveInteger",
        "QName",
        "short",
        "string",
        "time",
        "token",
        "unsignedByte",
        "unsignedInt",
        "unsignedLong",
        "unsignedShort",
        "yearMonthDuration",
    }
}

LOGGER = logging.getLogger("rdf_to_graphxx")


class GraphXXError(Exception):
    """A conversion, parsing, or validation error with a stable category."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class SourceToken:
    kind: str
    text: str
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class PrefixDecl:
    prefix: str
    namespace: str
    source_order: int
    generated: bool = False


@dataclass(frozen=True)
class GraphBlock:
    label_token: SourceToken | None
    open_start: int
    open_end: int
    close_start: int
    close_end: int


@dataclass
class SourceScan:
    tokens: list[SourceToken]
    prefixes: list[PrefixDecl]
    uses_a_shorthand: bool
    has_base_directive: bool
    explicit_bnode_labels: list[str]
    graph_blocks: list[GraphBlock]


@dataclass(frozen=True)
class QNameParts:
    qname: str
    prefix: str
    local: str


@dataclass(frozen=True)
class GraphRecord:
    full_graph_iri: str
    graph_qname: str
    graph_qname_prefix: str
    graph_qname_local_identifier: str

    def fields(self) -> tuple[str, ...]:
        return (
            "GRAPH",
            self.full_graph_iri,
            self.graph_qname,
            self.graph_qname_prefix,
            self.graph_qname_local_identifier,
        )


@dataclass(frozen=True)
class PrefixRecord:
    prefix: str
    namespace: str

    def fields(self) -> tuple[str, ...]:
        return ("PREFIX", self.prefix, self.namespace)


@dataclass(frozen=True)
class NodeRecord:
    rdf_term_type: str
    graphxx_class: str
    node_reference: str
    qname_prefix: str
    qname_local_identifier: str

    def fields(self) -> tuple[str, ...]:
        return (
            "NODE",
            self.rdf_term_type,
            self.graphxx_class,
            self.node_reference,
            self.qname_prefix,
            self.qname_local_identifier,
        )


@dataclass(frozen=True)
class AttributeRecord:
    owner_node_reference: str
    owner_graphxx_class: str
    predicate_qname: str
    predicate_qname_prefix: str
    predicate_qname_local_identifier: str
    lexical_value: str
    datatype_qname: str
    language: str

    def fields(self) -> tuple[str, ...]:
        return (
            "ATTRIBUTE",
            self.owner_node_reference,
            self.owner_graphxx_class,
            self.predicate_qname,
            self.predicate_qname_prefix,
            self.predicate_qname_local_identifier,
            self.lexical_value,
            self.datatype_qname,
            self.language,
        )


@dataclass(frozen=True)
class EdgeRecord:
    source_node_reference: str
    source_node_graphxx_class: str
    target_node_reference: str
    target_node_graphxx_class: str
    predicate_qname: str
    predicate_qname_prefix: str
    predicate_qname_local_identifier: str
    connector_kind: str

    def fields(self) -> tuple[str, ...]:
        return (
            "EDGE",
            self.source_node_reference,
            self.source_node_graphxx_class,
            self.target_node_reference,
            self.target_node_graphxx_class,
            self.predicate_qname,
            self.predicate_qname_prefix,
            self.predicate_qname_local_identifier,
            self.connector_kind,
        )


Record = GraphRecord | PrefixRecord | NodeRecord | AttributeRecord | EdgeRecord


@dataclass
class RoleEvidence:
    container: set[str] = field(default_factory=set)
    datatype: set[str] = field(default_factory=set)
    thing_type: set[str] = field(default_factory=set)
    property_resource: set[str] = field(default_factory=set)

    def active_roles(self) -> list[str]:
        roles: list[str] = []
        if self.container:
            roles.append("Container")
        if self.datatype:
            roles.append("DatatypeNode")
        if self.thing_type:
            roles.append("ThingType")
        if self.property_resource:
            roles.append("Property")
        return roles


@dataclass(frozen=True)
class ParsedInput:
    syntax: TypingLiteral["turtle", "trig"]
    graph: Graph
    graph_identifier: URIRef | None


def read_source_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GraphXXError("input-encoding", f"Input is not valid UTF-8: {exc}") from exc
    except OSError as exc:
        raise GraphXXError("input-io", f"Cannot read input file: {exc}") from exc


def _scan_quoted(source: str, start: int, quote: str) -> int:
    triple = source.startswith(quote * 3, start)
    delimiter = quote * (3 if triple else 1)
    i = start + len(delimiter)
    while i < len(source):
        if source.startswith(delimiter, i):
            return i + len(delimiter)
        if source[i] == "\\":
            i += 2
        else:
            i += 1
    raise GraphXXError("source-scan", f"Unterminated string beginning at character {start}")


def tokenize_source(source: str) -> list[SourceToken]:
    """Tokenize directives and structural syntax without parsing RDF triples."""

    tokens: list[SourceToken] = []
    punctuation = set("{}[]();,.")
    word_stoppers = set("#<>\"'{}[]();,")
    i = 0
    length = len(source)

    while i < length:
        char = source[i]
        if char.isspace():
            i += 1
            continue
        if char == "#":
            newline = source.find("\n", i)
            i = length if newline < 0 else newline + 1
            continue
        if char == "<":
            start = i
            i += 1
            escaped = False
            while i < length:
                current = source[i]
                if current == ">" and not escaped:
                    i += 1
                    text = source[start:i]
                    try:
                        parsed = from_n3(text)
                    except Exception as exc:  # RDFLib supplies the precise parse later.
                        raise GraphXXError(
                            "source-scan",
                            f"Invalid IRI reference at character {start}: {text}",
                        ) from exc
                    if not isinstance(parsed, URIRef):
                        raise GraphXXError("source-scan", f"Invalid IRI reference: {text}")
                    tokens.append(SourceToken("IRI", text, str(parsed), start, i))
                    break
                if current == "\\" and not escaped:
                    escaped = True
                else:
                    escaped = False
                i += 1
            else:
                raise GraphXXError(
                    "source-scan", f"Unterminated IRI reference beginning at character {start}"
                )
            continue
        if char in {'"', "'"}:
            start = i
            i = _scan_quoted(source, start, char)
            tokens.append(SourceToken("STRING", source[start:i], source[start:i], start, i))
            continue
        if char in punctuation:
            tokens.append(SourceToken("PUNCT", char, char, i, i + 1))
            i += 1
            continue
        if source.startswith("^^", i):
            tokens.append(SourceToken("PUNCT", "^^", "^^", i, i + 2))
            i += 2
            continue

        start = i
        while i < length:
            current = source[i]
            if current.isspace() or current in word_stoppers:
                break
            # A dot may occur inside a prefixed name, blank-node label, or
            # numeric token, but an unescaped trailing dot is statement syntax.
            if current == ".":
                next_char = source[i + 1] if i + 1 < length else ""
                if (
                    not next_char
                    or next_char.isspace()
                    or next_char in word_stoppers
                    or next_char in "{}[]();,."
                ):
                    break
            if current == "\\" and i + 1 < length:
                i += 2
            else:
                i += 1
        if i == start:
            tokens.append(SourceToken("PUNCT", char, char, i, i + 1))
            i += 1
        else:
            text = source[start:i]
            tokens.append(SourceToken("WORD", text, text, start, i))

    return tokens


def is_absolute_iri(value: str) -> bool:
    return bool(urlsplit(value).scheme)


def extract_declared_prefixes(tokens: Sequence[SourceToken]) -> tuple[list[PrefixDecl], bool]:
    prefixes: list[PrefixDecl] = []
    prefix_to_namespace: dict[str, str] = {}
    has_base = False
    i = 0
    order = 0

    while i < len(tokens):
        token = tokens[i]
        lowered = token.text.lower()
        if token.kind == "WORD" and lowered in {"@base", "base"}:
            has_base = True
        if token.kind == "WORD" and lowered in {"@prefix", "prefix"}:
            if i + 2 >= len(tokens):
                raise GraphXXError(
                    "prefix-declaration", f"Incomplete prefix declaration near character {token.start}"
                )
            prefix_token = tokens[i + 1]
            iri_token = tokens[i + 2]
            if prefix_token.kind != "WORD" or not prefix_token.text.endswith(":"):
                raise GraphXXError(
                    "prefix-declaration",
                    f"Invalid prefix label near character {prefix_token.start}: {prefix_token.text}",
                )
            if iri_token.kind != "IRI":
                raise GraphXXError(
                    "prefix-declaration",
                    f"Prefix {prefix_token.text} is not followed by an IRI namespace",
                )
            prefix = prefix_token.text
            namespace = iri_token.value
            if not is_absolute_iri(namespace):
                raise GraphXXError(
                    "relative-iri",
                    f"Prefix {prefix} uses a relative namespace IRI: {namespace}",
                )
            previous = prefix_to_namespace.get(prefix)
            if previous is not None and previous != namespace:
                raise GraphXXError(
                    "prefix-conflict",
                    f"Prefix {prefix} is declared for both {previous} and {namespace}",
                )
            if previous is None:
                prefix_to_namespace[prefix] = namespace
                prefixes.append(PrefixDecl(prefix, namespace, order))
                order += 1
            i += 3
            continue
        i += 1

    return prefixes, has_base


def find_graph_blocks(tokens: Sequence[SourceToken]) -> list[GraphBlock]:
    blocks: list[GraphBlock] = []
    stack: list[tuple[SourceToken | None, SourceToken]] = []
    depth = 0

    for index, token in enumerate(tokens):
        if token.text == "{":
            if depth == 0:
                label_token: SourceToken | None = None
                if index > 0:
                    previous = tokens[index - 1]
                    if previous.kind in {"WORD", "IRI"}:
                        label_token = previous
                    elif previous.text == "]":
                        label_token = previous
                stack.append((label_token, token))
            depth += 1
        elif token.text == "}":
            if depth == 0:
                raise GraphXXError(
                    "source-scan", f"Unmatched closing brace at character {token.start}"
                )
            depth -= 1
            if depth == 0:
                label_token, opening = stack.pop()
                blocks.append(
                    GraphBlock(
                        label_token=label_token,
                        open_start=opening.start,
                        open_end=opening.end,
                        close_start=token.start,
                        close_end=token.end,
                    )
                )

    if depth != 0:
        raise GraphXXError("source-scan", "Unmatched opening graph brace")
    return blocks


def scan_source(source: str) -> SourceScan:
    tokens = tokenize_source(source)
    prefixes, has_base = extract_declared_prefixes(tokens)

    for token in tokens:
        if token.kind == "IRI" and not is_absolute_iri(token.value):
            raise GraphXXError("relative-iri", f"Relative IRI is unsupported in V1: {token.text}")

    uses_a = any(token.kind == "WORD" and token.text == "a" for token in tokens)
    explicit_labels: list[str] = []
    seen_labels: set[str] = set()
    for token in tokens:
        if token.kind == "WORD" and token.text.startswith("_:") and len(token.text) > 2:
            label = token.text[2:]
            if label not in seen_labels:
                seen_labels.add(label)
                explicit_labels.append(label)

    if uses_a and not any(prefix.prefix == CANONICAL_RDF_PREFIX for prefix in prefixes):
        prefixes.append(
            PrefixDecl(
                CANONICAL_RDF_PREFIX,
                CANONICAL_RDF_NAMESPACE,
                len(prefixes),
                generated=True,
            )
        )

    return SourceScan(
        tokens=tokens,
        prefixes=prefixes,
        uses_a_shorthand=uses_a,
        has_base_directive=has_base,
        explicit_bnode_labels=explicit_labels,
        graph_blocks=find_graph_blocks(tokens),
    )


def _prefix_map(prefixes: Sequence[PrefixDecl]) -> dict[str, str]:
    return {prefix.prefix: prefix.namespace for prefix in prefixes}


def resolve_graph_block_identifier(
    block: GraphBlock, prefixes: Sequence[PrefixDecl]
) -> URIRef | BNode | None:
    token = block.label_token
    if token is None:
        return None
    if token.text.lower() == "graph":
        return None
    if token.text == "]" or token.text.startswith("_:"):
        return BNode(token.text[2:] if token.text.startswith("_:") else "graph")
    if token.kind == "IRI":
        return URIRef(token.value)
    if token.kind == "WORD" and ":" in token.text:
        prefix_label, local = token.text.split(":", 1)
        prefix = prefix_label + ":"
        namespace = _prefix_map(prefixes).get(prefix)
        if namespace is None:
            raise GraphXXError(
                "graph-identifier",
                f"Graph identifier {token.text} uses undeclared prefix {prefix}",
            )
        return URIRef(namespace + local)
    raise GraphXXError(
        "graph-identifier", f"Unsupported graph identifier near character {token.start}: {token.text}"
    )


def source_named_graph_identifiers(scan: SourceScan) -> list[URIRef | BNode]:
    identifiers: list[URIRef | BNode] = []
    for block in scan.graph_blocks:
        identifier = resolve_graph_block_identifier(block, scan.prefixes)
        if identifier is not None and identifier not in identifiers:
            identifiers.append(identifier)
    return identifiers


def _new_graph() -> Graph:
    return Graph(bind_namespaces="none")


def _parse_turtle(source: str) -> Graph:
    graph = _new_graph()
    graph.parse(data=source, format="turtle")
    return graph


def _parse_trig(source: str) -> Dataset:
    dataset = Dataset(default_union=False)
    dataset.parse(data=source, format="trig")
    return dataset


def _dataset_named_identifiers(dataset: Dataset) -> list[Identifier]:
    default_id = dataset.default_graph.identifier
    result: list[Identifier] = []
    for graph in dataset.graphs():
        if graph.identifier != default_id and graph.identifier not in result:
            result.append(graph.identifier)
    return result


def _combined_named_identifiers(dataset: Dataset, scan: SourceScan) -> list[Identifier]:
    identifiers = _dataset_named_identifiers(dataset)
    for identifier in source_named_graph_identifiers(scan):
        if identifier not in identifiers:
            identifiers.append(identifier)
    return identifiers


def _validate_trig_dataset(dataset: Dataset, scan: SourceScan) -> URIRef:
    identifiers = _combined_named_identifiers(dataset, scan)
    if any(isinstance(identifier, BNode) for identifier in identifiers):
        offending = next(identifier for identifier in identifiers if isinstance(identifier, BNode))
        raise GraphXXError(
            "blank-graph-identifier", f"Blank-node named graph is unsupported: {offending}"
        )
    if len(identifiers) == 0:
        raise GraphXXError("named-graph-count", "TriG V1 requires exactly one named graph; found 0")
    if len(identifiers) > 1:
        rendered = ", ".join(str(identifier) for identifier in identifiers)
        raise GraphXXError(
            "named-graph-count",
            f"TriG V1 supports exactly one named graph; found {len(identifiers)}: {rendered}",
        )
    if len(dataset.default_graph) > 0:
        raise GraphXXError(
            "mixed-default-graph",
            "Named-graph data is mixed with nonempty default-graph triples",
        )
    identifier = identifiers[0]
    if not isinstance(identifier, URIRef):
        raise GraphXXError("graph-identifier", f"Unexpected graph identifier term: {identifier!r}")
    return identifier


def detect_syntax(
    source: str, requested: TypingLiteral["auto", "turtle", "trig"], scan: SourceScan
) -> tuple[TypingLiteral["turtle", "trig"], Graph | Dataset, URIRef | None]:
    if scan.has_base_directive:
        raise GraphXXError("base-iri", "@base and BASE directives are unsupported in V1")

    if requested == "turtle":
        try:
            return "turtle", _parse_turtle(source), None
        except Exception as exc:
            raise GraphXXError("turtle-parse", str(exc)) from exc

    if requested == "trig":
        try:
            dataset = _parse_trig(source)
        except Exception as exc:
            raise GraphXXError("trig-parse", str(exc)) from exc
        graph_identifier = _validate_trig_dataset(dataset, scan)
        return "trig", dataset, graph_identifier

    trig_error: Exception | None = None
    try:
        dataset = _parse_trig(source)
        identifiers = _combined_named_identifiers(dataset, scan)
        if len(identifiers) > 1:
            _validate_trig_dataset(dataset, scan)
        if len(identifiers) == 1:
            graph_identifier = _validate_trig_dataset(dataset, scan)
            return "trig", dataset, graph_identifier
    except GraphXXError:
        raise
    except Exception as exc:
        trig_error = exc

    try:
        turtle_graph = _parse_turtle(source)
        return "turtle", turtle_graph, None
    except Exception as turtle_exc:
        trig_message = str(trig_error) if trig_error is not None else "TriG parsed but contained no named graph"
        raise GraphXXError(
            "syntax-detection",
            f"TriG parse/detection failed: {trig_message}; Turtle parse failed: {turtle_exc}",
        ) from turtle_exc


def _graph_for_identifier(dataset: Dataset, identifier: URIRef) -> Graph:
    return dataset.graph(identifier)


def _check_internal_marker_collision(graph: Graph) -> None:
    if any(True for _ in graph.triples((None, INTERNAL_BNODE_LABEL_PREDICATE, None))):
        raise GraphXXError(
            "internal-marker-collision",
            f"Input uses reserved predicate {INTERNAL_BNODE_LABEL_PREDICATE}",
        )


def _labels_inside_block(scan: SourceScan, block: GraphBlock) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for token in scan.tokens:
        if not (block.open_end <= token.start < block.close_start):
            continue
        if token.kind == "WORD" and token.text.startswith("_:") and len(token.text) > 2:
            label = token.text[2:]
            if label not in seen:
                seen.add(label)
                labels.append(label)
    return labels


def _marker_statements(labels: Sequence[str]) -> str:
    lines = [
        f"_:{label} <{INTERNAL_BNODE_LABEL_PREDICATE}> {Literal(label).n3()} ."
        for label in labels
    ]
    return "\n".join(lines)


def decorate_source_with_bnode_markers(
    source: str,
    syntax: TypingLiteral["turtle", "trig"],
    scan: SourceScan,
    graph_identifier: URIRef | None,
) -> str:
    if not scan.explicit_bnode_labels:
        return source
    if syntax == "turtle":
        return source + "\n" + _marker_statements(scan.explicit_bnode_labels) + "\n"

    assert graph_identifier is not None
    insertions: list[tuple[int, str]] = []
    for block in scan.graph_blocks:
        identifier = resolve_graph_block_identifier(block, scan.prefixes)
        if identifier == graph_identifier:
            labels = _labels_inside_block(scan, block)
            if labels:
                insertions.append((block.close_start, "\n" + _marker_statements(labels) + "\n"))

    if not insertions:
        raise GraphXXError(
            "blank-node-mapping",
            "Explicit blank-node labels were found but their named graph block could not be located",
        )

    decorated = source
    for position, text in sorted(insertions, reverse=True):
        decorated = decorated[:position] + text + decorated[position:]
    return decorated


def parse_active_graph_with_markers(
    source: str,
    syntax: TypingLiteral["turtle", "trig"],
    scan: SourceScan,
    graph_identifier: URIRef | None,
) -> Graph:
    decorated = decorate_source_with_bnode_markers(source, syntax, scan, graph_identifier)
    try:
        if syntax == "turtle":
            return _parse_turtle(decorated)
        dataset = _parse_trig(decorated)
        assert graph_identifier is not None
        return _graph_for_identifier(dataset, graph_identifier)
    except Exception as exc:
        raise GraphXXError("decorated-parse", f"Failed while mapping blank nodes: {exc}") from exc


def canonicalize_graph_and_blank_nodes(
    graph: Graph,
) -> tuple[Graph, dict[BNode, str]]:
    canonical = to_canonical_graph(graph)
    explicit_mapping: dict[BNode, str] = {}
    label_to_node: dict[str, BNode] = {}

    for subject, _, obj in canonical.triples((None, INTERNAL_BNODE_LABEL_PREDICATE, None)):
        if not isinstance(subject, BNode) or not isinstance(obj, Literal):
            raise GraphXXError("blank-node-mapping", "Malformed internal blank-node marker")
        label = str(obj)
        previous = label_to_node.get(label)
        if previous is not None and previous != subject:
            raise GraphXXError(
                "blank-node-mapping",
                f"Explicit blank-node label _:{label} resolved to multiple RDF nodes",
            )
        label_to_node[label] = subject
        explicit_mapping[subject] = label

    clean = _new_graph()
    for subject, predicate, obj in canonical:
        if predicate != INTERNAL_BNODE_LABEL_PREDICATE:
            clean.add((subject, predicate, obj))
    return clean, explicit_mapping


def assign_blank_node_references(
    graph: Graph, explicit_mapping: dict[BNode, str]
) -> dict[BNode, str]:
    bnodes = {
        term
        for triple in graph
        for term in (triple[0], triple[2])
        if isinstance(term, BNode)
    }
    mapping: dict[BNode, str] = {
        bnode: label for bnode, label in explicit_mapping.items() if bnode in bnodes
    }
    reserved = set(mapping.values())
    counter = 1
    for bnode in sorted(bnodes - mapping.keys(), key=str):
        while f"node{counter}" in reserved:
            counter += 1
        reference = f"node{counter}"
        mapping[bnode] = reference
        reserved.add(reference)
        counter += 1
    return mapping


def resolve_qname(
    iri: URIRef,
    prefixes: Sequence[PrefixDecl],
    *,
    preferred_prefix: str | None = None,
) -> QNameParts:
    iri_text = str(iri)
    if not is_absolute_iri(iri_text):
        raise GraphXXError("relative-iri", f"Relative IRI is unsupported: {iri_text}")

    if preferred_prefix is not None:
        for declaration in prefixes:
            if declaration.prefix == preferred_prefix and iri_text.startswith(declaration.namespace):
                local = iri_text[len(declaration.namespace) :]
                if local:
                    return QNameParts(preferred_prefix + local, preferred_prefix, local)

    candidates: list[tuple[int, int, PrefixDecl]] = []
    for declaration in prefixes:
        if iri_text.startswith(declaration.namespace):
            candidates.append(
                (-len(declaration.namespace), declaration.source_order, declaration)
            )
    if not candidates:
        raise GraphXXError(
            "unsupported-iri",
            f"IRI cannot be represented by a declared prefix: {iri_text}",
        )
    _, _, selected = min(candidates)
    local = iri_text[len(selected.namespace) :]
    if not local:
        raise GraphXXError(
            "invalid-qname", f"IRI has an empty local identifier for prefix {selected.prefix}: {iri_text}"
        )
    return QNameParts(selected.prefix + local, selected.prefix, local)


def _is_container_membership_predicate(predicate: URIRef) -> bool:
    if predicate == RDFS.member:
        return True
    
    text = str(predicate)
    prefix = str(RDF) + "_"
    return text.startswith(prefix) and text[len(prefix) :].isdigit()


def collect_nodes_and_role_evidence(
    graph: Graph,
) -> tuple[set[URIRef | BNode], dict[URIRef | BNode, RoleEvidence]]:
    nodes: set[URIRef | BNode] = set()
    evidence: dict[URIRef | BNode, RoleEvidence] = {}

    def ensure(term: URIRef | BNode) -> RoleEvidence:
        nodes.add(term)
        return evidence.setdefault(term, RoleEvidence())

    for subject, predicate, obj in graph:
        if not isinstance(subject, (URIRef, BNode)):
            raise GraphXXError("unexpected-term", f"Unexpected RDF subject: {subject!r}")
        if not isinstance(predicate, URIRef):
            raise GraphXXError("unexpected-term", f"Unexpected RDF predicate: {predicate!r}")
        ensure(subject)
        if isinstance(obj, (URIRef, BNode)):
            ensure(obj)
        elif not isinstance(obj, Literal):
            raise GraphXXError("unexpected-term", f"Unexpected RDF object: {obj!r}")

        if predicate == RDF.type and isinstance(obj, (URIRef, BNode)):
            ensure(obj).thing_type.add("object of rdf:type")
            if obj in CLASS_TYPE_OBJECTS:
                ensure(subject).thing_type.add(f"typed as {obj}")
            if obj == RDFS.Datatype:
                ensure(subject).datatype.add("typed as rdfs:Datatype")
            if obj in PROPERTY_TYPE_OBJECTS:
                ensure(subject).property_resource.add(f"typed as {obj}")
            if obj in CONTAINER_TYPE_OBJECTS:
                ensure(subject).container.add(f"typed as {obj}")

        if predicate == RDFS.subClassOf and isinstance(obj, (URIRef, BNode)):
            ensure(subject).thing_type.add("subject of rdfs:subClassOf")
            ensure(obj).thing_type.add("object of rdfs:subClassOf")

        if predicate in OWL_CLASS_CONSTRUCT_PREDICATES:
            ensure(subject).thing_type.add(f"subject of {predicate}")
            if isinstance(obj, (URIRef, BNode)):
                ensure(obj).thing_type.add(f"object of {predicate}")

        if predicate == RDFS.domain:
            ensure(subject).property_resource.add("subject of rdfs:domain")
            if isinstance(obj, (URIRef, BNode)):
                ensure(obj).thing_type.add("object of rdfs:domain")

        if predicate == RDFS.range:
            ensure(subject).property_resource.add("subject of rdfs:range")
            if isinstance(obj, (URIRef, BNode)):
                if isinstance(obj, URIRef) and obj in RECOGNIZED_XSD_DATATYPES:
                    ensure(obj).datatype.add("XSD datatype used as rdfs:range")
                else:
                    ensure(obj).thing_type.add("class used as rdfs:range")

        if predicate == RDFS.subPropertyOf and isinstance(obj, (URIRef, BNode)):
            ensure(subject).property_resource.add("subject of rdfs:subPropertyOf")
            ensure(obj).property_resource.add("object of rdfs:subPropertyOf")

        if _is_container_membership_predicate(predicate):
            ensure(subject).container.add(f"subject of {predicate}")

    for node in nodes:
        if isinstance(node, URIRef) and node in RECOGNIZED_XSD_DATATYPES:
            evidence[node].datatype.add("recognized XSD datatype resource")

    return nodes, evidence


def classify_graphxx_node(
    term: URIRef | BNode,
    evidence: RoleEvidence,
) -> str:
    roles = evidence.active_roles()

    if len(roles) > 1:
        LOGGER.warning(
            "Conflicting role evidence for %s: %s; applying precedence",
            term,
            ", ".join(roles),
        )

    if evidence.container:
        return "Container"

    if isinstance(term, BNode):
        return "HelperNode"

    if evidence.datatype:
        return "DatatypeNode"

    if evidence.thing_type:
        return "ThingType"

    if evidence.property_resource:
        return PROPERTY_GRAPHXX_CLASS

    return "ThingIdentifier"


def term_reference(
    term: URIRef | BNode,
    prefixes: Sequence[PrefixDecl],
    blank_node_references: dict[BNode, str],
) -> str:
    if isinstance(term, URIRef):
        return resolve_qname(term, prefixes).qname
    if isinstance(term, BNode):
        try:
            return blank_node_references[term]
        except KeyError as exc:
            raise GraphXXError("blank-node-mapping", f"No reference assigned to {term}") from exc
    raise GraphXXError("unexpected-term", f"Expected IRI or blank node, got {term!r}")


def build_node_records(
    nodes: Iterable[URIRef | BNode],
    evidence: dict[URIRef | BNode, RoleEvidence],
    prefixes: Sequence[PrefixDecl],
    blank_node_references: dict[BNode, str],
) -> list[NodeRecord]:
    records: set[NodeRecord] = set()
    for term in nodes:
        graphxx_class = classify_graphxx_node(term, evidence[term])
        if isinstance(term, URIRef):
            qname = resolve_qname(term, prefixes)
            records.add(NodeRecord("IRI", graphxx_class, qname.qname, qname.prefix, qname.local))
        elif isinstance(term, BNode):
            reference = blank_node_references[term]
            records.add(NodeRecord("BNODE", graphxx_class, reference, ABSENT_VALUE, reference))
        else:
            raise GraphXXError("unexpected-term", f"Unexpected node term: {term!r}")
    return sorted(records, key=lambda record: record.node_reference)


def _predicate_qname(
    predicate: URIRef,
    prefixes: Sequence[PrefixDecl],
    uses_a_shorthand: bool,
) -> QNameParts:
    preferred = CANONICAL_RDF_PREFIX if uses_a_shorthand and predicate == RDF.type else None
    return resolve_qname(predicate, prefixes, preferred_prefix=preferred)


def build_attribute_records(
    graph: Graph,
    prefixes: Sequence[PrefixDecl],
    blank_node_references: dict[BNode, str],
    owner_graphxx_classes: dict[str, str],
    uses_a_shorthand: bool,
) -> list[AttributeRecord]:
    records: set[AttributeRecord] = set()
    for subject, predicate, obj in graph:
        if not isinstance(obj, Literal):
            continue
        owner = term_reference(subject, prefixes, blank_node_references)
        try:
            owner_graphxx_class = owner_graphxx_classes[owner]
        except KeyError as exc:
            raise GraphXXError(
                "attribute-owner",
                f"Attribute owner has no classified NODE record: {owner}",
            ) from exc
        predicate_qname = _predicate_qname(predicate, prefixes, uses_a_shorthand)
        language = obj.language or ABSENT_VALUE
        if obj.language:
            datatype = ABSENT_VALUE
        elif obj.datatype is not None:
            datatype = resolve_qname(URIRef(obj.datatype), prefixes).qname
        else:
            datatype = ABSENT_VALUE
        records.add(
            AttributeRecord(
                owner,
                owner_graphxx_class,
                predicate_qname.qname,
                predicate_qname.prefix,
                predicate_qname.local,
                str(obj),
                datatype,
                language,
            )
        )
    return sorted(
        records,
        key=lambda record: (
            record.owner_node_reference,
            record.predicate_qname,
            record.lexical_value,
            record.datatype_qname,
            record.language,
        ),
    )


def build_edge_records(
    graph: Graph,
    prefixes: Sequence[PrefixDecl],
    blank_node_references: dict[BNode, str],
    node_graphxx_classes: dict[str, str],
    uses_a_shorthand: bool,
) -> list[EdgeRecord]:
    records: set[EdgeRecord] = set()
    for subject, predicate, obj in graph:
        if isinstance(obj, Literal):
            continue
        if not isinstance(obj, (URIRef, BNode)):
            raise GraphXXError("unexpected-term", f"Unexpected edge target: {obj!r}")
        source = term_reference(subject, prefixes, blank_node_references)
        target = term_reference(obj, prefixes, blank_node_references)
        try:
            source_graphxx_class = node_graphxx_classes[source]
        except KeyError as exc:
            raise GraphXXError(
                "edge-source",
                f"Edge source has no classified NODE record: {source}",
            ) from exc
        try:
            target_graphxx_class = node_graphxx_classes[target]
        except KeyError as exc:
            raise GraphXXError(
                "edge-target",
                f"Edge target has no classified NODE record: {target}",
            ) from exc
        predicate_qname = _predicate_qname(predicate, prefixes, uses_a_shorthand)
        connector_kind = SPECIAL_CONNECTOR_KINDS.get(predicate, "GENERIC")
        records.add(
            EdgeRecord(
                source,
                source_graphxx_class,
                target,
                target_graphxx_class,
                predicate_qname.qname,
                predicate_qname.prefix,
                predicate_qname.local,
                connector_kind,
            )
        )
    return sorted(
        records,
        key=lambda record: (
            record.source_node_reference,
            record.predicate_qname,
            record.target_node_reference,
        ),
    )


def build_graph_record(
    graph_identifier: URIRef | None, prefixes: Sequence[PrefixDecl]
) -> GraphRecord | None:
    if graph_identifier is None:
        return None
    qname = resolve_qname(graph_identifier, prefixes)
    return GraphRecord(str(graph_identifier), qname.qname, qname.prefix, qname.local)


def escape_field(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(FIELD_SEPARATOR, "\\p")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def validate_records(records: Sequence[Record]) -> None:
    node_classes = {
        record.node_reference: record.graphxx_class
        for record in records
        if isinstance(record, NodeRecord)
    }
    node_references = set(node_classes)
    for record in records:
        if isinstance(record, AttributeRecord):
            if record.owner_node_reference not in node_references:
                raise GraphXXError(
                    "attribute-owner",
                    f"Attribute owner has no NODE record: {record.owner_node_reference}",
                )
            expected_class = node_classes[record.owner_node_reference]
            if record.owner_graphxx_class != expected_class:
                raise GraphXXError(
                    "attribute-owner-class",
                    "Attribute owner class does not match its NODE record: "
                    f"{record.owner_node_reference} has {record.owner_graphxx_class}, "
                    f"expected {expected_class}",
                )
        if isinstance(record, EdgeRecord):
            if record.source_node_reference not in node_references:
                raise GraphXXError(
                    "edge-source",
                    f"Edge source has no NODE record: {record.source_node_reference}",
                )
            if record.target_node_reference not in node_references:
                raise GraphXXError(
                    "edge-target",
                    f"Edge target has no NODE record: {record.target_node_reference}",
                )
            expected_source_class = node_classes[record.source_node_reference]
            if record.source_node_graphxx_class != expected_source_class:
                raise GraphXXError(
                    "edge-source-class",
                    "Edge source class does not match its NODE record: "
                    f"{record.source_node_reference} has "
                    f"{record.source_node_graphxx_class}, expected "
                    f"{expected_source_class}",
                )
            expected_target_class = node_classes[record.target_node_reference]
            if record.target_node_graphxx_class != expected_target_class:
                raise GraphXXError(
                    "edge-target-class",
                    "Edge target class does not match its NODE record: "
                    f"{record.target_node_reference} has "
                    f"{record.target_node_graphxx_class}, expected "
                    f"{expected_target_class}",
                )

        escaped = tuple(escape_field(field) for field in record.fields())
        for field in escaped:
            if FIELD_SEPARATOR in field or "\n" in field or "\r" in field or "\t" in field:
                raise GraphXXError(
                    "field-escaping", f"Record contains an unescaped separator or line break: {record}"
                )


def serialize_records(records: Sequence[Record]) -> str:
    lines = [
        FIELD_SEPARATOR.join(escape_field(field) for field in record.fields())
        for record in records
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def convert_source(
    source: str,
    *,
    syntax: TypingLiteral["auto", "turtle", "trig"] = "auto",
    input_name: str = "<memory>",
) -> str:
    try:
        scan = scan_source(source)
        detected_syntax, parsed, graph_identifier = detect_syntax(source, syntax, scan)

        if detected_syntax == "turtle":
            assert isinstance(parsed, Graph)
            initial_graph = parsed
        else:
            assert isinstance(parsed, Dataset)
            assert graph_identifier is not None
            initial_graph = _graph_for_identifier(parsed, graph_identifier)
        _check_internal_marker_collision(initial_graph)

        active_graph = parse_active_graph_with_markers(
            source, detected_syntax, scan, graph_identifier
        )
        graph, explicit_mapping = canonicalize_graph_and_blank_nodes(active_graph)
        blank_node_references = assign_blank_node_references(graph, explicit_mapping)
        nodes, evidence = collect_nodes_and_role_evidence(graph)

        records: list[Record] = []
        graph_record = build_graph_record(graph_identifier, scan.prefixes)
        if graph_record is not None:
            records.append(graph_record)
        records.extend(PrefixRecord(prefix.prefix, prefix.namespace) for prefix in scan.prefixes)
        node_records = build_node_records(
            nodes, evidence, scan.prefixes, blank_node_references
        )
        records.extend(node_records)
        node_graphxx_classes = {
            record.node_reference: record.graphxx_class for record in node_records
        }
        records.extend(
            build_attribute_records(
                graph,
                scan.prefixes,
                blank_node_references,
                node_graphxx_classes,
                scan.uses_a_shorthand,
            )
        )
        records.extend(
            build_edge_records(
                graph,
                scan.prefixes,
                blank_node_references,
                node_graphxx_classes,
                scan.uses_a_shorthand,
            )
        )
        validate_records(records)
        return serialize_records(records)
    except GraphXXError as exc:
        raise GraphXXError(exc.category, f"{input_name}: {exc.message}") from exc


def atomic_write_output(path: Path, content: str) -> None:
    directory = path.parent if path.parent != Path("") else Path(".")
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise GraphXXError("output-io", f"Cannot create output directory {directory}: {exc}") from exc

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=directory,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as exc:
        raise GraphXXError("output-io", f"Cannot atomically write {path}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def convert_file(
    input_path: Path,
    output_path: Path,
    syntax: TypingLiteral["auto", "turtle", "trig"] = "auto",
) -> None:
    source = read_source_file(input_path)
    content = convert_source(source, syntax=syntax, input_name=str(input_path))
    atomic_write_output(output_path, content)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Turtle or TriG RDF into GRAPHxx ADOscript transport records."
    )
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 Turtle/TriG input file")
    parser.add_argument("--output", required=True, type=Path, help="UTF-8 GRAPHxx output file")
    parser.add_argument(
        "--syntax",
        choices=("auto", "turtle", "trig"),
        default="auto",
        help="Input syntax; default: auto",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = build_argument_parser().parse_args(argv)
    try:
        convert_file(args.input, args.output, args.syntax)
        return 0
    except GraphXXError as exc:
        print(f"ERROR [{exc.category}] {exc.message}", file=sys.stderr)
        return 2
    except Exception as exc:  # Defensive boundary for unattended ADOscript use.
        print(f"ERROR [unexpected] {args.input}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
