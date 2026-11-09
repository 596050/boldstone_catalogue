#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_TEXT = (
    "[Our Income Protection provides the ultimate cover for illness and injury.] "
    "Whether a client is employed or self-employed, it has all the options you need to tailor cover "
    "to their situation and budget.\n\n"
    "And with our own job rather than own occupation definition, your clients benefit from a greater "
    "certainty of payout.\n\n"
    "Read on to find out more."
)

DEFAULT_LABELS = [
    "Product:Insurance product type or name (e.g. Income Protection, Life Cover, Critical Illness).",
    "Feature:Named feature or option of the product (e.g. own occupation definition, waiver of premium).",
    "Premium:Explicit premium amount or mention of premium payment (e.g. GBP 20/month, monthly premium).",
    "BenefitValue:Numeric benefit amount or percent (e.g. GBP 100,000, 60% of earnings).",
    "CoverType:Cover structure over time (level, increasing, decreasing, family income benefit).",
    "PayoutType:Benefit payment form (lump sum, monthly income).",
    "CoverBasis:Formula used to calculate benefit (e.g. 65% of earnings).",
    "DeferredPeriod:Waiting period before benefits begin (e.g. 4 weeks, 13 weeks).",
    "PaymentPeriod:Duration benefits are paid (e.g. 2 years, to age 65).",
    "Exclusion:Explicit exclusions (e.g. self-inflicted injury, pre-existing conditions).",
    "AgeLimit:Entry or expiry age limits.",
    "CoverLimit:Maximum or minimum cover amounts.",
    "PolicyTerm:Policy term length (years, months, or to age).",
    "Benefit:Included benefit or add-on (e.g. waiver of premium, global treatment).",
    "PremiumRule:Premium change rules (guaranteed, reviewable, indexation).",
    "PaymentMethod:How premiums are paid (direct debit, payroll).",
    "Policy:Mentions of the policy or contract itself.",
    "Cover:Specific cover within a policy (life cover, terminal illness).",
    "PolicyStatus:Lifecycle status (quoted, applied, in force, lapsed).",
    "PolicyType:Policy structure (single, joint, dual, combined).",
    "PolicyOption:Optional rider or option (guaranteed increase, immediate cover).",
    "Promise:Named promise, guarantee, or pledge.",
    "PremiumType:Premium basis (guaranteed vs reviewable).",
    "PremiumFrequency:Payment frequency (monthly, annual).",
    "Index:Indexation reference (RPI, CPI).",
    "DefinitionType:Eligibility or claim definition (own job, own occupation, ADL).",
    "CustomerNeed:Stated customer need (budget, mortgage protection, family security).",
    "ValueProposition:Outcome or benefit claim (certainty of payout, peace of mind).",
    "EmploymentStatus:Employment status (employed, self-employed, unemployed).",
    "TargetPersona:Target persona (parents, homeowners, professionals).",
    "ProductTargetCustomers:Target segment (self-employed, families, high net worth).",
    "ProductEligibility:Eligibility criteria (resident, age, BMI).",
    "ProductCoverDetails:What the product covers (illness, injury, death).",
    "ProductPremium:Pricing info (premium amount, reviewable or guaranteed).",
    "ProductClaims:Claims info or stats.",
    "ProductExclusions:Product exclusions (pre-existing conditions, hazardous sports).",
    "ProductBenefits:Included product benefits (waiver of premium, global treatment).",
    "COVERS:Relation: Product covers condition or trigger.",
    "EXCLUDES:Relation: Product excludes condition or activity.",
    "REQUIRES:Relation: Product requires eligibility or risk criteria.",
    "OFFERS:Relation: Organization or product offers service or benefit.",
    "LIMITS:Relation: Product limits age, amount, or term.",
    "APPLIES_TO:Relation: Rule or feature applies to persona or product.",
    "CALCULATED_BY:Relation: Benefit calculated by basis.",
    "PAID_VIA:Relation: Benefit paid via method.",
    "TARGETS:Relation: Product targets persona or segment.",
    "ADDRESSES:Relation: Product or feature addresses a need.",
    "DELIVERS:Relation: Product or feature delivers value proposition.",
    "SUPERIOR_TO:Relation: Comparative claim (rather than or better than).",
]

DEFAULT_THRESHOLD = 0.7
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NER_CONFIG_PATH = (
    REPO_ROOT
    / "experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/"
    / "rag_solr_knowledge_graph/stages/stage_0_ingestion/ner_config.json"
)
DEFAULT_INPUT_DIR = (
    REPO_ROOT
    / "experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/standardized"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/ner_output"
)
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "gliner_ml_extraction_output.txt"
DEFAULT_OUTPUT_SUFFIX = ".gliner.txt"

