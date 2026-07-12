from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from continuum.harness_interop import (  # noqa: E402
    HarnessInteropError,
    load_harness_contribution_manifest,
    parse_harness_contribution_manifest,
)

MANIFEST_PATH = ROOT / ".continuum" / "harness-contributions.json"


class HarnessInteropTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_loads_pinned_blacksmith_guild_contributions(self) -> None:
        manifest = load_harness_contribution_manifest(MANIFEST_PATH)
        self.assertEqual("EndeavorEverlasting/BlacksmithGuild", manifest.source_repository)
        self.assertEqual("79b3fffa9b1d7f85c3247d3be23f081b0efc6cec", manifest.source_commit_sha)
        self.assertEqual(
            ("harness-skill-maturity", "repo-floor-hygiene", "agent-skill-factoring"),
            tuple(item.contribution_id for item in manifest.portable_contributions),
        )

    def test_rejects_mutable_or_short_source_reference(self) -> None:
        self.document["source"]["commit_sha"] = "main"
        with self.assertRaises(HarnessInteropError) as raised:
            parse_harness_contribution_manifest(self.document)
        self.assertEqual("interop.commit_invalid", raised.exception.code)

    def test_rejects_experimental_contribution_targeting_continuum(self) -> None:
        self.document["contributions"][0]["maturity"] = "experimental"
        with self.assertRaises(HarnessInteropError) as raised:
            parse_harness_contribution_manifest(self.document)
        self.assertEqual("interop.maturity_gate", raised.exception.code)

    def test_rejects_domain_behavior_targeting_harness(self) -> None:
        self.document["contributions"][0]["classification"] = "domain_specific"
        with self.assertRaises(HarnessInteropError) as raised:
            parse_harness_contribution_manifest(self.document)
        self.assertEqual("interop.harness_boundary", raised.exception.code)

    def test_rejects_repository_path_escape(self) -> None:
        self.document["contributions"][0]["source_paths"] = ["../outside.json"]
        with self.assertRaises(HarnessInteropError) as raised:
            parse_harness_contribution_manifest(self.document)
        self.assertEqual("interop.path_invalid", raised.exception.code)

    def test_rejects_duplicate_contribution_ids(self) -> None:
        duplicate = copy.deepcopy(self.document["contributions"][0])
        self.document["contributions"].append(duplicate)
        with self.assertRaises(HarnessInteropError) as raised:
            parse_harness_contribution_manifest(self.document)
        self.assertEqual("interop.contribution_duplicate", raised.exception.code)

    def test_schema_document_uses_draft_2020_12_and_closed_objects(self) -> None:
        schema = json.loads((ROOT / "schemas" / "harness-contribution.schema.json").read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["contribution"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
