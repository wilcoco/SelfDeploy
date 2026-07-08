"""SelfDeploy — an ought-first measurement-grounding engine.

A low-cost stand-in for the Palantir FDE effect, aimed at SMBs. The core move:
take an executive's requirement as the *ought*, decompose it into the substructure
it logically entails, then ground each entailed record against the company's real
evidence. What can't ground is a *red cell* — the hidden layer, surfaced.

Public surface:
    build_graph   requirement -> ought-graph (decompose)
    ground        ought-graph + evidence -> graded graph (deterministic gate)
    Evidence, Signal
    text_report, html_report
    VERTICALS     the Kind-B measurement grammars
"""
from .collectors import (
    DEFAULT_CATALOG,
    Collector,
    GapPlan,
    collect_all,
    data_source_collector,
    manual_gate_collector,
    plan_sensing,
    predictive_maintenance_collector,
)
from .decompose import build_graph, build_obligation_graph
from .evolve import CONTINUOUS, PROMOTE, REDESIGN, Verdict, classify_requirement, classify_signal
from .grounding import Evidence, Metrics, Signal, ground, metrics
from .interview import Answer, Question, apply_answers, generate_questions, run_round
from .ir import CATASTROPHIC, MINOR, MODERATE, SEVERE, Contract, ContractGraph, Grade, NodeKind, Provenance
from .llm import ClaudeRequirementMapper
from .owners import (
    LLMOrgInferer,
    LLMOwnerResolver,
    assign_owners,
    bootstrap,
    by_owner,
    manual_resolver,
    org_chart_resolver,
    template_resolver,
)
from .report import html_report, risk_register_html, text_report
from .categories import RISK_CATEGORIES, RiskCategory, coverage
from .clearance import ACTION_TYPES, ActionType, Clearance, clear_action
from .manage import ManagedItem, cascade, management_surface, select, status_summary
from .sensitivity import Flag, LLMSensitivityChecker, check_campaign
from .risk import (
    RiskItem,
    by_exposure,
    by_regulation,
    effective_exposure,
    effective_regulations,
    effective_severity,
    escalate,
    risk_register,
)
from .templates import VERTICALS, VerticalTemplate

__all__ = [
    "build_graph",
    "ground",
    "Evidence",
    "Signal",
    "Metrics",
    "metrics",
    "Contract",
    "ContractGraph",
    "Grade",
    "NodeKind",
    "Provenance",
    "text_report",
    "html_report",
    "VERTICALS",
    "VerticalTemplate",
    "Answer",
    "Question",
    "generate_questions",
    "apply_answers",
    "run_round",
    "ClaudeRequirementMapper",
    "classify_signal",
    "classify_requirement",
    "Verdict",
    "CONTINUOUS",
    "PROMOTE",
    "REDESIGN",
    "Collector",
    "GapPlan",
    "DEFAULT_CATALOG",
    "collect_all",
    "plan_sensing",
    "predictive_maintenance_collector",
    "data_source_collector",
    "manual_gate_collector",
    "build_obligation_graph",
    "risk_register",
    "effective_severity",
    "escalate",
    "RiskItem",
    "CATASTROPHIC",
    "SEVERE",
    "MODERATE",
    "MINOR",
    "assign_owners",
    "by_owner",
    "template_resolver",
    "org_chart_resolver",
    "manual_resolver",
    "LLMOwnerResolver",
    "bootstrap",
    "effective_regulations",
    "risk_register_html",
    "by_regulation",
    "by_exposure",
    "effective_exposure",
    "LLMOrgInferer",
    "check_campaign",
    "Flag",
    "LLMSensitivityChecker",
    "clear_action",
    "Clearance",
    "ActionType",
    "ACTION_TYPES",
    "RISK_CATEGORIES",
    "RiskCategory",
    "coverage",
    "management_surface",
    "select",
    "cascade",
    "status_summary",
    "ManagedItem",
]

__version__ = "0.0.1"
