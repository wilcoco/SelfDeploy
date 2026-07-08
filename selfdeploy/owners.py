"""Owner resolution + routing — so cascade *distributes* instead of dumping.

Each control carries a functional role seed (품질/정비/구매/…) from its template.
An OwnerResolver turns that seed into a concrete owner, three ways (the CEO picks):

  1. org-chart    — a role → person map (조직도 입력)
  2. manual       — explicit per-control / per-tag assignment (의무별 수동 지정)
  3. llm          — infer the owner from the control's label (LLM 추론)

All three fall back to the template role, so an unmapped control still routes
somewhere. Then routing groups the risk register by owner: each role sees only
its own top gaps — a few narrow questions, never the whole taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .ir import Contract, ContractGraph
from .llm import DEFAULT_MODEL

Resolver = Callable[[Contract], Optional[str]]


def template_resolver() -> Resolver:
    """Baseline: the control's own template role is the owner label."""
    return lambda node: node.owner_role or None


def org_chart_resolver(role_to_owner: dict[str, str], base: Resolver | None = None) -> Resolver:
    """조직도 입력: map each functional role to a concrete person/team."""
    base = base or template_resolver()

    def resolve(node: Contract) -> Optional[str]:
        return role_to_owner.get(node.owner_role) or base(node)

    return resolve


def manual_resolver(overrides: dict[str, str], base: Resolver | None = None) -> Resolver:
    """의무별 수동 지정: explicit owner per contract id or per grounding tag."""
    base = base or template_resolver()

    def resolve(node: Contract) -> Optional[str]:
        if node.id in overrides:
            return overrides[node.id]
        for tag in node.grounding_tags:
            if tag in overrides:
                return overrides[tag]
        return base(node)

    return resolve


class LLMOwnerResolver:
    """LLM 추론: infer the owning role from the control's label + an org description.

    Gated: the model must return one of the known roles, else we fall back to the
    template role. Offline-safe (lazy import, injectable client).
    """

    def __init__(self, roles: list[str], org_description: str = "", client=None, model: str = DEFAULT_MODEL):
        self.roles = roles
        self.org_description = org_description
        self.model = model
        self._client = client
        self._base = template_resolver()

    def _client_or_default(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def __call__(self, node: Contract) -> Optional[str]:
        import json

        client = self._client_or_default()
        response = client.messages.create(
            model=self.model,
            max_tokens=512,
            system="You assign one owning role to an operational control. Choose only from the given roles.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"역할 후보: {self.roles}\n"
                        f"조직 설명: {self.org_description or '(없음)'}\n"
                        f"통제: {node.label}\n"
                        "이 통제를 소유할 역할 하나만 고르라."
                    ),
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"role": {"type": "string", "enum": self.roles}},
                        "required": ["role"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        text = next((b.text for b in response.content if b.type == "text"), "{}")
        role = json.loads(text).get("role")
        return role if role in self.roles else self._base(node)  # gate


@dataclass
class OrgRole:
    canonical: str
    owner: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class BootstrapResult:
    resolver: Resolver
    exceptions: list[tuple[str, str, str]]  # (contract_id, label, unmatched role) needing confirmation


def parse_org(data: dict) -> list[OrgRole]:
    """Accept either the rich form {roles:[{role,owner,aliases}]} or flat {role: owner}."""
    if "roles" in data:
        return [OrgRole(r["role"], r["owner"], r.get("aliases", [])) for r in data["roles"]]
    return [OrgRole(role, owner, []) for role, owner in data.items() if not role.startswith("_")]


def _lookup(role_seed: str, org: list[OrgRole]) -> Optional[str]:
    for r in org:
        if role_seed == r.canonical or role_seed in r.aliases:
            return r.owner
    return None


def bootstrap(graph: ContractGraph, data: dict) -> BootstrapResult:
    """Door-B setup with minimal friction: auto-infer owners from the org chart, and
    surface only the controls whose role didn't match — the human confirms just those."""
    org = parse_org(data)
    exceptions: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for node in graph.iter_nodes():
        if not node.owner_role:
            continue
        if _lookup(node.owner_role, org) is None and node.owner_role not in seen:
            seen.add(node.owner_role)
            exceptions.append((node.id, node.label, node.owner_role))

    def resolver(node: Contract) -> Optional[str]:
        return _lookup(node.owner_role, org) or (node.owner_role or None)

    return BootstrapResult(resolver=resolver, exceptions=exceptions)


def assign_owners(graph: ContractGraph, resolver: Resolver) -> ContractGraph:
    """Set node.owner from the resolver, without clobbering an already-owned judgment."""
    for node in graph.iter_nodes():
        if node.owner:  # e.g. a judgment owner already set by grounding
            continue
        node.owner = resolver(node)
    return graph


def by_owner(items: list) -> dict[str, list]:
    """Group anything with an `.owner` attribute into per-owner buckets."""
    buckets: dict[str, list] = {}
    for it in items:
        key = getattr(it, "owner", None) or "미지정"
        buckets.setdefault(key, []).append(it)
    return buckets
