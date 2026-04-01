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
)

# These classes test the behavior of PdfReader
class _FakePage: 
    def __init__(self, text: str) -> None:
        self._text = text  

    def extract_text(self) -> str:
        return self._text 

class _FakeReader:  
    def __init__(self, _: str) -> None:
        self.pages = [_FakePage("Requirement A"), _FakePage("Requirement B")]

       

       
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
        self.assertIn("Requirement A", loaded["doc1"]["text"]) 
 
   


    def test_build_zero_shot_prompt(self) -> None: 

        prompt = build_zero_shot_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("d1.pdf", prompt)
        self.assertIn("Alpha", prompt)   
        self.assertIn('"doc1"', prompt)   

  
       
    def test_build_few_shot_prompt(self) -> None: 

        prompt = build_few_shot_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("Example input", prompt) 
        self.assertIn("Example output JSON", prompt)  



    def test_build_chain_of_thought_prompt(self) -> None: 

        prompt = build_chain_of_thought_prompt("d1.pdf", "Alpha", "d2.pdf", "Beta")
        self.assertIn("Internally reason", prompt)
        self.assertIn("Return only final JSON", prompt) 



    def test_identify_kdes_with_prompts(self) -> None: 

        fake_output = (
            '{"doc1": [{"name": "user id", "requirements": ["Store user id"]}], '
            '"doc2": [{"name": "email", "requirements": ["Store email"]}]}'
        )

        def fake_generator(_: str) -> str:
            return fake_output

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
            self.assertTrue((Path(tmp) / "cis-r1-kdes.yaml").exists())
            self.assertTrue((Path(tmp) / "cis-r2-kdes.yaml").exists())

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

   

     
  

 
if __name__ == "__main__":
    unittest.main()