RELATION_LABELS = {
    "COVERS",
    "EXCLUDES",
    "REQUIRES",
    "OFFERS",
    "LIMITS",
    "APPLIES_TO",
    "CALCULATED_BY",
    "PAID_VIA",
    "TARGETS",
    "ADDRESSES",
    "DELIVERS",
    "SUPERIOR_TO",
}

NUMBER_RE = re.compile(r"\d")
CURRENCY_RE = re.compile(r"\b(gbp|usd|eur|cad|aud|pound|dollar|euro)s?\b", re.I)
TIME_RE = re.compile(r"\b(day|week|month|year)s?\b|\bto age\b", re.I)
PAYOUT_RE = re.compile(r"\b(lump sum|monthly|income)\b", re.I)
COVER_TYPE_RE = re.compile(
    r"\b(level|increasing|decreasing|family income benefit)\b", re.I
)
EMP_STATUS_RE = re.compile(r"\b(employed|self-employed|unemployed|retired)\b", re.I)
DEF_TYPE_RE = re.compile(
    r"\b(own job|own occupation|any occupation|activities of daily living|adl)\b",
    re.I,
)
POLICY_TYPE_RE = re.compile(
    r"\b(single|joint|dual|stand[- ]alone|combined|accelerated)\b", re.I
)
POLICY_STATUS_RE = re.compile(
    r"\b(quoted|applied|in force|lapsed|cancelled|reinstated)\b", re.I
)
PREMIUM_TYPE_RE = re.compile(r"\b(guaranteed|reviewable|level)\b", re.I)
PREMIUM_FREQ_RE = re.compile(r"\b(monthly|annually|annual|weekly|quarterly)\b", re.I)
INDEX_RE = re.compile(r"\b(rpi|cpi|inflation)\b", re.I)
PRODUCT_RE = re.compile(
    r"\b(income protection|life (insurance|cover|protection)|critical illness|accident|sickness)\b",
    re.I,
)

RELATION_PATTERNS = {
    "COVERS": [
        re.compile(r"\bcover(?:s|age)?(?: for)? ([^.\n;]+)", re.I),
    ],
    "EXCLUDES": [
        re.compile(r"\bexclude(?:s|d|ing)? ([^.\n;]+)", re.I),
        re.compile(r"\bdoes not cover ([^.\n;]+)", re.I),
        re.compile(r"\bnot covered:? ([^.\n;]+)", re.I),
    ],
    "REQUIRES": [
        re.compile(r"\brequire(?:s|d|ing)? ([^.\n;]+)", re.I),
        re.compile(r"\bmust ([^.\n;]+)", re.I),
        re.compile(r"\bneed(?:s)? to ([^.\n;]+)", re.I),
    ],
    "OFFERS": [
        re.compile(r"\boffer(?:s|ed|ing)? ([^.\n;]+)", re.I),
    ],
    "LIMITS": [
        re.compile(r"\blimit(?:s|ed|ing)? ([^.\n;]+)", re.I),
        re.compile(r"\bup to ([^.\n;]+)", re.I),
        re.compile(r"\bmaximum ([^.\n;]+)", re.I),
        re.compile(r"\bminimum ([^.\n;]+)", re.I),
    ],
    "APPLIES_TO": [
        re.compile(r"\bappl(?:y|ies) to ([^.\n;]+)", re.I),
    ],
    "CALCULATED_BY": [
        re.compile(r"\bcalculated by ([^.\n;]+)", re.I),
        re.compile(r"\bbased on ([^.\n;]+)", re.I),
    ],
    "PAID_VIA": [
        re.compile(r"\bpaid via ([^.\n;]+)", re.I),
        re.compile(r"\bpaid as ([^.\n;]+)", re.I),
        re.compile(r"\bpaid in ([^.\n;]+)", re.I),
    ],
    "TARGETS": [
        re.compile(r"\btarget(?:s|ed)? (?:at|to) ([^.\n;]+)", re.I),
        re.compile(r"\baimed at ([^.\n;]+)", re.I),
    ],
    "ADDRESSES": [
        re.compile(r"\baddress(?:es|ed|ing)? ([^.\n;]+)", re.I),
        re.compile(r"\bdesigned for ([^.\n;]+)", re.I),
        re.compile(r"\btailor(?:s|ed)? to ([^.\n;]+)", re.I),
    ],
    "DELIVERS": [
        re.compile(r"\bbenefit from ([^.\n;]+)", re.I),
        re.compile(r"\bdeliver(?:s|ed|ing)? ([^.\n;]+)", re.I),
    ],
    "SUPERIOR_TO": [
        re.compile(r"\brather than ([^.\n;]+)", re.I),
        re.compile(r"\bbetter than ([^.\n;]+)", re.I),
        re.compile(r"\binstead of ([^.\n;]+)", re.I),
    ],
}


