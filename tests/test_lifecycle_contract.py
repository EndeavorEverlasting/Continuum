from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / ".continuum" / "lifecycle.json"
ADR = ROOT / "docs" / "adr" / "0001-continuum-dormant.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"


class DormantLifecycleContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(LIFECYCLE.read_text(encoding="utf-8"))

    def test_continuum_is_dormant(self) -> None:
        self.assertEqual(self.payload["status"], "dormant")
        self.assertEqual(self.payload["repository_role"], "preserved-reference")
        self.assertFalse(self.payload["feature_development_allowed"])
        self.assertFalse(self.payload["runtime_expansion_allowed"])

    def test_agentswitchboard_is_active_control_plane(self) -> None:
        self.assertEqual(
            self.payload["active_control_plane"],
            {
                "repository": "EndeavorEverlasting/AgentSwitchboard",
                "role": "active-control-plane",
            },
        )

    def test_reactivation_is_not_an_automatic_gate(self) -> None:
        self.assertFalse(self.payload["reactivation_allowed"])
        self.assertEqual(
            self.payload["reactivation_policy"],
            "new-explicit-architecture-decision-only",
        )

    def test_dormant_policy_is_visible_at_entrypoints(self) -> None:
        adr = ADR.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        agents = AGENTS.read_text(encoding="utf-8")
        for text in (adr, readme, agents):
            self.assertIn("AgentSwitchboard", text)
            self.assertIn("dormant", text.lower())
        self.assertIn("no automatic reactivation gate", adr.lower())


if __name__ == "__main__":
    unittest.main()
