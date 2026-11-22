import json
from pathlib import Path

import pytest

from tools.epav import stack_catalog
from tools.epav.package_resolver import _PM_REGISTRY
from tools.epav.project_rules import _infer_stack

_CATALOG = json.loads((Path(stack_catalog.__file__).parent / "stack_catalog.json").read_text())["technologies"]


def test_catalog_schema():
    assert len(_CATALOG) >= 150
    for tech in _CATALOG:
        assert tech["name"] and tech["category"]
        assert tech.get("aliases") or tech.get("exact_case"), tech["name"]
        assert set(tech) <= {"name", "category", "aliases", "exact_case", "package_manager"}, tech["name"]


def test_catalog_names_unique():
    names = [t["name"] for t in _CATALOG]
    assert len(names) == len(set(names))


def test_catalog_aliases_unique():
    seen: dict[str, str] = {}
    for tech in _CATALOG:
        for alias in tech.get("aliases", []):
            key = alias.lower()
            assert key not in seen, f"alias {alias!r} used by {seen.get(key)} and {tech['name']}"
            seen[key] = tech["name"]


def test_catalog_package_managers_exist_in_resolver():
    for tech in _CATALOG:
        pm = tech.get("package_manager")
        if pm and pm not in ("terraform", "helm", "ansible"):
            assert pm in _PM_REGISTRY, f"{tech['name']} -> {pm}"


@pytest.mark.parametrize("text,expected", [
    ("Frontend: Next.js 16 with Tailwind CSS", {"Next.js", "Tailwind CSS"}),
    ("Backend is Django 5 on Python 3.12 with PostgreSQL", {"Django", "Python", "PostgreSQL"}),
    ("Spring Boot 3 service, Java 21, Kafka for events", {"Spring Boot", "Java", "Kafka"}),
    ("ASP.NET Core 8 API with Entity Framework and SQL Server", {"ASP.NET Core", "Entity Framework", "Microsoft SQL Server"}),
    ("Laravel 11 (PHP 8.3) with MySQL and Redis", {"Laravel", "PHP", "MySQL", "Redis"}),
    ("Ruby on Rails 7 monolith with Sidekiq", {"Ruby on Rails", "Ruby", "Sidekiq"}),
    ("Phoenix LiveView app written in Elixir", {"Phoenix", "Elixir"}),
    ("Mobile: Flutter 3 with Firebase", {"Flutter", "Firebase"}),
    ("iOS app in SwiftUI, Android in Jetpack Compose", {"Swift / iOS native", "Kotlin / Android native"}),
    ("Written in Go using Gin framework, deployed to GKE", {"Go", "Gin", "GCP"}),
    ("Axum service in Rust", {"Axum", "Rust"}),
    ("Desktop app with Tauri", {"Tauri"}),
    ("Infra: Terraform modules on AWS, Helm charts on Kubernetes", {"Terraform / OpenTofu", "AWS", "Helm", "Kubernetes"}),
    ("C++20 engine using Qt 6", {"C++", "Qt"}),
    ("tRPC API via create-t3-app with Prisma", {"tRPC / T3", "Prisma"}),
])
def test_detect_by_category(text, expected):
    assert expected <= set(stack_catalog.detect(text))


def test_whole_word_no_false_positives():
    # old _infer_stack matched "t3" inside any word; "go" must not match inside "mongo"/"google"
    found = set(stack_catalog.detect("We store ht3x blobs in mongo and use google docs. Let's go."))
    assert "tRPC / T3" not in found
    assert "Go" not in found
    assert "MongoDB" in found


def test_exact_case_aliases():
    assert "Ruby on Rails" in stack_catalog.detect("A Rails app")
    assert "Ruby on Rails" not in stack_catalog.detect("guard rails on the stairs")
    assert "Swift" in stack_catalog.detect("Written in Swift")
    assert "Swift" not in stack_catalog.detect("a swift response")


def test_mentioned_only_still_matches():
    # documented limit of keyword matching: it can't tell "use" from "rejected"
    assert "MongoDB" in stack_catalog.detect("We considered MongoDB but rejected it.")


def test_package_manager_for_first_mention():
    assert stack_catalog.package_manager_for("Laravel 11 with Vue.js") == "composer"
    assert stack_catalog.package_manager_for("PostgreSQL then Django") == "pip"
    assert stack_catalog.package_manager_for("PostgreSQL only") == ""


def test_infer_stack_keeps_output_format():
    assert _infer_stack("Next.js and Supabase") == "Next.js, Supabase"
    assert _infer_stack("nothing relevant here") == "(update with your stack)"
