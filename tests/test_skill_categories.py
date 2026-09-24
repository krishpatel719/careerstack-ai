"""Tests for skills_vocab.json's technical/professional categorisation and
miner.py's skill_category() lookup -- see ats.py's by_category breakdown,
which depends on every canonical skill having exactly one category.
"""

import asyncio

import pytest

import app.services.roleprofile.miner as miner_module
from app.services.roleprofile.miner import (
    POSTING_TITLE_FILTER_VERSION,
    RoleProfileDataUnavailableError,
    SKILL_CATEGORIES,
    is_usable_role_profile,
    mine_role_profile,
    posting_matches_role,
    skill_category,
)

EXPECTED_PROFESSIONAL = {
    "adaptability",
    "agile",
    "analytical skills",
    "attention to detail",
    "communication skills",
    "conflict resolution",
    "critical thinking",
    "cross-functional collaboration",
    "decision making",
    "kanban",
    "leadership",
    "mentoring",
    "problem solving",
    "project management",
    "scrum",
    "stakeholder management",
    "team collaboration",
    "time management",
}


def test_every_vocab_skill_has_exactly_one_of_the_two_categories():
    assert set(SKILL_CATEGORIES.values()) == {"technical", "professional"}


def test_professional_skills_match_the_expected_set():
    professional = {skill for skill, category in SKILL_CATEGORIES.items() if category == "professional"}
    assert professional == EXPECTED_PROFESSIONAL


def test_tools_and_methodologies_are_classified_as_the_user_specified():
    """Explicit judgement calls from the spec: agile/scrum are
    methodologies, not technologies, so they're professional; git and jira
    are tools, so they're technical.
    """
    assert skill_category("agile") == "professional"
    assert skill_category("scrum") == "professional"
    assert skill_category("git") == "technical"
    assert skill_category("jira") == "technical"


def test_unknown_skill_defaults_to_technical():
    assert skill_category("some-made-up-skill-xyz") == "technical"


def test_frontend_posting_filter_rejects_backend_titles():
    assert posting_matches_role({"title": "Senior Frontend Engineer"}, "Frontend Developers")
    assert posting_matches_role({"title": "Front End Developer"}, "frontend developer")
    assert not posting_matches_role({"title": "Java Backend Engineer"}, "Frontend Developer")
    assert not posting_matches_role({"title": "Full Stack Developer"}, "frontend developer")


@pytest.mark.parametrize(
    "role, matching_titles, unrelated_titles",
    [
        (
            "Backend Developer",
            ["Java Backend Engineer", "Server Side Developer", "Full Stack Developer"],
            ["Frontend Engineer", "Android Developer"],
        ),
        (
            "MERN Developer",
            ["MERN Stack Engineer", "Full Stack Developer"],
            ["Java Backend Engineer", "UI Designer"],
        ),
        (
            "Android Developer",
            ["Senior Android Engineer", "Mobile App Developer", "Flutter Developer"],
            ["Java Backend Engineer", "Frontend Engineer"],
        ),
        (
            "Machine Learning Engineer",
            ["Machine Learning Engineer", "Data Scientist", "AI/ML Engineer"],
            ["Frontend Developer", "Product Manager"],
        ),
        (
            "DevOps Engineer",
            ["DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer"],
            ["Frontend Developer", "Data Analyst"],
        ),
        (
            "QA Engineer",
            ["QA Automation Engineer", "Software Test Engineer", "SDET"],
            ["Frontend Developer", "Java Backend Engineer"],
        ),
        (
            "UI/UX Designer",
            ["Product Designer", "UX Researcher", "Web Designer"],
            ["Frontend Developer", "Product Manager"],
        ),
        (
            "Product Manager",
            ["Senior Product Manager", "Product Owner"],
            ["Frontend Developer", "Product Designer"],
        ),
        (
            "Cybersecurity Engineer",
            ["Application Security Engineer", "SOC Analyst", "AppSec Engineer"],
            ["Frontend Developer", "Data Scientist"],
        ),
    ],
)
def test_recognised_role_families_filter_unrelated_postings(
    role, matching_titles, unrelated_titles
):
    for title in matching_titles:
        assert posting_matches_role({"title": title}, role), (role, title)
    for title in unrelated_titles:
        assert not posting_matches_role({"title": title}, role), (role, title)


def test_generic_software_role_keeps_existing_provider_matching_behaviour():
    """A generic role has no safe specialty classification, so the title
    filter stays out of the way instead of guessing frontend/backend/full stack.
    """
    assert posting_matches_role(
        {"title": "Software Engineer"}, "software engineer"
    )


@pytest.mark.parametrize("role", ["Frontend Developer", "Backend Developer", "QA Engineer"])
def test_role_profiles_mined_before_current_title_filtering_are_unusable(role):
    profile = {
        "role": role,
        "location": "India",
        "postings_sampled": 40,
        "skill_frequencies": {"react": {"frequency": 0.5, "count": 20}},
    }

    assert not is_usable_role_profile(profile)
    profile["posting_title_filter_version"] = POSTING_TITLE_FILTER_VERSION
    assert is_usable_role_profile(profile)


def test_frontend_mining_ignores_unrelated_backend_postings(monkeypatch):
    async def _mixed_results(*args, **kwargs):
        return [
            {
                "id": f"frontend-{index}",
                "title": f"Frontend Engineer {index}",
                "description": "Build responsive interfaces with HTML, CSS, and React.",
            }
            for index in range(3)
        ] + [
            {
                "id": f"backend-{index}",
                "title": f"Java Backend Engineer {index}",
                "description": "Build services with Java, Spring Boot, and AWS.",
            }
            for index in range(3)
        ]

    monkeypatch.setattr(miner_module, "search", _mixed_results)

    profile = asyncio.run(mine_role_profile("frontend developer", "India"))

    assert profile["postings_sampled"] == 3
    assert "java" not in profile["skill_frequencies"]
    assert "spring boot" not in profile["skill_frequencies"]
    assert "react" in profile["skill_frequencies"]
    assert profile["posting_title_filter_version"] == POSTING_TITLE_FILTER_VERSION


def test_no_results_is_not_a_mineable_profile(monkeypatch):
    async def _no_results(*args, **kwargs):
        return []

    monkeypatch.setattr(miner_module, "search", _no_results)

    with pytest.raises(RoleProfileDataUnavailableError, match="No job postings"):
        asyncio.run(mine_role_profile("data archaeologist", "India"))


def test_postings_without_recognised_skills_are_not_a_mineable_profile(monkeypatch):
    async def _unusable_postings(*args, **kwargs):
        return [
            {
                "id": f"posting-{index}",
                "title": "Unusual role",
                "description": "A description with no vocabulary matches.",
            }
            for index in range(3)
        ]

    monkeypatch.setattr(miner_module, "search", _unusable_postings)

    with pytest.raises(RoleProfileDataUnavailableError, match="No usable skill frequencies"):
        asyncio.run(mine_role_profile("data archaeologist", "India"))
