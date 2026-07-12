from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from continuum.domain_lifecycle import (
    DomainLifecycleError,
    evaluate_domain_action,
    parse_domain_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


def snapshot(
    *,
    domain: str = "mux",
    state: str = "detached",
    verification: str = "independently_verified",
    evidence_reference: str | None = "provider:domain-state",
):
    return parse_domain_snapshot(
        {
            "$schema": "schemas/execution-domain-snapshot.schema.json",
            "schema_version": 1,
            "kind": "continuum.execution-domain-snapshot",
            "domain": domain,
            "state": state,
            "verification": verification,
            "evidence_reference": evidence_reference,
        }
    )


def domain(*capabilities: str, auto_start: bool = False):
    return SimpleNamespace(
        name="mux",
        capabilities=tuple(capabilities),
        auto_start=auto_start,
    )


class DomainLifecycleTests(unittest.TestCase):
    def test_attach_is_allowed_for_verified_detached_domain(self):
        decision = evaluate_domain_action(
            domain("attach", "detach", "spawn"),
            snapshot(),
            "attach",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, "domain_action.attach_allowed")
        self.assertEqual(decision.resulting_state, "attached")
        self.assertFalse(decision.to_dict()["applied"])

    def test_attach_is_idempotent_for_attached_domain(self):
        decision = evaluate_domain_action(
            domain("attach"),
            snapshot(state="attached"),
            "attach",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, "domain_action.already_attached")
        self.assertEqual(decision.resulting_state, "attached")

    def test_caller_reported_state_cannot_authorize_action(self):
        decision = evaluate_domain_action(
            domain("detach"),
            snapshot(
                state="attached",
                verification="caller_reported",
                evidence_reference="operator:terminal-output",
            ),
            "detach",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "domain_action.state_unverified")

    def test_missing_capability_blocks_before_state_transition(self):
        decision = evaluate_domain_action(
            domain("inspect"),
            snapshot(),
            "attach",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "domain_action.capability_missing")

    def test_spawn_requires_attachment_even_when_service_auto_start_is_allowed(self):
        decision = evaluate_domain_action(
            domain("spawn", auto_start=True),
            snapshot(state="detached"),
            "spawn",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "domain_action.attach_required")
        self.assertIn("auto_start", decision.message)

    def test_spawn_is_allowed_for_verified_attached_domain(self):
        decision = evaluate_domain_action(
            domain("spawn"),
            snapshot(state="attached"),
            "spawn",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, "domain_action.spawn_allowed")
        self.assertEqual(decision.resulting_state, "attached")

    def test_unavailable_domain_blocks_action(self):
        decision = evaluate_domain_action(
            domain("attach"),
            snapshot(state="unavailable"),
            "attach",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, "domain_action.unavailable")

    def test_unverified_snapshot_cannot_claim_evidence(self):
        with self.assertRaisesRegex(
            DomainLifecycleError,
            "must not claim an evidence reference",
        ):
            snapshot(
                state="unverified",
                verification="unverified",
                evidence_reference="caller:guess",
            )

    def test_domain_names_must_match(self):
        with self.assertRaisesRegex(DomainLifecycleError, "does not match"):
            evaluate_domain_action(
                domain("attach"),
                snapshot(domain="other"),
                "attach",
            )

    def test_snapshot_rejects_unknown_fields(self):
        document = snapshot().to_dict()
        document["surprise"] = True

        with self.assertRaisesRegex(DomainLifecycleError, "unsupported fields"):
            parse_domain_snapshot(document)


class WezTermContributionManifestTests(unittest.TestCase):
    def test_manifest_uses_existing_interop_contract_and_pins_authority(self):
        from continuum.harness_interop import load_harness_contribution_manifest

        path = ROOT / ".continuum" / "wezterm-contributions.json"
        manifest = load_harness_contribution_manifest(path)

        self.assertEqual(manifest.source_repository, "wezterm/wezterm")
        self.assertEqual(
            manifest.source_commit_sha,
            "fff02ca501c3b457f99b467a86061d2b150c51f2",
        )
        self.assertEqual(
            {item.contribution_id for item in manifest.portable_contributions},
            {
                "domain-capability-state-separation",
                "explicit-domain-action-decisions",
                "startup-selection-separation",
            },
        )
        reference = next(
            item
            for item in manifest.contributions
            if item.contribution_id == "remote-local-identity-reconciliation"
        )
        self.assertEqual(reference.target_layer, "reference_only")

    def test_new_schema_documents_use_draft_2020_12(self):
        for name in (
            "execution-domain-snapshot.schema.json",
            "execution-domain-decision.schema.json",
        ):
            document = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(
                document["$schema"],
                "https://json-schema.org/draft/2020-12/schema",
            )


if __name__ == "__main__":
    unittest.main()
