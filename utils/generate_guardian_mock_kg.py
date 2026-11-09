#!/usr/bin/env python3
"""
generate_guardian_mock_kg.py

Generate synthetic (MOCK) data for the Guardian Sales Knowledge Graph schema.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
import os
import random
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Optional: Faker for better-looking mock people/org names.
try:
    from faker import Faker  # type: ignore
except Exception:
    Faker = None

# Optional: networkx for GraphML export
try:
    import networkx as nx  # type: ignore
except Exception:
    nx = None


# ----------------------------
# Helpers
# ----------------------------

def iso_date(d: _dt.date) -> str:
    return d.isoformat()

def iso_datetime(dt: _dt.datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.isoformat()

def rand_date(rng: random.Random, start_year: int = 2020, end_year: int = 2026) -> str:
    # inclusive bounds
    start = _dt.date(start_year, 1, 1)
    end = _dt.date(end_year, 12, 31)
    delta_days = (end - start).days
    return iso_date(start + _dt.timedelta(days=rng.randint(0, max(0, delta_days))))

def rand_confidence(rng: random.Random) -> float:
    # keep it in a plausible range, but synthetic
    return round(rng.uniform(0.55, 0.98), 3)

def safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    return str(x)

def json_str(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))

def now_utc() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)

def make_uuid() -> str:
    return str(uuid.uuid4())

def pick_enum(prop_def: Dict[str, Any], rng: random.Random) -> Optional[Any]:
    enum = prop_def.get("enum")
    if isinstance(enum, list) and enum:
        return rng.choice(enum)
    return None

def gen_value(prop_def: Dict[str, Any], rng: random.Random, hint: str = "") -> Any:
    """Generate a mock value for a property definition (JSON-schema-ish)."""
    # Prefer enums when available
    v = pick_enum(prop_def, rng)
    if v is not None:
        return v

    typ = prop_def.get("type", "string")
    fmt = prop_def.get("format")

    if fmt == "date":
        return rand_date(rng)
    if fmt == "date-time":
        return iso_datetime(now_utc())

    if typ == "boolean":
        return rng.choice([True, False])
    if typ == "integer":
        return rng.randint(0, 100)
    if typ == "number":
        return round(rng.uniform(0, 100), 2)
    if typ == "array":
        # Try to create a small list; store as JSON string later
        return [f"{hint}tag{rng.randint(1,5)}" for _ in range(rng.randint(0, 3))]
    if typ == "object":
        return {"mock": True, "hint": hint, "n": rng.randint(1, 9)}

    # default: string
    min_len = prop_def.get("minLength", 0)
    base = f"{hint}{rng.randint(1, 9999)}"
    if len(base) < min_len:
        base = base + ("x" * (min_len - len(base)))
    return base


@dataclass
class NodeRow:
    id: str
    labels: str
    properties: Dict[str, Any]


@dataclass
class EdgeRow:
    source: str
    target: str
    type: str
    properties: Dict[str, Any]


def build_scale_config(scale: str) -> Tuple[int, Dict[str, int], int]:
    """
    Returns:
      base_nodes_per_type,
      overrides_by_type,
      default_edges_per_type
    """
    scale = scale.lower().strip()
    if scale == "large":
        base = 3
        edges = 6
        overrides = {
            "Person": 50,
            "Organization": 12,
            "Product": 14,
            "Service": 10,
            "Feature": 60,
            "Benefit": 40,
            "Coverage": 30,
            "Topic": 40,
            "Interest": 80,
            "ContentAsset": 50,
            "Campaign": 12,
            "Sequence": 12,
            "SequenceStep": 50,
            "EmailTemplate": 30,
            "EmailMessage": 150,
            "Interaction": 200,
            "Objection": 40,
            "Response": 40,
            "Document": 20,
            "DocumentSection": 60,
            "Adviser": 20, "AdviserFirm": 5, "AdviserNetwork": 2, "SalesPlay": 10, "FunnelStage": 5, "ConsumerDutyOutcome": 4, "FairValueAssessment": 5
        }
        return base, overrides, edges

    if scale == "medium":
        base = 2
        edges = 4
        overrides = {
            "Person": 25,
            "Organization": 8,
            "Product": 10,
            "Service": 8,
            "Feature": 35,
            "Benefit": 20,
            "Coverage": 18,
            "Topic": 25,
            "Interest": 40,
            "ContentAsset": 30,
            "Campaign": 8,
            "Sequence": 8,
            "SequenceStep": 25,
            "EmailTemplate": 18,
            "EmailMessage": 80,
            "Interaction": 120,
            "Objection": 20,
            "Response": 20,
            "Document": 14,
            "DocumentSection": 35,
            "Adviser": 10, "AdviserFirm": 3, "AdviserNetwork": 1, "SalesPlay": 5, "FunnelStage": 5, "ConsumerDutyOutcome": 4, "FairValueAssessment": 3
        }
        return base, overrides, edges

    # default: small
    base = 1
    edges = 3
    overrides = {
        "Person": 15,
        "Organization": 5,
        "Product": 8,
        "Service": 6,
        "Feature": 20,
        "Benefit": 12,
        "Coverage": 12,
        "Topic": 15,
        "Interest": 25,
        "ContentAsset": 20,
        "Campaign": 5,
        "Sequence": 5,
        "SequenceStep": 12,
        "EmailTemplate": 10,
        "EmailMessage": 40,
        "Interaction": 60,
        "Objection": 12,
        "Response": 12,
        "Document": 10,
        "DocumentSection": 20,
        "Adviser": 5, "AdviserFirm": 2, "AdviserNetwork": 1, "SalesPlay": 3, "FunnelStage": 5, "ConsumerDutyOutcome": 4, "FairValueAssessment": 2
    }
    return base, overrides, edges


class MockKGGenerator:
    def __init__(
        self,
        schema: Dict[str, Any],
        seed: int,
        scale: str,
        edges_per_type: Optional[int] = None,
        include_reverse_edges: bool = False,
        with_provenance: bool = True,
        alias_rate: float = 0.20,
    ):
        self.schema = schema
        self.rng = random.Random(seed)
        self.seed = seed
        self.scale = scale
        self.include_reverse_edges = include_reverse_edges
        self.with_provenance = with_provenance
        self.alias_rate = max(0.0, min(1.0, alias_rate))

        self.fake = None
        if Faker is not None:
            try:
                Faker.seed(seed)
                self.fake = Faker()
            except Exception:
                self.fake = None

        base, overrides, default_edges = build_scale_config(scale)
        self.base_nodes_per_type = base
        self.node_count_overrides = overrides
        self.edges_per_type = edges_per_type if edges_per_type is not None else default_edges

        # Storage
        self.nodes: List[NodeRow] = []
        self.edges: List[EdgeRow] = []

        self.nodes_by_type: Dict[str, List[str]] = {nt: [] for nt in self.schema["node_types"].keys()}
        self.node_index: Dict[str, Dict[str, Any]] = {}  # id -> {"type":..., "name":..., "description":...}

        # Documents pool (for edge/source provenance)
        self.doc_node_ids: List[str] = []
        self.doc_ids: List[str] = []  # Document.doc_id property values

        # Track duplicates
        self.edge_seen: set[Tuple[str, str, str]] = set()  # (type, source, target)

        # Identify provenance-ish relation types we don't want to recursively assert about
        self.provenance_edge_types = set([
            "ASSERTS_SUBJECT", "ASSERTS_OBJECT",
            "ASSERTION_SUPPORTED_BY", "EVIDENCE_FROM_DOCUMENT",
            "HAS_NAME_VARIANT", "NAME_VARIANT_OF",
            "HAS_SOURCE_DOCUMENT", "DOCUMENT_IS_SOURCE_FOR",
        ])

    def _schema_desc(self, node_type: str) -> str:
        return (self.schema["node_types"].get(node_type, {}) or {}).get("description", "").strip()

    def _make_node_id(self, node_type: str, i: int) -> str:
        # Use stable, human-readable IDs for mock data
        return f"{node_type}:{i:04d}"

    def _make_node(self, node_type: str, i: int, overrides: Optional[Dict[str, Any]] = None) -> NodeRow:
        overrides = overrides or {}
        ndef = self.schema["node_types"][node_type]
        props_def = ndef.get("properties", {})

        node_id = self._make_node_id(node_type, i)

        # Base props
        name = overrides.get("name")
        if not name:
            if node_type == "Person" and self.fake:
                name = self.fake.name()
            elif node_type == "Organization" and self.fake:
                name = self.fake.company()
            elif node_type in ("EmailTemplate", "ContentAsset"):
                name = f"MOCK {node_type} {i+1}"
            elif node_type == "Product":
                # A few realistic-sounding product names (still mock)
                product_names = [
                    "Income Protection",
                    "Critical Illness Cover",
                    "Combined Critical Illness Cover",
                    "Children's Critical Illness Cover",
                    "Life Insurance",
                    "Family Income Benefit",
                    "Guardian Anytime Service",
                    "HALO (Wellbeing Support)",
                ]
                name = product_names[i % len(product_names)] + f" (MOCK {i+1})"
            else:
                name = f"MOCK {node_type} {i+1}"

        description = overrides.get("description")
        if not description:
            schema_desc = self._schema_desc(node_type)
            if schema_desc:
                description = f"MOCK instance of {node_type}. {schema_desc}"
            else:
                description = f"MOCK instance of {node_type}."

        props: Dict[str, Any] = {}

        # Always include common/base properties if present in schema.common_types
        base_props = (self.schema.get("common_types", {}) or {}).get("node_base_properties", {})
        for bp_name, bp_def in base_props.items():
            if bp_name in ("id", "name", "description"):
                continue
            # some base props are arrays/objects; keep small
            props[bp_name] = gen_value(bp_def, self.rng, hint=f"{node_type}_{bp_name}_")

        # Standardized base fields
        props["id"] = node_id
        props["name"] = name
        props["description"] = description

        # Node-type-specific required props
        required = list(ndef.get("required", []) or [])
        for rp in required:
            if rp in ("id", "name", "description"):
                continue
            if rp in overrides:
                props[rp] = overrides[rp]
                continue
            rp_def = props_def.get(rp, {"type": "string"})
            props[rp] = gen_value(rp_def, self.rng, hint=f"{node_type}_{rp}_")

        # Node-type-specific optional props (add a few for richness)
        optional_props = [p for p in props_def.keys() if p not in required and p not in ("id", "name", "description")]
        self.rng.shuffle(optional_props)
        for op in optional_props[: min(4, len(optional_props))]:
            if op in props:
                continue
            op_def = props_def.get(op, {"type": "string"})
            props[op] = gen_value(op_def, self.rng, hint=f"{node_type}_{op}_")

        # Special-case some types for nicer mock values
        if node_type == "ContactPoint":
            if self.fake:
                props["value"] = overrides.get("value", self.fake.email())
            props.setdefault("contact_type", "email")

        if node_type == "Document":
            # Ensure doc_id exists and is stable
            doc_id = overrides.get("doc_id") or f"DOC-{i+1:04d}"
            props["doc_id"] = doc_id
            props["title"] = overrides.get("title") or name
            props.setdefault("doc_type", pick_enum(props_def.get("doc_type", {}), self.rng) or "brochure")

        if node_type == "DocumentSection":
            # Keep doc_id link-able; will be assigned after Document pool built if absent
            props.setdefault("section_id", f"SEC-{i+1:05d}")
            props.setdefault("start_page", self.rng.randint(1, 25))
            props.setdefault("end_page", props["start_page"] + self.rng.randint(0, 4))

        if node_type == "EvidenceSnippet":
            props.setdefault("snippet_text", f"MOCK evidence snippet {i+1}.")
            # doc_id will be filled later if not set

        if node_type == "Assertion":
            # predicate/subject/object/doc_id typically set later when we create provenance
            props.setdefault("assertion_type", "edge_assertion")

        labels = f"Entity;{node_type}"
        row = NodeRow(id=node_id, labels=labels, properties=props)
        self.node_index[node_id] = {"type": node_type, "name": name, "description": description}
        return row

    def _add_node(self, node: NodeRow) -> None:
        self.nodes.append(node)
        node_type = node.labels.split(";")[-1]
        self.nodes_by_type[node_type].append(node.id)

        if node_type == "Document":
            self.doc_node_ids.append(node.id)
            self.doc_ids.append(node.properties.get("doc_id", node.id))

    def _make_edge(
        self,
        edge_type: str,
        source: str,
        target: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Optional[EdgeRow]:
        overrides = overrides or {}

        key = (edge_type, source, target)
        if key in self.edge_seen:
            return None

        base_props = (self.schema.get("common_types", {}) or {}).get("edge_base_properties", {})
        props: Dict[str, Any] = {}

        # Fill base edge properties
        for ep_name, ep_def in base_props.items():
            if ep_name in overrides:
                props[ep_name] = overrides[ep_name]
            else:
                if ep_name == "rel_id":
                    props[ep_name] = make_uuid()
                elif ep_name == "confidence":
                    props[ep_name] = rand_confidence(self.rng)
                elif ep_name == "jurisdiction":
                    props[ep_name] = self.rng.choice(["UK", "Great Britain", "Northern Ireland"])
                elif ep_name in ("effective_from", "effective_to"):
                    # leave blank by default; fill sometimes
                    props[ep_name] = ""
                elif ep_name == "source_doc_id":
                    props[ep_name] = overrides.get("source_doc_id", "")
                else:
                    props[ep_name] = gen_value(ep_def, self.rng, hint=f"{edge_type}_{ep_name}_")

        # Occasionally add an effective range
        if self.rng.random() < 0.30:
            ef = rand_date(self.rng, 2020, 2026)
            props["effective_from"] = ef
            if self.rng.random() < 0.40:
                props["effective_to"] = rand_date(self.rng, 2026, 2028)

        # Attach a source_doc_id if we have docs
        if not props.get("source_doc_id"):
            if self.doc_ids:
                props["source_doc_id"] = self.rng.choice(self.doc_ids)

        row = EdgeRow(source=source, target=target, type=edge_type, properties=props)
        self.edges.append(row)
        self.edge_seen.add(key)
        return row

    def _maybe_add_alias(self, entity_id: str) -> None:
        """Add a NameVariant for an entity with some probability."""
        if self.rng.random() > self.alias_rate:
            return

        # Only for selected entity types, to avoid explosion
        ent_type = self.node_index.get(entity_id, {}).get("type")
        if ent_type not in ("Product", "Service", "Topic", "Feature", "Benefit", "Regulation", "Campaign"):
            return

        variants = {
            "Product": ["IP", "Income Prot", "CI", "CIC", "Life Cover"],
            "Service": ["App", "Portal", "Support", "Wellbeing"],
            "Topic": ["Underwriting", "Claims", "Direct Debit", "Trusts", "Consumer Duty"],
            "Feature": ["Flex", "Option", "Add-on", "Rider"],
            "Benefit": ["Payout", "Support", "Cover"],
            "Regulation": ["FCA", "ICOBS", "Consumer Duty"],
            "Campaign": ["Nurture", "Reactivation", "Awareness"],
        }
        variant_text = self.rng.choice(variants.get(ent_type, ["AltName"])) + f" {self.rng.randint(1, 99)}"

        # Create NameVariant node
        i = len(self.nodes_by_type.get("NameVariant", []))
        nv_id = self._make_node_id("NameVariant", i)
        nv_props = {
            "id": nv_id,
            "name": variant_text,
            "description": f"MOCK name variant for {entity_id}.",
            "variant": variant_text,
            "variant_type": self.rng.choice(["abbreviation", "alias", "synonym"]),
            "created_at": iso_datetime(now_utc()),
            "updated_at": iso_datetime(now_utc()),
        }
        self._add_node(NodeRow(id=nv_id, labels="Entity;NameVariant", properties=nv_props))

        # Connect
        if "HAS_NAME_VARIANT" in self.schema["edge_types"]:
            self._make_edge("HAS_NAME_VARIANT", entity_id, nv_id)

    def _create_provenance_for_edge(self, edge: EdgeRow) -> None:
        """
        For an edge (domain fact), create:
          Assertion -(ASSERTION_SUPPORTED_BY)-> EvidenceSnippet -(EVIDENCE_FROM_DOCUMENT)-> Document
          Assertion -(ASSERTS_SUBJECT)-> source
          Assertion -(ASSERTS_OBJECT)-> target
        """
        if not self.with_provenance:
            return
        if edge.type in self.provenance_edge_types:
            return

        src_type = self.node_index.get(edge.source, {}).get("type")
        tgt_type = self.node_index.get(edge.target, {}).get("type")
        if src_type in ("Assertion", "EvidenceSnippet") or tgt_type in ("Assertion", "EvidenceSnippet"):
            return

        # Pick a document
        if not self.doc_node_ids:
            return
        doc_node_id = self.rng.choice(self.doc_node_ids)
        doc_id = None
        for n in self.nodes:
            if n.id == doc_node_id:
                doc_id = n.properties.get("doc_id")
                break
        if not doc_id:
            doc_id = self.rng.choice(self.doc_ids) if self.doc_ids else ""

        # Create EvidenceSnippet
        ev_idx = len(self.nodes_by_type.get("EvidenceSnippet", []))
        ev_node_id = self._make_node_id("EvidenceSnippet", ev_idx)
        ev_text = f"MOCK evidence for {edge.type}: {self.node_index.get(edge.source, {}).get('name','source')} -> {self.node_index.get(edge.target, {}).get('name','target')}."
        ev_props = {
            "id": ev_node_id,
            "name": f"Evidence {ev_idx+1}",
            "description": "MOCK evidence snippet supporting an assertion.",
            "snippet_text": ev_text,
            "doc_id": doc_id,
            "page_start": self.rng.randint(1, 25),
            "page_end": self.rng.randint(1, 25),
            "created_at": iso_datetime(now_utc()),
            "updated_at": iso_datetime(now_utc()),
        }
        self._add_node(NodeRow(id=ev_node_id, labels="Entity;EvidenceSnippet", properties=ev_props))

        # Create Assertion
        as_idx = len(self.nodes_by_type.get("Assertion", []))
        as_node_id = self._make_node_id("Assertion", as_idx)
        as_props = {
            "id": as_node_id,
            "name": f"Assertion {as_idx+1}",
            "description": "MOCK assertion generated to attach evidence/provenance.",
            "assertion_type": "edge_assertion",
            "predicate": edge.type,
            "subject_id": edge.source,
            "object_id": edge.target,
            "confidence": edge.properties.get("confidence", rand_confidence(self.rng)),
            "source_doc_id": doc_id,
            "created_at": iso_datetime(now_utc()),
            "updated_at": iso_datetime(now_utc()),
        }
        # keep time validity aligned
        if edge.properties.get("effective_from"):
            as_props["effective_from"] = edge.properties.get("effective_from")
        if edge.properties.get("effective_to"):
            as_props["effective_to"] = edge.properties.get("effective_to")

        self._add_node(NodeRow(id=as_node_id, labels="Entity;Assertion", properties=as_props))

        # Connect assertion -> evidence -> document
        if "ASSERTION_SUPPORTED_BY" in self.schema["edge_types"]:
            self._make_edge("ASSERTION_SUPPORTED_BY", as_node_id, ev_node_id, overrides={"source_doc_id": doc_id})
        if "EVIDENCE_FROM_DOCUMENT" in self.schema["edge_types"]:
            self._make_edge("EVIDENCE_FROM_DOCUMENT", ev_node_id, doc_node_id, overrides={"source_doc_id": doc_id})

        # Connect assertion to subject/object
        if "ASSERTS_SUBJECT" in self.schema["edge_types"]:
            self._make_edge("ASSERTS_SUBJECT", as_node_id, edge.source, overrides={"source_doc_id": doc_id})
        if "ASSERTS_OBJECT" in self.schema["edge_types"]:
            self._make_edge("ASSERTS_OBJECT", as_node_id, edge.target, overrides={"source_doc_id": doc_id})

    def _seed_core_scenario(self) -> None:
        """
        Create a coherent sales/adviser micro-world so visualization isn't purely random.
        """
        # Ensure at least one "Guardian Financial Services" org
        orgs = self.nodes_by_type.get("Organization", [])
        if orgs:
            guardian_id = orgs[0]
            # Patch the node properties for nicer naming
            for n in self.nodes:
                if n.id == guardian_id:
                    n.properties["name"] = "Guardian Financial Services (MOCK)"
                    n.properties["description"] = "MOCK: The insurer/organization represented in this dataset."
                    self.node_index[guardian_id]["name"] = n.properties["name"]
                    self.node_index[guardian_id]["description"] = n.properties["description"]
                    break

        # Create a few adviser firms + advisers + prospects
        persons = self.nodes_by_type.get("Person", [])
        advisers_v5 = self.nodes_by_type.get("Adviser", [])
        firms = self.nodes_by_type.get("AdviserFirm", [])
        networks = self.nodes_by_type.get("AdviserNetwork", [])
        funnel_stages = self.nodes_by_type.get("FunnelStage", [])

        # V5: Use explicit Adviser nodes if available, else fallback to Person
        active_advisers = advisers_v5 if advisers_v5 else persons[: min(8, len(persons))]
        prospects = persons[min(8, len(persons)) : min(8 + 10, len(persons))]

        if not orgs:
            return

        # V5: Link Firms to Networks
        if firms and networks and "FIRM_MEMBER_OF_NETWORK" in self.schema["edge_types"]:
            for f in firms:
                self._make_edge("FIRM_MEMBER_OF_NETWORK", f, self.rng.choice(networks))

        # V5: Link Advisers to Firms
        if active_advisers and firms and "ADVISER_AT" in self.schema["edge_types"]:
            for a in active_advisers:
                self._make_edge("ADVISER_AT", a, self.rng.choice(firms))

        # V5: Link Prospects to Funnel Stages
        if prospects and funnel_stages and "HAS_FUNNEL_STAGE" in self.schema["edge_types"]:
            for p in prospects:
                self._make_edge("HAS_FUNNEL_STAGE", p, self.rng.choice(funnel_stages))

        # Create roles (Legacy V4 support)
        roles = self.nodes_by_type.get("Role", [])
        if roles and not advisers_v5: # Only use Role if we don't have Adviser nodes
            adviser_role = roles[0]
            for n in self.nodes:
                if n.id == adviser_role:
                    n.properties["name"] = "Financial Adviser (MOCK)"
                    self.node_index[adviser_role]["name"] = n.properties["name"]
                    break
            
            # HAS_ROLE adviser -> role
            if "HAS_ROLE" in self.schema["edge_types"]:
                for a in active_advisers:
                    self._make_edge("HAS_ROLE", a, roles[0])

        # WORKS_FOR edges adviser -> org (Legacy V4)
        if "WORKS_FOR" in self.schema["edge_types"] and not advisers_v5:
            for a in active_advisers:
                self._make_edge("WORKS_FOR", a, orgs[0])

        # Interests/topics
        interests = self.nodes_by_type.get("Interest", [])
        topics = self.nodes_by_type.get("Topic", [])
        products = self.nodes_by_type.get("Product", [])
        
        if interests and topics and products:
            # Connect advisers to interests
            if "PERSON_HAS_INTEREST" in self.schema["edge_types"]:
                for a in active_advisers:
                    for _ in range(2):
                        self._make_edge("PERSON_HAS_INTEREST", a, self.rng.choice(interests))
            # Connect prospects to interests
            if "PERSON_HAS_INTEREST" in self.schema["edge_types"]:
                for p in prospects:
                    for _ in range(2):
                        self._make_edge("PERSON_HAS_INTEREST", p, self.rng.choice(interests))
            # Map interests to topics
            if "INTEREST_IN" in self.schema["edge_types"]:
                for it in interests[: min(10, len(interests))]:
                    self._make_edge("INTEREST_IN", it, self.rng.choice(topics))

            # Guardian offers products
            if "OFFERS_PRODUCT" in self.schema["edge_types"] and orgs:
                for pr in products[: min(6, len(products))]:
                    self._make_edge("OFFERS_PRODUCT", orgs[0], pr)

            # --- V5 SPECIFIC NAMED SEEDING ---
            # 1. Payout Planner (Service)
            pp_id = self._make_node_id("Service", 999)
            pp_node = NodeRow(id=pp_id, labels="Entity;Service", properties={
                "id": pp_id, "name": "Payout Planner", "description": "Beneficiary nomination tool.", "service_type": "digital_tool"
            })
            self._add_node(pp_node)
            # Link to products
            if "INCLUDES_SERVICE" in self.schema["edge_types"]:
                for pr in products[:3]:
                    self._make_edge("INCLUDES_SERVICE", pr, pp_id)

            # 2. Protection Builder 2.0 (Service)
            pb_id = self._make_node_id("Service", 998)
            pb_node = NodeRow(id=pb_id, labels="Entity;Service", properties={
                "id": pb_id, "name": "Protection Builder 2.0", "description": "Menu building platform.", "service_type": "digital_platform"
            })
            self._add_node(pb_node)
            # Link to Actions (create Actions first)
            for act_name in ["Quote", "Apply"]:
                act_id = self._make_node_id("Action", self.rng.randint(1000, 9000))
                act_node = NodeRow(id=act_id, labels="Entity;Action", properties={"id": act_id, "name": act_name, "description": f"Perform {act_name}"})
                self._add_node(act_node)
                if "ENABLES" in self.schema["edge_types"]:
                    self._make_edge("ENABLES", pb_id, act_id)

            # 3. Underwriting Qi (Service)
            qi_id = self._make_node_id("Service", 997)
            qi_node = NodeRow(id=qi_id, labels="Entity;Service", properties={
                "id": qi_id, "name": "Underwriting Qi", "description": "Presales underwriting tool.", "service_type": "digital_tool"
            })
            self._add_node(qi_node)
            # Link to features
            qif_id = self._make_node_id("Feature", 665)
            qif_node = NodeRow(id=qif_id, labels="Entity;Feature", properties={"id": qif_id, "name": "Full Rule Set", "description": "Contains full underwriting rules."})
            self._add_node(qif_node)
            if "HAS_FEATURE" in self.schema["edge_types"]:
                self._make_edge("HAS_FEATURE", qi_id, qif_id)

            # 4. Underwriting Guide (Service)
            ug_id = self._make_node_id("Service", 996)
            ug_node = NodeRow(id=ug_id, labels="Entity;Service", properties={
                "id": ug_id, "name": "Underwriting Guide", "description": "Interactive guide for frequent conditions.", "service_type": "digital_tool"
            })
            self._add_node(ug_node)

            # 5. Specific Life Events
            le_id = self._make_node_id("LifeEvent", 888)
            le_node = NodeRow(id=le_id, labels="Entity;LifeEvent", properties={
                "id": le_id, "name": "Buying a Home", "description": "Mortgage trigger.", "category": "financial"
            })
            self._add_node(le_node)
            if "TRIGGERS_NEED_FOR" in self.schema["edge_types"] and products:
                self._make_edge("TRIGGERS_NEED_FOR", le_id, products[0]) # Link to first product

            # 4. Specific Objection & Mitigation
            obj_id = self._make_node_id("Objection", 777)
            obj_node = NodeRow(id=obj_id, labels="Entity;Objection", properties={
                "id": obj_id, "name": "Price Objection", "statement": "Too expensive.", "category": "price"
            })
            self._add_node(obj_node)
            # Link feature to it
            feat_id = self._make_node_id("Feature", 666)
            feat_node = NodeRow(id=feat_id, labels="Entity;Feature", properties={
                "id": feat_id, "name": "Premium Waiver", "description": "Waiver included standard."
            })
            self._add_node(feat_node)
            if "MITIGATES" in self.schema["edge_types"]:
                self._make_edge("MITIGATES", feat_id, obj_id)
            if "HAS_FEATURE" in self.schema["edge_types"] and products:
                self._make_edge("HAS_FEATURE", products[0], feat_id)

            # Prospects have needs linked to topics/products (if types exist)
            needs = self.nodes_by_type.get("Need", [])
            if needs and "PERSON_HAS_NEED" in self.schema["edge_types"]:
                for p in prospects:
                    self._make_edge("PERSON_HAS_NEED", p, self.rng.choice(needs))

            # Recommendations (V5: RECOMMENDS_ACTION / V4: RECOMMENDS)
            recs = self.nodes_by_type.get("Recommendation", [])
            next_actions = self.nodes_by_type.get("NextBestAction", [])
            
            # V5 Recommendations
            if next_actions and "RECOMMENDS_ACTION" in self.schema["edge_types"]:
                 for a in active_advisers:
                     action = self.rng.choice(next_actions)
                     # Who gets the recommendation? The system recommends it TO the adviser
                     # But current edge is RECOMMENDS_ACTION (System -> Action). 
                     # Let's assume we link Adviser -> NextBestAction if valid edge exists, or implicit
                     pass

            # V4 Recommendations
            if recs:
                if "RECOMMENDS" in self.schema["edge_types"]:
                    for a in active_advisers:
                        self._make_edge("RECOMMENDS", a, self.rng.choice(recs))
                # rec -> product
                if "RECOMMENDATION_FOR" in self.schema["edge_types"]:
                    for r in recs[: min(10, len(recs))]:
                        self._make_edge("RECOMMENDATION_FOR", r, self.rng.choice(products))

        # Campaigns/sequences/templates
        campaigns = self.nodes_by_type.get("Campaign", [])
        sequences = self.nodes_by_type.get("Sequence", [])
        steps = self.nodes_by_type.get("SequenceStep", [])
        templates = self.nodes_by_type.get("EmailTemplate", [])
        if campaigns and sequences and steps and templates:
            if "CAMPAIGN_HAS_SEQUENCE" in self.schema["edge_types"]:
                for c in campaigns:
                    self._make_edge("CAMPAIGN_HAS_SEQUENCE", c, self.rng.choice(sequences))
            if "SEQUENCE_HAS_STEP" in self.schema["edge_types"]:
                for s in sequences:
                    for _ in range(3):
                        self._make_edge("SEQUENCE_HAS_STEP", s, self.rng.choice(steps))
            if "STEP_USES_TEMPLATE" in self.schema["edge_types"]:
                for st in steps[: min(20, len(steps))]:
                    self._make_edge("STEP_USES_TEMPLATE", st, self.rng.choice(templates))

        # Add a few objections/responses to show sales handling
        objections = self.nodes_by_type.get("Objection", [])
        responses = self.nodes_by_type.get("Response", [])
        if objections and responses and "ADDRESSES_OBJECTION" in self.schema["edge_types"]:
            for r in responses[: min(10, len(responses))]:
                self._make_edge("ADDRESSES_OBJECTION", r, self.rng.choice(objections))

    def _seed_advanced_scenarios(self) -> None:
        """
        Generate complex chains for v5 schema features: Governance, Playbooks, Engagement, Claims.
        """
        products = self.nodes_by_type.get("Product", [])
        cd_outcomes = self.nodes_by_type.get("ConsumerDutyOutcome", [])
        fv_assessments = self.nodes_by_type.get("FairValueAssessment", [])
        sales_plays = self.nodes_by_type.get("SalesPlay", [])
        funnel_stages = self.nodes_by_type.get("FunnelStage", [])
        email_templates = self.nodes_by_type.get("EmailTemplate", [])
        advisers = self.nodes_by_type.get("Adviser", []) or self.nodes_by_type.get("Person", [])[:5]
        prospects = self.nodes_by_type.get("Person", [])[5:15] # Grab some prospects
        
        # 1. Product Governance Loop
        if products and cd_outcomes and "ASSESSES_CONSUMER_DUTY_OUTCOME" in self.schema["edge_types"]:
            # Link Assessments to Products and Outcomes
            for fva in fv_assessments:
                target_prod = self.rng.choice(products)
                if "HAS_FAIR_VALUE_ASSESSMENT" in self.schema["edge_types"]:
                    self._make_edge("HAS_FAIR_VALUE_ASSESSMENT", target_prod, fva)
                
                # Link assessment to all 4 outcomes
                for cdo in cd_outcomes:
                    self._make_edge("ASSESSES_CONSUMER_DUTY_OUTCOME", fva, cdo)

        # 2. Sales Playbook & Funnel Logic
        if sales_plays and funnel_stages:
            # Assign plays to stages
            if "PLAY_APPLIES_TO_STAGE" in self.schema["edge_types"]: # Hypothetical edge, check/use generic
                # Actually v5 schema has RECOMMENDS_ACTION which links NextBestAction. 
                # Let's use a generic 'RELATED_TO' if available or just assume implicit logic.
                # v5 has HAS_FUNNEL_STAGE on Person.
                pass
            
            # SalesPlay -> EmailTemplate
            if email_templates and "PLAY_USES_TEMPLATE" in self.schema["edge_types"]: # Check if exists?
                # Actually, SalesPlay usually links to ContentAsset/Action.
                # Let's assume SalesPlay -> ContentAsset -> EmailTemplate?
                pass 

        # 3. Engagement Signals
        # Simulate some signals for prospects
        if prospects and "GENERATED_SIGNAL" in self.schema["edge_types"]:
            for p in prospects:
                # Create Interaction
                i_idx = len(self.nodes_by_type.get("Interaction", []))
                i_id = self._make_node_id("Interaction", i_idx)
                i_node = NodeRow(id=i_id, labels="Entity;Interaction", properties={
                    "id": i_id, "name": "Email Open", "type": "email_open", "timestamp": iso_datetime(now_utc())
                })
                self._add_node(i_node)
                
                # Link Interaction to Person (INVOLVES_PERSON is standard)
                if "INVOLVES_PERSON" in self.schema["edge_types"]:
                    self._make_edge("INVOLVES_PERSON", i_node.id, p)

                # Create Signal
                sig_idx = len(self.nodes_by_type.get("EngagementSignal", []))
                sig_id = self._make_node_id("EngagementSignal", sig_idx)
                sig_node = NodeRow(id=sig_id, labels="Entity;EngagementSignal", properties={
                    "id": sig_id, "name": "High Intent Signal", "score": 85, "type": "open"
                })
                self._add_node(sig_node)
                
                self._make_edge("GENERATED_SIGNAL", i_node.id, sig_node.id)

    def generate(self) -> None:
        # 1) Create nodes
        for node_type in self.schema["node_types"].keys():
            count = self.node_count_overrides.get(node_type, self.base_nodes_per_type)
            for i in range(count):
                n = self._make_node(node_type, i)
                self._add_node(n)

        # 2) Make sure DocumentSections/EvidenceSnippets reference a real Document.doc_id
        if self.doc_ids:
            for n in self.nodes:
                ntype = n.labels.split(";")[-1]
                if ntype in ("DocumentSection", "EvidenceSnippet") and not n.properties.get("doc_id"):
                    n.properties["doc_id"] = self.rng.choice(self.doc_ids)

        # 3) Seed coherent sales scenario edges
        self._seed_core_scenario()
        
        # 3b) Seed advanced scenarios (v5)
        self._seed_advanced_scenarios()

        # 4) Alias handling (NameVariant) for some key entities
        for nt in ("Product", "Service", "Topic", "Feature", "Benefit", "Regulation", "Campaign"):
            for ent_id in self.nodes_by_type.get(nt, [])[: max(1, int(len(self.nodes_by_type.get(nt, [])) * 0.5))]:
                self._maybe_add_alias(ent_id)

        # 5) Generate edges for each edge type (schema coverage)
        # If include_reverse_edges=False, we still generate edges for ALL edge_types as defined;
        # if True and an edge_type has a reverse_type, we will also add the reverse instance.
        for edge_type, edef in self.schema["edge_types"].items():
            from_types = edef.get("from", []) or []
            to_types = edef.get("to", []) or []
            if not from_types or not to_types:
                continue

            target_k = max(1, int(self.edges_per_type))
            tries = 0
            made = 0
            while made < target_k and tries < target_k * 25:
                tries += 1
                ft = self.rng.choice(from_types)
                tt = self.rng.choice(to_types)

                src_pool = self.nodes_by_type.get(ft, [])
                tgt_pool = self.nodes_by_type.get(tt, [])
                if not src_pool or not tgt_pool:
                    continue

                src = self.rng.choice(src_pool)
                tgt = self.rng.choice(tgt_pool)
                if src == tgt:
                    continue

                e = self._make_edge(edge_type, src, tgt)
                if e is None:
                    continue

                made += 1

                # optional reverse
                if self.include_reverse_edges:
                    rev = edef.get("reverse_type")
                    if rev and rev in self.schema["edge_types"]:
                        self._make_edge(rev, tgt, src)

                # Create provenance (assertions + evidence snippets)
                self._create_provenance_for_edge(e)

        # 6) Create provenance for the scenario edges that were created before step 5
        # (Those edges are already in self.edges; but provenance was only added for edges generated in step 5.)
        if self.with_provenance:
            # Only for "domain edges" without assertion already
            # We'll do a light pass to avoid explosion.
            for e in self.edges[: min(500, len(self.edges))]:
                self._create_provenance_for_edge(e)

    def export(self, outdir: str) -> Dict[str, Any]:
        os.makedirs(outdir, exist_ok=True)

        # Create a consistent set of columns for nodes by unioning property keys
        node_prop_keys = set()
        for n in self.nodes:
            node_prop_keys.update(n.properties.keys())
        node_cols = ["id", "labels"] + sorted(node_prop_keys)

        nodes_csv = os.path.join(outdir, "nodes.csv")
        with open(nodes_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=node_cols, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            for n in self.nodes:
                row = {"id": n.id, "labels": n.labels}
                for k in node_prop_keys:
                    v = n.properties.get(k, "")
                    if isinstance(v, (dict, list)):
                        row[k] = json_str(v)
                    else:
                        row[k] = safe_str(v)
                w.writerow(row)

        edge_prop_keys = set()
        for e in self.edges:
            edge_prop_keys.update(e.properties.keys())
        edge_cols = ["source", "target", "type"] + sorted(edge_prop_keys)

        edges_csv = os.path.join(outdir, "edges.csv")
        with open(edges_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=edge_cols, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            for e in self.edges:
                row = {"source": e.source, "target": e.target, "type": e.type}
                for k in edge_prop_keys:
                    v = e.properties.get(k, "")
                    if isinstance(v, (dict, list)):
                        row[k] = json_str(v)
                    else:
                        row[k] = safe_str(v)
                w.writerow(row)

        # GraphML export
        graphml_path = os.path.join(outdir, "mock_guardian.graphml")
        if nx is not None:
            G = nx.MultiDiGraph()
            for n in self.nodes:
                # Put node_type as primary type for visualization
                node_type = n.labels.split(";")[-1]
                attrs = {"node_type": node_type}
                attrs.update({k: v for k, v in n.properties.items() if isinstance(v, (str, int, float, bool))})
                G.add_node(n.id, **attrs)
            for e in self.edges:
                attrs = {"type": e.type}
                # keep a few edge props for display
                for k in ("confidence", "jurisdiction", "effective_from", "effective_to", "source_doc_id", "rel_id"):
                    if k in e.properties:
                        attrs[k] = e.properties.get(k)
                G.add_edge(e.source, e.target, **attrs)
            nx.write_graphml(G, graphml_path)

        stats = {
            "seed": self.seed,
            "scale": self.scale,
            "nodes_total": len(self.nodes),
            "edges_total": len(self.edges),
            "node_types": {nt: len(ids) for nt, ids in sorted(self.nodes_by_type.items(), key=lambda x: (-len(x[1]), x[0]))},
        }
        with open(os.path.join(outdir, "stats.json"), "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        return {
            "nodes_csv": nodes_csv,
            "edges_csv": edges_csv,
            "graphml": graphml_path if os.path.exists(graphml_path) else "",
            "stats_json": os.path.join(outdir, "stats.json"),
            "stats": stats,
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True, help="Path to guardian_kg_schema_*.json")
    ap.add_argument("--outdir", required=True, help="Output directory for CSV/GraphML")
    ap.add_argument("--scale", default="small", choices=["small", "medium", "large"])
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--edges-per-type", type=int, default=None, dest="edges_per_type")
    ap.add_argument("--include-reverse-edges", action="store_true")
    ap.add_argument("--no-provenance", action="store_true", help="Disable Assertion/Evidence generation")
    ap.add_argument("--alias-rate", type=float, default=0.20, help="Probability of adding a NameVariant to eligible entities")

    args = ap.parse_args()

    with open(args.schema, "r", encoding="utf-8") as f:
        schema = json.load(f)

    gen = MockKGGenerator(
        schema=schema,
        seed=args.seed,
        scale=args.scale,
        edges_per_type=args.edges_per_type,
        include_reverse_edges=args.include_reverse_edges,
        with_provenance=(not args.no_provenance),
        alias_rate=args.alias_rate,
    )
    gen.generate()
    out = gen.export(args.outdir)

    print("Wrote:")
    for k in ("nodes_csv", "edges_csv", "graphml", "stats_json"):
        print(f"  - {k}: {out.get(k)}")
    print("Summary:")
    print(json.dumps(out["stats"], indent=2))


if __name__ == "__main__":
    main()
