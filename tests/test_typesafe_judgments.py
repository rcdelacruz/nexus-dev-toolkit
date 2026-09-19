"""Tests for the TypeSafe-backed judgment calls in tools/epav/.

None of these hit the real TypeSafe API: `judgment.system_one`/
`system_one_async` are monkeypatched per-test, and the "TypeSafe unavailable"
path is exercised by patching them to return None (exactly what happens with
no TYPESAFE_API_KEY set, per `tools.epav.judgment`'s own fail-soft contract).
"""

from tools.epav import arch_ingest, judgment, package_resolver, project_rules


class _FakeChoiceAnswer:
    def __init__(self, choice, confidence):
        self.choice = choice
        self.confidence = confidence


class _FakeNoulAnswer:
    def __init__(self, noul):
        self.noul = noul


class _FakeResponse:
    def __init__(self, choices=None, nouls=None):
        self.choices = choices or {}
        self.nouls = nouls or {}


async def _returns_none(*args, **kwargs):
    return None


# ── arch_ingest ──────────────────────────────────────────────────────────────

def test_split_by_heading_keeps_every_heading_as_its_own_block():
    text = "intro line\n# Tech Stack\nNext.js\n## RBAC Rules\nadmin only\n# Table of Contents\n1. a"
    preamble, blocks = arch_ingest._split_by_heading(text)
    assert preamble == "intro line"
    assert [h for h, _ in blocks] == ["Tech Stack", "RBAC Rules", "Table of Contents"]
    assert "Next.js" in dict(blocks)["Tech Stack"]


async def test_extract_sections_falls_back_to_keywords_when_typesafe_unavailable(monkeypatch):
    monkeypatch.setattr(judgment, "system_one_async", _returns_none)
    text = "# Tech Stack\nNext.js\n# Table of Contents\n1. a"
    sections = await arch_ingest._extract_sections(text)
    assert "tech stack" in sections
    assert "table of contents" not in sections


async def test_extract_sections_uses_typesafe_categories(monkeypatch):
    async def fake_system_one_async(state, questions):
        assert set(questions) == {"h0", "h1"}
        return _FakeResponse(choices={
            "h0": _FakeChoiceAnswer("stack", 0.99),
            "h1": _FakeChoiceAnswer("other", 0.99),
        })

    monkeypatch.setattr(judgment, "system_one_async", fake_system_one_async)
    text = "# Tech Stack\nNext.js\n# Table of Contents\n1. a"
    sections = await arch_ingest._extract_sections(text)
    assert set(sections) == {"tech stack"}


# ── project_rules ────────────────────────────────────────────────────────────

def test_infer_stack_fallback_matches_original_keywords():
    text = "Built with Next.js, Postgres, and Tailwind CSS."
    assert project_rules._infer_stack_fallback(text) == "Next.js, PostgreSQL, Tailwind CSS"


async def test_infer_stack_uses_typesafe_nouls(monkeypatch):
    async def fake_system_one_async(state, questions):
        nouls = {tag: _FakeNoulAnswer(0.9 if tag == "Django" else 0.01) for tag in questions}
        return _FakeResponse(nouls=nouls)

    monkeypatch.setattr(judgment, "system_one_async", fake_system_one_async)
    assert await project_rules._infer_stack("Django backend, nothing else") == "Django"


async def test_infer_stack_falls_back_when_typesafe_unavailable(monkeypatch):
    monkeypatch.setattr(judgment, "system_one_async", _returns_none)
    result = await project_rules._infer_stack("Next.js app with Supabase")
    assert "Next.js" in result and "Supabase" in result


# ── package_resolver ─────────────────────────────────────────────────────────