def resolve_gliner_url(worker_url: str, gliner_extract_url: str) -> str:
    if gliner_extract_url:
        return gliner_extract_url
    if worker_url:
        return worker_url.rstrip("/") + "/gliner/extract"
    return "http://127.0.0.1:8000/extract"


def load_payload(payload_file: str | None) -> dict:
    if payload_file:
        with open(payload_file, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "text": DEFAULT_TEXT,
        "labels": DEFAULT_LABELS,
        "threshold": DEFAULT_THRESHOLD,
    }


def load_ner_config(config_path: str | None) -> dict:
    path = Path(config_path) if config_path else DEFAULT_NER_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"ner_config.json not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_from_json(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        print(f"Skipping {path.name}: {err}", file=sys.stderr)
        return None
    if isinstance(data, dict):
        text = data.get("text") or data.get("content") or data.get("body")
    else:
        text = None
    if not text or not isinstance(text, str):
        print(f"Skipping {path.name}: missing text field", file=sys.stderr)
        return None
    return text


def collect_input_files(
    input_dir: str, input_file: str, limit: int | None
) -> list[Path]:
    paths: list[Path] = []
    if input_file:
        file_path = Path(input_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")
        paths.append(file_path)
    if input_dir:
        dir_path = Path(input_dir)
        if not dir_path.exists():
            raise FileNotFoundError(f"Input dir not found: {dir_path}")
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Input dir is not a directory: {dir_path}")
        paths.extend(sorted(dir_path.glob("*.json")))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    if limit and limit > 0:
        unique = unique[:limit]
    return unique


def resolve_output_suffix(raw_suffix: str) -> str:
    if not raw_suffix:
        return DEFAULT_OUTPUT_SUFFIX
    return raw_suffix if raw_suffix.startswith(".") else f".{raw_suffix}"


from typing import Any

def flatten_entity_labels(config_obj) -> list[tuple[str, Any]]:
    labels: list[tuple[str, Any]] = []
    if isinstance(config_obj, dict):
        for key, value in config_obj.items():
            if isinstance(value, dict) and "description" in value:
                # Return the whole dict (description, dtype, etc.)
                labels.append((key, value))
            elif isinstance(value, dict):
                labels.extend(flatten_entity_labels(value))
    return labels


def flatten_relation_labels(config_obj) -> list[tuple[str, Any]]:
    labels: list[tuple[str, Any]] = []
    if isinstance(config_obj, dict):
        for key, value in config_obj.items():
            if isinstance(value, str):
                labels.append((key, value))
            elif isinstance(value, dict):
                labels.extend(flatten_relation_labels(value))
    return labels


def parse_labels(labels) -> tuple[list[str], dict[str, Any], list[tuple[str, Any]]]:
    label_desc: dict[str, Any] = {}
    label_names: list[str] = []
    label_pairs: list[tuple[str, Any]] = []

    if isinstance(labels, dict):
        for name, config in labels.items():
            if not isinstance(name, str):
                continue
            # config can be string (desc) or dict
            label_desc.setdefault(name, config)
            if name not in label_names:
                label_names.append(name)
            label_pairs.append((name, config))
        return label_names, label_desc, label_pairs

    if isinstance(labels, list):
        for item in labels:
            if not isinstance(item, str):
                continue
            if ":" in item:
                name, desc = item.split(":", 1)
                name = name.strip()
                desc = desc.strip()
            else:
                name = item.strip()
                desc = ""
            if not name:
                continue
            label_desc.setdefault(name, desc)
            if name not in label_names:
                label_names.append(name)
            label_pairs.append((name, desc))
        return label_names, label_desc, label_pairs

    raise ValueError("labels must be a list or dict")


def dedupe_label_pairs(pairs: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    desc_map: dict[str, Any] = {}
    order: list[str] = []
    for label, config in pairs:
        if label in desc_map and label in order:
            order.remove(label)
        desc_map[label] = config
        order.append(label)
    return [(label, desc_map[label]) for label in order]


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def clean_value(value: str) -> str:
    return value.strip().strip("[](){}<>\"' \t\r\n.,;:")


def split_phrase(phrase: str) -> list[str]:
    cleaned = clean_value(phrase)
    parts = re.split(r"\s+and\s+|,\s*", cleaned)
    return [clean_value(part) for part in parts if part.strip()]


def unique_preserve(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for val in values:
        if val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def should_keep_value(label: str, value: str) -> bool:
    lower = value.lower()
    if label in {"Premium", "ProductPremium"}:
        return (
            "premium" in lower or NUMBER_RE.search(value) or CURRENCY_RE.search(value)
        )
    if label in {"BenefitValue", "CoverLimit"}:
        return NUMBER_RE.search(value) is not None or CURRENCY_RE.search(value)
    if label in {"CoverBasis"}:
        return ("%" in value or "percent" in lower) or NUMBER_RE.search(value)
    if label in {"DeferredPeriod", "PaymentPeriod", "PolicyTerm"}:
        return TIME_RE.search(value) or NUMBER_RE.search(value)
    if label == "CoverType":
        return COVER_TYPE_RE.search(value) is not None
    if label == "PayoutType":
        return PAYOUT_RE.search(value) is not None
    if label == "DefinitionType":
        return DEF_TYPE_RE.search(value) is not None
    if label == "EmploymentStatus":
        return EMP_STATUS_RE.search(value) is not None
    if label == "PolicyType":
        return POLICY_TYPE_RE.search(value) is not None
    if label == "PolicyStatus":
        return POLICY_STATUS_RE.search(value) is not None
    if label == "PremiumType":
        return PREMIUM_TYPE_RE.search(value) is not None
    if label == "PremiumFrequency":
        return PREMIUM_FREQ_RE.search(value) is not None
    if label == "Index":
        return INDEX_RE.search(value) is not None
    if label == "Product":
        return PRODUCT_RE.search(value) is not None
    if label == "ProductEligibility":
        return any(
            term in lower
            for term in ("eligible", "eligibility", "resident", "age", "bmi")
        )
    return True


def filter_entities(
    agg: dict[str, list[dict]], relation_labels: set[str]
) -> dict[str, list[dict]]:
    filtered: dict[str, list[dict]] = {}
    for label, items in agg.items():
        # Dedup by text value, keeping the one with highest confidence if available
        seen: dict[str, dict] = {}
        
        for item in items:
            text = item.get("text", "")
            cleaned_text = clean_value(text)
            if not cleaned_text:
                continue
            
            # Check filtering rules
            if label not in relation_labels:
                if not should_keep_value(label, cleaned_text):
                    continue
            
            # If we haven't seen this text, or if this item has higher confidence, store it
            # (Note: GLiNER relations converted to dicts won't have confidence, treating as 0 or None)
            existing = seen.get(cleaned_text)
            current_conf = item.get("confidence")
            
            if existing is None:
                # Update text to cleaned version
                item["text"] = cleaned_text
                seen[cleaned_text] = item
            else:
                existing_conf = existing.get("confidence")
                # If current has confidence and existing doesn't, or current is higher
                if current_conf is not None:
                    if existing_conf is None or current_conf > existing_conf:
                        item["text"] = cleaned_text
                        seen[cleaned_text] = item
        
        if seen:
            filtered[label] = list(seen.values())
            
    return filtered


def extract_relations(
    sentences: list[str], relation_labels: set[str]
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for sentence in sentences:
        for label in relation_labels:
            patterns = RELATION_PATTERNS.get(label, [])
            for pattern in patterns:
                for match in pattern.findall(sentence):
                    values = split_phrase(match)
                    if not values:
                        continue
                    out.setdefault(label, []).extend(values)
    for label, values in out.items():
        out[label] = unique_preserve(values)
    return out


def normalize_entities(data: dict) -> dict[str, list[dict]]:
    entities_root = data.get("entities")
    found: dict[str, list[dict]] = {}
    if isinstance(entities_root, list):
        for ent in entities_root:
            if not isinstance(ent, dict):
                continue
            label = ent.get("label")
            text = ent.get("text")
            if label and text:
                entity_obj = {
                    "text": text,
                    "label": label,
                    "confidence": ent.get("score"),  # GLiNER usually returns 'score'
                    "start": ent.get("start"),
                    "end": ent.get("end"),
                }
                # Fallback if 'score' is missing but 'confidence' exists
                if entity_obj["confidence"] is None:
                    entity_obj["confidence"] = ent.get("confidence")
                
                found.setdefault(label, []).append(entity_obj)
    elif isinstance(entities_root, dict):
        # Handle legacy or alternative format if necessary, though list is standard
        if "entities" in entities_root and isinstance(entities_root["entities"], dict):
            entities_root = entities_root["entities"]
        if isinstance(entities_root, dict):
            for label, values in entities_root.items():
                if isinstance(values, list):
                    for v in values:
                        if isinstance(v, str):
                             found.setdefault(label, []).append({"text": v, "label": label})
                        elif isinstance(v, dict):
                             v["label"] = label
                             found.setdefault(label, []).append(v)
                elif values is not None:
                    found.setdefault(label, []).append({"text": str(values), "label": label})
    return found


def post_json(
    url: str,
    payload: dict,
    token: str,
    timeout_s: float,
    max_retries: int,
    backoff_s: float,
) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                body = resp.read()
            return json.loads(body)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as err:
            last_err = err
            if attempt >= max_retries:
                break
            sleep_s = backoff_s * (2**attempt)
            if sleep_s:
                print(
                    f"Retrying GLiNER request (attempt {attempt + 2}/{max_retries + 1}) in {sleep_s:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(sleep_s)
    raise last_err if last_err else RuntimeError("request failed")


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def format_status(found: bool, use_color: bool) -> str:
    if not use_color:
        return "FOUND" if found else "EMPTY"
    return "\033[32mFOUND\033[0m" if found else "\033[31mEMPTY\033[0m"


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def build_output_text(
    label_pairs: list[tuple[str, Any]],
    agg: dict[str, list[dict]],
    use_color: bool,
) -> str:
    if label_pairs:
        label_width = max(30, max(len(label) for label, _ in label_pairs))
    else:
        label_width = 30
    status_width = 10
    values_width = 40
    conf_width = 10

    lines: list[str] = []
    lines.append(
        f"{'LABEL':<{label_width}} | {'STATUS':<{status_width}} | {'CONF.':<{conf_width}} | {'VALUES':<{values_width}} | DESCRIPTION"
    )
    lines.append("-" * max(120, label_width + status_width + conf_width + values_width + 15))

    for label_name, config in label_pairs:
        # Extract description string if config is a dict
        if isinstance(config, dict):
            description = config.get("description", "")
        else:
            description = str(config)

        found_items = agg.get(label_name, [])
        if found_items:
            # Extract texts
            texts = [item.get("text", "") for item in found_items]
            values_str = ", ".join(texts)
            
            # Calculate average confidence
            scores = [item.get("confidence") for item in found_items if item.get("confidence") is not None]
            if scores:
                avg_conf = sum(scores) / len(scores)
                conf_str = f"{avg_conf:.2f}"
            else:
                conf_str = "-"
                
            status = format_status(True, use_color)
        else:
            values_str = "-"
            conf_str = "-"
            status = format_status(False, use_color)
            
        lines.append(
            f"{label_name:<{label_width}} | {status:<{status_width}} | {conf_str:<{conf_width}} | {values_str:<{values_width}} | {description}"
        )

    return "\n".join(lines)


def normalize_relations(data: dict) -> dict[str, list[dict]]:
    relations_root = data.get("relation_extraction")
    found: dict[str, list[dict]] = {}
    if isinstance(relations_root, list):
        for rel in relations_root:
            if not isinstance(rel, dict):
                continue
            # Structure: head: dict, tail: dict, label: str, score: float
            label = rel.get("label")
            head = rel.get("head", {})
            tail = rel.get("tail", {})
            
            if label:
                # Construct a readable text representation or keep structure?
                # For compatibility with filter_entities and output table which expect 'text'
                # We'll construct "Head -> Tail" string as text
                text_rep = f"{head.get('text', '')} -> {tail.get('text', '')}"
                
                entity_obj = {
                    "text": text_rep,
                    "label": label,
                    "confidence": rel.get("score"),
                    "head": head,
                    "tail": tail,
                    "start": head.get("start"), # Use head start
                    "end": tail.get("end")      # Use tail end
                }
                found.setdefault(label, []).append(entity_obj)
    return found

def format_description(name: str, config: Any, template: str) -> str:
    if isinstance(config, dict):
        desc = config.get("description", "")
        dtype = config.get("dtype", "")
    else:
        desc = str(config)
        dtype = ""
    
    if not template:
        return desc
    
    return template.replace("{label}", name).replace("{description}", desc).replace("{dtype}", dtype)


def extract_entities_api(
    sentence: str,
    labels: list[str],
    label_desc: dict[str, Any],
    gliner_url: str,
    relay_auth_token: str,
    labels_mode: str,
    chunk_size: int,
    timeout_s: float,
    max_retries: int,
    retry_backoff_s: float,
    threshold: float,
    label_template: str,
    template_map: dict[str, str],
) -> dict[str, list[dict]]:
    agg: dict[str, list[dict]] = {}
    
    for chunk in chunked(labels, chunk_size):
        chunk_payload = {
            "text": sentence,
            "threshold": threshold,
            "mode": "entities",
            "include_confidence": True,
            "include_spans": True,
        }
        
        if labels_mode == "schema":
            chunk_payload["labels"] = {
                name: format_description(name, label_desc.get(name, ""), label_template)
                for name in chunk
            }
        else: # list mode
            # Use template if available, else just name (or description? standard GLiNER list mode is just labels, but we usually want description prompting)
            # The previous code used template or just name.
            if label_template:
                chunk_payload["labels"] = [
                    format_description(name, label_desc.get(name, ""), label_template)
                    for name in chunk
                ]
            else:
                chunk_payload["labels"] = chunk

        print(
            f"Sending ENTITY request for {len(chunk)} labels...",
            file=sys.stderr,
        )

        resp = post_json(
            gliner_url,
            chunk_payload,
            relay_auth_token,
            timeout_s,
            max_retries,
            retry_backoff_s,
        )
        found = normalize_entities(resp)

        # Map back templates
        if template_map and labels_mode == "list":
            remapped_found = {}
            for label, items in found.items():
                original_name = template_map.get(label, label)
                for item in items:
                    item["label"] = original_name
                remapped_found[original_name] = items
            found = remapped_found

        for label, values in found.items():
            agg.setdefault(label, []).extend(values)
            
    return agg

def extract_relations_api(
    sentence: str,
    labels: list[str],
    label_desc: dict[str, Any],
    gliner_url: str,
    relay_auth_token: str,
    chunk_size: int,
    timeout_s: float,
    max_retries: int,
    retry_backoff_s: float,
    threshold: float,
) -> dict[str, list[dict]]:
    agg: dict[str, list[dict]] = {}
    
    # We can chunk relations too
    for chunk in chunked(labels, chunk_size):
        chunk_payload = {
            "text": sentence,
            "threshold": threshold,
            "mode": "relations",
            "include_confidence": True,
            "include_spans": True,
            # Relations usually don't need descriptions in list mode for extract_relations
            # But if we used schema mode they would. Let's assume list of labels for now.
            "labels": chunk 
        }
        
        print(
            f"Sending RELATION request for {len(chunk)} labels...",
            file=sys.stderr,
        )

        resp = post_json(
            gliner_url,
            chunk_payload,
            relay_auth_token,
            timeout_s,
            max_retries,
            retry_backoff_s,
        )
        found = normalize_relations(resp)

        for label, values in found.items():
            agg.setdefault(label, []).extend(values)
            
    return agg

def extract_mixed_api(
    sentence: str,
    entity_labels: list[str],
    relation_labels: list[str],
    label_desc: dict[str, Any],
    gliner_url: str,
    relay_auth_token: str,
    timeout_s: float,
    max_retries: int,
    retry_backoff_s: float,
    threshold: float,
    label_template: str,
) -> dict[str, list[dict]]:
    
    # Construct combined payload
    # Entities schema
    entities_payload = {
        name: format_description(name, label_desc.get(name, ""), label_template) 
        for name in entity_labels
    }
    
    # Relations schema (assuming label_desc contains relation descriptions)
    # Relations usually don't use templates or dtype, just description string
    relations_payload = {
        name: format_description(name, label_desc.get(name, ""), "") # No template for relations by default? Or same?
        # Assuming relations don't use the entity template.
        for name in relation_labels
    }
    
    payload = {
        "text": sentence,
        "threshold": threshold,
        "mode": "mixed",
        "entities": entities_payload,
        "relations": relations_payload,
        "include_confidence": True,
        "include_spans": True
    }
    
    print(f"Sending MIXED request for {len(entity_labels)} entities and {len(relation_labels)} relations...", file=sys.stderr)
    
    resp = post_json(
        gliner_url, 
        payload, 
        relay_auth_token, 
        timeout_s, 
        max_retries, 
        retry_backoff_s
    )
    
    agg = {}
    # Parse entities (looks for 'entities' key)
    ent_found = normalize_entities(resp)
    for k, v in ent_found.items():
        agg.setdefault(k, []).extend(v)
        
    # Parse relations (looks for 'relation_extraction' key)
    rel_found = normalize_relations(resp)
    for k, v in rel_found.items():
        agg.setdefault(k, []).extend(v)
        
    return agg

def extract_for_text(
    text: str,
    entity_labels: list[str],
    relation_labels: set[str],
    label_desc: dict[str, Any],
    gliner_url: str,
    relay_auth_token: str,
    labels_mode: str,
    chunk_size: int,
    timeout_s: float,
    max_retries: int,
    retry_backoff_s: float,
    sentence_split: bool,
    threshold: float,
    label_template: str = "",
    stream_handle=None,
) -> dict[str, list[dict]]:
    agg: dict[str, list[dict]] = {}
    sentences = split_sentences(text) if sentence_split else [text]

    # Pre-calculate templated labels if needed
    template_map = {} 
    if labels_mode == "list" and label_template:
        for name in entity_labels:
            config = label_desc.get(name, "")
            templated = format_description(name, config, label_template)
            template_map[templated] = name

    relation_list = list(relation_labels)

    for sentence in sentences:
        # Check if we can fit everything in one request
        if labels_mode == "schema" and (len(entity_labels) + len(relation_list) <= chunk_size):
             # Use Mixed Mode
             mixed_found = extract_mixed_api(
                 sentence, entity_labels, relation_list, label_desc, gliner_url, relay_auth_token,
                 timeout_s, max_retries, retry_backoff_s, threshold, label_template
             )
             for label, values in mixed_found.items():
                 agg.setdefault(label, []).extend(values)
                 
             # Stream write for mixed
             if stream_handle:
                 try:
                     stream_handle.write(json.dumps({"text": sentence, "found": mixed_found}) + "\n")
                     stream_handle.flush()
                 except OSError as err:
                     print(f"Stream write error: {err}", file=sys.stderr)
                     
        else:
            # Fallback to separate/chunked requests
            ent_found = {}
            rel_found = {}
            
            # Entities
            if entity_labels:
                ent_found = extract_entities_api(
                    sentence, entity_labels, label_desc, gliner_url, relay_auth_token,
                    labels_mode, chunk_size, timeout_s, max_retries, retry_backoff_s,
                    threshold, label_template, template_map
                )
                for label, values in ent_found.items():
                    agg.setdefault(label, []).extend(values)

            # Relations (API)
            if relation_labels:
                rel_found = extract_relations_api(
                    sentence, relation_list, label_desc, gliner_url, relay_auth_token,
                    chunk_size, timeout_s, max_retries, retry_backoff_s, threshold
                )
                for label, values in rel_found.items():
                    agg.setdefault(label, []).extend(values)

            # Stream write
            if stream_handle:
                try:
                    # Combine current sentence results for streaming
                    current_found = {}
                    if entity_labels:
                        for k, v in ent_found.items():
                            current_found.setdefault(k, []).extend(v)
                    if relation_labels:
                        for k, v in rel_found.items():
                            current_found.setdefault(k, []).extend(v)
                    
                    stream_handle.write(
                        json.dumps({"text": sentence, "found": current_found}) + "\n"
                    )
                    stream_handle.flush()
                except OSError as err:
                    print(f"Stream write error: {err}", file=sys.stderr)

    return filter_entities(agg, set(entity_labels) | relation_labels)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run GLiNER extraction against a local or relay endpoint.",
    )
    parser.add_argument("--payload-file", help="Path to JSON payload file.")
    parser.add_argument(
        "--ner-config",
        default=os.environ.get("GLINER_NER_CONFIG", str(DEFAULT_NER_CONFIG_PATH)),
        help="Path to ner_config.json.",
    )
    parser.add_argument(
        "--labels-source",
        choices=["config", "payload"],
        default=os.environ.get("GLINER_LABELS_SOURCE", "config"),
    )
    parser.add_argument(
        "--output-path",
        default=os.environ.get("GLINER_OUTPUT_PATH", str(DEFAULT_OUTPUT_PATH)),
        help="Write output table to this path.",
    )
    parser.add_argument(
        "--input-dir",
        default=os.environ.get("GLINER_INPUT_DIR", ""),
        help="Directory of standardized JSON files to process.",
    )
    parser.add_argument(
        "--input-file",
        default=os.environ.get("GLINER_INPUT_FILE", ""),
        help="Single standardized JSON file to process.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("GLINER_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory to write per-file outputs.",
    )
    parser.add_argument(
        "--output-suffix",
        default=os.environ.get("GLINER_OUTPUT_SUFFIX", DEFAULT_OUTPUT_SUFFIX),
        help="Suffix for per-file outputs (default: .gliner.txt).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("GLINER_INPUT_LIMIT", "0")),
        help="Limit number of input files processed (0 = no limit).",
    )
    parser.add_argument("--worker-url", default=os.environ.get("WORKER_URL", ""))
    parser.add_argument(
        "--gliner-extract-url",
        default=os.environ.get("GLINER_EXTRACT_URL", ""),
    )
    parser.add_argument(
        "--relay-auth-token",
        default=os.environ.get("RELAY_AUTH_TOKEN", ""),
    )
    parser.add_argument(
        "--labels-mode",
        choices=["list", "schema"],
        default=os.environ.get("GLINER_LABELS_MODE", "schema"),
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=int(os.environ.get("GLINER_LABEL_CHUNK_SIZE", "1")),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("GLINER_HTTP_TIMEOUT", "30")),
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=int(os.environ.get("GLINER_MAX_RETRIES", "3")),
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=float(os.environ.get("GLINER_RETRY_BACKOFF", "2")),
    )
    env_split = os.environ.get("GLINER_SENTENCE_SPLIT", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    parser.add_argument(
        "--sentence-split",
        dest="sentence_split",
        action="store_true",
        default=env_split,
        help="Split text into sentences before extraction.",
    )
    parser.add_argument(
        "--no-sentence-split",
        dest="sentence_split",
        action="store_false",
        help="Disable sentence splitting.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=(
            float(os.environ["GLINER_THRESHOLD"])
            if os.environ.get("GLINER_THRESHOLD")
            else None
        ),
        help="Override payload threshold.",
    )
    env_print = os.environ.get("GLINER_PRINT_OUTPUT", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    parser.add_argument(
        "--print-output",
        dest="print_output",
        action="store_true",
        default=env_print,
        help="Print output tables to stdout.",
    )
    parser.add_argument(
        "--no-print-output",
        dest="print_output",
        action="store_false",
        help="Suppress output tables; still writes files.",
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI color output."
    )

    args = parser.parse_args()

    gliner_url = resolve_gliner_url(args.worker_url, args.gliner_extract_url)
    payload = load_payload(args.payload_file)

    label_pairs: list[tuple[str, str]] = []
    relation_labels: set[str] = set()
    if args.labels_source == "config":
        try:
            config = load_ner_config(args.ner_config)
        except FileNotFoundError as err:
            print(str(err), file=sys.stderr)
            return 1
        entity_pairs = dedupe_label_pairs(
            flatten_entity_labels(config.get("entity_labels", {}))
        )
        relation_pairs = dedupe_label_pairs(
            flatten_relation_labels(config.get("relation_labels", {}))
        )
        label_pairs = dedupe_label_pairs(entity_pairs + relation_pairs)
        relation_labels = {label for label, _ in relation_pairs}
    else:
        labels = payload.get("labels", [])
        label_names, label_desc, label_pairs = parse_labels(labels)
        label_pairs = dedupe_label_pairs(label_pairs)
        relation_labels = {name for name in label_names if name in RELATION_LABELS}

    if not label_pairs:
        print("No labels found from config or payload.", file=sys.stderr)
        return 1

    label_desc = {label: desc for label, desc in label_pairs}
    label_names = [label for label, _ in label_pairs]
    
    # Get template from config if available
    label_template = config.get("gliner_label_template", "") if 'config' in locals() else ""

    if args.chunk_size < 1:
        args.chunk_size = 1

    entity_labels = [name for name in label_names if name not in relation_labels]
    use_color = not args.no_color and os.environ.get("NO_COLOR") is None

    threshold = payload.get("threshold", DEFAULT_THRESHOLD)
    if args.threshold is not None:
        threshold = args.threshold

    input_files: list[Path] = []
    if args.input_dir or args.input_file:
        try:
            input_files = collect_input_files(
                args.input_dir, args.input_file, args.limit
            )
        except (FileNotFoundError, NotADirectoryError) as err:
            print(str(err), file=sys.stderr)
            return 1

    if input_files:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = resolve_output_suffix(args.output_suffix)
        for input_path in input_files:
            text = load_text_from_json(input_path)
            if not text:
                continue
            
            stream_path = output_dir / f"{input_path.stem}.stream.jsonl"
            with stream_path.open("w", encoding="utf-8") as stream_handle:
                agg = extract_for_text(
                    text=text,
                    entity_labels=entity_labels,
                    relation_labels=relation_labels,
                    label_desc=label_desc,
                    gliner_url=gliner_url,
                    relay_auth_token=args.relay_auth_token,
                    labels_mode=args.labels_mode,
                    chunk_size=args.chunk_size,
                    timeout_s=args.timeout,
                    max_retries=args.max_retries,
                    retry_backoff_s=args.retry_backoff,
                    sentence_split=args.sentence_split,
                    threshold=threshold,
                    label_template=label_template,
                    stream_handle=stream_handle,
                )
            output_text = build_output_text(label_pairs, agg, use_color)
            output_path = output_dir / f"{input_path.stem}{suffix}"
            output_path.write_text(strip_ansi(output_text) + "\n", encoding="utf-8")
            if args.print_output:
                if len(input_files) > 1:
                    print(f"\n# {input_path.name}")
                print(output_text)
            else:
                print(f"Wrote {output_path}", file=sys.stderr)
        return 0

    text = payload.get("text", "")
    if not text:
        print("No input text available.", file=sys.stderr)
        return 1

    stream_path = (
        Path(args.output_path).with_suffix(".stream.jsonl")
        if args.output_path
        else Path("gliner_output.stream.jsonl")
    )
    
    with stream_path.open("w", encoding="utf-8") as stream_handle:
        agg = extract_for_text(
            text=text,
            entity_labels=entity_labels,
            relation_labels=relation_labels,
            label_desc=label_desc,
            gliner_url=gliner_url,
            relay_auth_token=args.relay_auth_token,
            labels_mode=args.labels_mode,
            chunk_size=args.chunk_size,
            timeout_s=args.timeout,
            max_retries=args.max_retries,
            retry_backoff_s=args.retry_backoff,
            sentence_split=args.sentence_split,
            threshold=threshold,
            label_template=label_template,
            stream_handle=stream_handle,
        )
    output_text = build_output_text(label_pairs, agg, use_color)

    if args.print_output:
        print(output_text)

    output_path = args.output_path.strip() if args.output_path else ""
    if output_path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(strip_ansi(output_text) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
