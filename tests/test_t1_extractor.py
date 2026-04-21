import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import src.T1_Extractor as extractor

from src.T1_Extractor import (
    build_chain_of_thought_prompt,
    build_few_shot_prompt,
    build_zero_shot_prompt,
    dump_llm_outputs_to_text,
    identify_kdes_with_prompts,
    load_and_validate_documents,
    _extract_cis_titles,
    _extract_cis_title_list,
    _build_per_title_few_shot,
    _parse_single_kde,
)


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    def __init__(self, _: str) -> None:
        self.pages = [
            _FakePage("3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)"),
            _FakePage("3.1.1 Ensure that the kubeconfig file permissions are set to 644 (Manual)"),
        ]


class TestT1Extractor(unittest.TestCase):

    def test_load_and_validate_documents(self) -> None:

        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "a.pdf"
            right = Path(tmp) / "b.pdf"
            left.write_bytes(b"%PDF-1.4")
            right.write_bytes(b"%PDF-1.4")

            with patch("src.T1_Extractor.PdfReader", _FakeReader):
                loaded = load_and_validate_documents(str(left), str(right))

        self.assertIn("doc1", loaded)
        self.assertIn("doc2", loaded)
        self.assertIn("Anonymous Auth", loaded["doc1"]["text"])

    def test_build_zero_shot_prompt(self) -> None:

        prompt = build_zero_shot_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("d1.pdf", prompt)
        self.assertIn("Alpha", prompt)
        self.assertIn('"doc1"', prompt)
        self.assertIn("MUST", prompt)

    def test_build_few_shot_prompt(self) -> None:

        prompt = build_few_shot_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("Example 1", prompt)
        self.assertIn("Anonymous Auth", prompt)
        self.assertIn("kubeconfig file permissions", prompt)

    def test_build_chain_of_thought_prompt(self) -> None:

        prompt = build_chain_of_thought_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("Internally reason", prompt)
        self.assertIn("MUST", prompt)

    def test_identify_kdes_with_prompts(self) -> None:

        def fake_generator(prompt: str) -> str:
            if "Anonymous Auth is Not Enabled" in prompt:
                return (
                    '{"name": "Anonymous Auth", '
                    '"requirements": ["3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)"]}'
                )
            if "kubeconfig file permissions" in prompt:
                return (
                    '{"name": "kubeconfig file permissions", '
                    '"requirements": ["3.1.1 Ensure that the kubeconfig file permissions are set to 644 (Manual)"]}'
                )
            return "no json here"

        with tempfile.TemporaryDirectory() as tmp:

            left = Path(tmp) / "cis-r1.pdf"
            right = Path(tmp) / "cis-r2.pdf"
            left.write_bytes(b"%PDF-1.4")
            right.write_bytes(b"%PDF-1.4")

            with patch("src.T1_Extractor.PdfReader", _FakeReader):
                with patch.object(extractor, "DEFAULT_OUTPUT_DIR", Path(tmp)):
                    result = identify_kdes_with_prompts(
                        str(left),
                        str(right),
                        generator=fake_generator,
                    )

            self.assertIn("element1", result["doc1"])
            self.assertTrue(len(result["doc1"]) >= 1)

            doc1_yaml = Path(tmp) / "cis-r1-kdes.yaml"
            doc2_yaml = Path(tmp) / "cis-r2-kdes.yaml"
            self.assertTrue(doc1_yaml.exists())
            self.assertTrue(doc2_yaml.exists())

            doc1_content = doc1_yaml.read_text(encoding="utf-8").strip()
            doc2_content = doc2_yaml.read_text(encoding="utf-8").strip()
            self.assertNotEqual(doc1_content, "{}")
            self.assertNotEqual(doc2_content, "{}")
            self.assertTrue(len(doc1_content) > 0)
            self.assertTrue(len(doc2_content) > 0)

    def test_dump_llm_outputs_to_text(self) -> None:
        records = [
            {
                "llm_name": "google/gemma-3-1b-it",
                "prompt_used": "Prompt body",
                "prompt_type": "zero-shot",
                "llm_output": "{}",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "llm.txt"
            dump_llm_outputs_to_text(records, str(out))
            content = out.read_text(encoding="utf-8")

        self.assertIn("*LLM Name*", content)
        self.assertIn("*Prompt Used*", content)
        self.assertIn("*Prompt Type*", content)
        self.assertIn("*LLM Output*", content)

    def test_extract_cis_titles(self) -> None:

        sample = (
            "Page 17\n"
            "\n"
            "Some introductory prose that should be ignored.\n"
            "3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)\n"
            "4.1.3 Ensure that the kubelet service file permissions are set (Manual)\n"
            "\n"
            "5.10.2 Minimize the admission of privileged containers (Automated)\n"
            "14\n"
            "More prose without a match.\n"
        )

        result = _extract_cis_titles(sample)
        lines = result.split("\n")

        self.assertEqual(len(lines), 3)
        self.assertIn("3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)", lines)
        self.assertIn("4.1.3 Ensure that the kubelet service file permissions are set (Manual)", lines)
        self.assertIn("5.10.2 Minimize the admission of privileged containers (Automated)", lines)
        self.assertNotIn("Page 17", result)
        self.assertNotIn("introductory prose", result)

    def test_build_per_title_few_shot(self) -> None:
        prompt = _build_per_title_few_shot(
            "cis-r1.pdf",
            "3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)",
        )
        self.assertIn("cis-r1.pdf", prompt)
        self.assertIn("Anonymous Auth", prompt)
        self.assertIn("Example 1", prompt)
        self.assertIn("3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)", prompt)

    def test_parse_single_kde_happy(self) -> None:
        result = _parse_single_kde('{"name": "foo", "requirements": ["bar"]}')
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["name"], "foo")
        self.assertEqual(result["requirements"], ["bar"])

    def test_parse_single_kde_extra_data(self) -> None:
        result = _parse_single_kde('{"name": "foo", "requirements": ["bar"]} trailing prose')
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["name"], "foo")

    def test_parse_single_kde_no_json(self) -> None:
        result = _parse_single_kde("just prose no braces")
        self.assertIsNone(result)

    def test_extract_cis_title_list(self) -> None:
        sample = (
            "Some noise line\n"
            "3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)\n"
            "random text\n"
            "4.1.3 Ensure kubelet service file permissions are set (Manual)\n"
            "more noise\n"
        )
        result = _extract_cis_title_list(sample)
        self.assertEqual(len(result), 2)
        self.assertIn("3.2.1 Ensure that Anonymous Auth is Not Enabled (Automated)", result)
        self.assertIn("4.1.3 Ensure kubelet service file permissions are set (Manual)", result)


if __name__ == "__main__":
    unittest.main()
