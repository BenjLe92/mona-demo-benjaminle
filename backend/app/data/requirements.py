"""Extract hard requirements that a grant's text states clearly.

Deliberately conservative: a sentence only yields a requirement when it uses ownership or
entity wording, and never when it reads as a preference ("encouraged", "priority", "including").
Anything not recognised here is left for the applicant to read in the full criteria text.
"""

from __future__ import annotations

import re

from app.domain.models import FounderGroup, Requirement

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")

# Wording that marks a preference or an example, not a requirement.
_SOFT = re.compile(
    r"encourag|priorit|prefer|especially|particularly|focus|emphasis|not required|regardless|"
    r"open to all|includ|such as|e\.g\.|bonus|additional|optional|rising to|underrepresented|underserved|"
    r"support(s|ing)?\b|mission|dedicated|aims?\b|celebrat|empower",
    re.IGNORECASE,
)
# In the description column, a sentence must also read as a rule.
_RULE_CUE = re.compile(r"\bmust\b|eligib|required|\bonly\b|at least|51%|majority", re.IGNORECASE)

_OWNERSHIP = re.compile(r"\b(owned|led|founded)\b", re.IGNORECASE)
_GROUP_PATTERNS: dict[FounderGroup, re.Pattern[str]] = {
    "woman": re.compile(r"\bwom[ae]n\b|\bfemale\b", re.IGNORECASE),
    "black": re.compile(r"\bblack\b|african[- ]american", re.IGNORECASE),
    "bipoc": re.compile(
        r"\bbipoc\b|minorit|people of colou?r|latin[oaxe]\b|hispanic|indigenous|native american|"
        r"\baapi\b|asian[- ]american",
        re.IGNORECASE,
    ),
    "veteran": re.compile(r"\bveteran", re.IGNORECASE),
}
_OWNERSHIP_WINDOW = 45  # characters either side of "owned" searched for a group word

_NONPROFIT_ONLY = re.compile(
    r"must (be|have) (a |an )?(registered |tax-exempt |current )?(501\(c\)|non-?profit)|"
    r"(only|exclusively) (to |for )?(501\(c\)|non-?profit)|"
    r"(501\(c\)\(3\)|non-?profit) (organizations?|status)( is| are)? (only|required)",
    re.IGNORECASE,
)
_NONPROFIT_BLOCKERS = re.compile(r"for-profit|fiscal|small business|individual|artist|\bor\b", re.IGNORECASE)

_FOR_PROFIT_ONLY = re.compile(
    r"must be (a |an )?(\w+ )?for-profit|for-profit (business|compan|entit|small business|venture)",
    re.IGNORECASE,
)
_NONPROFIT_EXCLUDED = re.compile(r"non-?profits? (organizations? )?(are |is )?(not eligible|ineligible)", re.IGNORECASE)
_FOR_PROFIT_EXCLUDED = re.compile(
    r"not open to for-profit|"
    r"for-profit (businesses|companies|entities|organizations) (are |is )?(not eligible|ineligible|excluded|outside)",
    re.IGNORECASE,
)
_ANY_NONPROFIT = re.compile(r"non-?profit|501\(c\)", re.IGNORECASE)

_BRICK = re.compile(
    r"must (have|operate|own|lease|occupy) (a |an )?(physical|brick[- ]and[- ]mortar|storefront|commercial) "
    r"|brick[- ]and[- ]mortar (business|location|storefront|retail|establishment)|"
    r"home-based businesses (are )?(not eligible|ineligible)",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s.strip(" -•\t") for s in _SENTENCE_SPLIT.split(text) if s.strip(" -•\t")]


def _founder_groups(sentence: str) -> list[FounderGroup]:
    groups: list[FounderGroup] = []
    for match in _OWNERSHIP.finditer(sentence):
        window = sentence[max(0, match.start() - _OWNERSHIP_WINDOW) : match.end() + _OWNERSHIP_WINDOW]
        for group, pattern in _GROUP_PATTERNS.items():
            if group not in groups and pattern.search(window):
                groups.append(group)
    return groups


def _scan(sentence: str) -> Requirement | None:
    source = sentence[:300]
    groups = _founder_groups(sentence)
    if groups:
        return Requirement(kind="founder", groups=groups, source=source)
    if _FOR_PROFIT_EXCLUDED.search(sentence):
        return Requirement(kind="nonprofit", source=source)
    if _NONPROFIT_EXCLUDED.search(sentence):
        return Requirement(kind="for_profit", source=source)
    # "For-profit businesses and qualifying nonprofits" admits both, so it is not a restriction.
    if _FOR_PROFIT_ONLY.search(sentence) and not _ANY_NONPROFIT.search(sentence):
        return Requirement(kind="for_profit", source=source)
    if _NONPROFIT_ONLY.search(sentence) and not _NONPROFIT_BLOCKERS.search(sentence):
        return Requirement(kind="nonprofit", source=source)
    if _BRICK.search(sentence):
        return Requirement(kind="brick_and_mortar", source=source)
    return None


def extract_requirements(eligibility_text: str, description: str = "") -> list[Requirement]:
    """Return at most one requirement per kind, preferring the eligibility column."""
    found: dict[str, Requirement] = {}
    candidates = [(s, False) for s in _sentences(eligibility_text)]
    candidates += [(s, True) for s in _sentences(description)]
    for sentence, needs_cue in candidates:
        if _SOFT.search(sentence) or (needs_cue and not _RULE_CUE.search(sentence)):
            continue
        requirement = _scan(sentence)
        # The criteria column outranks the description: if it admits nonprofits, a
        # "for-profit" phrase in the description is not a restriction.
        if needs_cue and requirement and requirement.kind == "for_profit" and _ANY_NONPROFIT.search(eligibility_text):
            continue
        if requirement and requirement.kind not in found:
            found[requirement.kind] = requirement
    return list(found.values())