def test_detect_package_manager_exact_name_short_circuits(monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("should not call TypeSafe when the hint names a pm exactly")

    monkeypatch.setattr(judgment, "system_one", fail_if_called)
    assert package_resolver._detect_package_manager("use yarn please") == "yarn"


def test_detect_package_manager_word_boundary_avoids_substring_collision(monkeypatch):
    monkeypatch.setattr(judgment, "system_one", lambda **kwargs: None)
    # "go" is a substring of "django" and "npm" is a substring of "pnpm" --
    # neither should short-circuit via the exact-name fast path.
    assert package_resolver._detect_package_manager("pnpm workspace") == "pnpm"


def test_detect_package_manager_uses_high_confidence_choice(monkeypatch):
    monkeypatch.setattr(
        judgment, "system_one",
        lambda **kwargs: _FakeResponse(choices={"package_manager": _FakeChoiceAnswer("cargo", 0.95)}),
    )
    assert package_resolver._detect_package_manager("a Rust service") == "cargo"


def test_detect_package_manager_falls_back_on_low_confidence(monkeypatch):
    monkeypatch.setattr(
        judgment, "system_one",
        lambda **kwargs: _FakeResponse(choices={"package_manager": _FakeChoiceAnswer("cargo", 0.5)}),
    )
    assert package_resolver._detect_package_manager("some obscure elixir thing") == "npm"


def test_detect_package_manager_falls_back_when_typesafe_unavailable(monkeypatch):
    monkeypatch.setattr(judgment, "system_one", lambda **kwargs: None)
    assert package_resolver._detect_package_manager("a python service") == "pip"


def test_detect_package_manager_fallback_recognizes_iac_tools():
    assert package_resolver._detect_package_manager_fallback("terraform for aws") == "terraform"
    assert package_resolver._detect_package_manager_fallback("ansible playbooks") == "ansible"
    assert package_resolver._detect_package_manager_fallback("helm chart") == "helm"


# ── arch_ingest: project shape ──────────────────────────────────────────────

def test_classify_project_shape_falls_back_when_typesafe_unavailable(monkeypatch):
    monkeypatch.setattr(judgment, "system_one_async", _returns_none)
    return_value = arch_ingest._classify_project_shape_fallback(
        "Terraform modules provisioning an AWS VPC and EKS cluster."
    )
    assert return_value == "infrastructure"


async def test_classify_project_uses_typesafe_choice_and_noul(monkeypatch):
    async def fake_system_one_async(state, questions):
        assert "architecture_document" in state
        assert set(questions) == {"shape", "has_infra"}
        return _FakeResponse(
            choices={"shape": _FakeChoiceAnswer("infrastructure", 0.99)},
            nouls={"has_infra": _FakeNoulAnswer(0.95)},
        )

    monkeypatch.setattr(judgment, "system_one_async", fake_system_one_async)
    shape, has_infra = await arch_ingest._classify_project("Terraform modules for an AWS VPC.")
    assert shape == "infrastructure"
    assert has_infra is True


async def test_classify_project_flags_has_infra_alongside_a_non_infra_shape(monkeypatch):
    # A 3-tier app with its own Terraform/OpenTofu modules: project_shape is a
    # single forced choice ("web_app"), but has_infrastructure_component must
    # still surface independently so /scaffold generates the IaC deliverables
    # too, not just the app boilerplate.
    async def fake_system_one_async(state, questions):
        return _FakeResponse(
            choices={"shape": _FakeChoiceAnswer("web_app", 0.9)},
            nouls={"has_infra": _FakeNoulAnswer(0.9)},
        )

    monkeypatch.setattr(judgment, "system_one_async", fake_system_one_async)
    shape, has_infra = await arch_ingest._classify_project("React app; OpenTofu provisions the AWS infra it runs on.")
    assert shape == "web_app"
    assert has_infra is True


def test_classify_project_shape_fallback_defaults_to_web_app():
    # No IaC/pipeline/CLI/mobile keywords -- preserves /scaffold's long-standing
    # default of assuming a UI app when nothing says otherwise.
    assert arch_ingest._classify_project_shape_fallback("A service that does things.") == "web_app"


def test_has_infrastructure_component_fallback_recognizes_opentofu():
    assert arch_ingest._has_infrastructure_component_fallback("Provisioned via OpenTofu modules.")
    assert not arch_ingest._has_infrastructure_component_fallback("A plain Next.js app with no infra of its own.")
