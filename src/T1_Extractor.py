# Author: Will Jones 
# date: 3.31.26

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Callable
import yaml
from pypdf import PdfReader



# setting defaults for ease of use.
DEFAULT_MODEL_NAME = "google/gemma-3-1b-it"   
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "Output_files" / "T1_Extractor_Output"  



 
# Opening and validating 2 documents, then returning their content as string.   
def load_and_validate_documents(doc1_path: str, doc2_path: str) -> dict[str, dict[str, str]]:   
    

    p1 = check_pdf(doc1_path)
    p2 = check_pdf(doc2_path)
        
    return {  
        "doc1": {"path": str(p1), "name": p1.name, "text": read_pdf_text(p1)},  
        "doc2": {"path": str(p2), "name": p2.name, "text": read_pdf_text(p2)},  
    }      

    

   
 

 
# Building the zero shot prompt.
def build_zero_shot_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""     
You are a requirements analyst at the best company in the world. You have trained hours on hours for this very moment. Identify key data elements (KDE's) from the two documents.
A KDE may map to multiple requirements.   

Return ONLY valid JSON with this exact shape:     
{{  
  "doc1": [{{"name": "...", "requirements": ["req1", "req2"]}}],
  "doc2": [{{"name": "...", "requirements": ["req1", "req2"]}}]
}} 

Document 1 Name: {doc1_name} 
Document 1 Content: 
{doc1_text}

Document 2 Name: {doc2_name}
Document 2 Content:
{doc2_text}
""".strip() 


  

   

# Building the few shot prompt.
def build_few_shot_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""   
You are a requirements analyst at the best company in the world. You have trained hours on hours for this very moment. Identify key data elements (KDE's) from the two documents.
A KDE may map to multiple requirements.   
  
Example input:
Document A: User profile shall store full name and email. Password must be at least 12 chars.
Document B: Account must include username, email, and MFA preference.   
    
Example output JSON:
{{   
  "doc1": [    
    {{"name": "full name", "requirements": ["User profile shall store full name"]}},
    {{"name": "email", "requirements": ["User profile shall store email"]}},  
    {{"name": "password", "requirements": ["Password must be at least 12 chars"]}}
  ],
  "doc2": [
    {{"name": "username", "requirements": ["Account must include username"]}},
    {{"name": "email", "requirements": ["Account must include email"]}},
    {{"name": "MFA preference", "requirements": ["Account must include MFA preference"]}}
  ]
}}    

Now do the same for these two docs.  Return only JSON.
  
Document 1 Name: {doc1_name}
Document 1 Content:  
{doc1_text}

Document 2 Name: {doc2_name} 
Document 2 Content: 
{doc2_text} 
""".strip()  
  
   






# Building the chain of thought prompt.
def build_chain_of_thought_prompt(doc1_name: str, doc1_text: str, doc2_name: str, doc2_text: str) -> str:
    return f"""   
You are a requirements analyst at the best company in the world. You have trained hours on hours for this very moment.
Internally reason through KDE extraction and mapping, but do not show your reasoning.
Return only final JSON.   

Required JSON:
{{   
  "doc1": [{{"name": "...", "requirements": ["req1", "req2"]}}],
  "doc2": [{{"name": "...", "requirements": ["req1", "req2"]}}]
}}
  
Document 1 Name: {doc1_name}  
Document 1 Content:
{doc1_text}
 
Document 2 Name: {doc2_name}
Document 2 Content:
{doc2_text} 
""".strip()  
 




# Main function to identify KDE's using the prompts,
# merging results and outputting to YAML and text files.
def identify_kdes_with_prompts(
        
    
    doc1_path: str,  
    doc2_path: str,
    model_name: str = DEFAULT_MODEL_NAME,
    generator: Callable[[str], str] | None = None,
    max_new_tokens: int = 1024,
) -> dict[str, dict[str, dict[str, Any]]]:
    
    docs = load_and_validate_documents(doc1_path, doc2_path)
    out_dir = DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_prompt_markdown_to_output(out_dir)



    
    builders = [
        ("zero-shot", build_zero_shot_prompt),
        ("few-shot", build_few_shot_prompt),
        ("chain-of-thought", build_chain_of_thought_prompt),
    ]




    llm = generator if generator is not None else make_llm(model_name, max_new_tokens)


 
    merged: dict[str, dict[str, set[str]]] = {"doc1": {}, "doc2": {}}
    all_runs: list[dict[str, str]] = []


    for prompt_type, make_prompt in builders:

        prompt = make_prompt(
            docs["doc1"]["name"], docs["doc1"]["text"], docs["doc2"]["name"], docs["doc2"]["text"]
        )

        raw = llm(prompt)
        parsed = safe_parse_output(raw)


        for which_doc in ["doc1", "doc2"]:
            for item in parsed.get(which_doc, []):
                name = str(item.get("name", "")).strip().lower()
                if not name:
                    continue


                if name not in merged[which_doc]:
                    merged[which_doc][name] = set()


                reqs = item.get("requirements", [])
                if not isinstance(reqs, list):
                    reqs = [str(reqs)]



                for req in reqs:
                    req_clean = str(req).strip()
                    if req_clean:
                        merged[which_doc][name].add(req_clean)

        all_runs.append(
            {
                "llm_name": model_name,
                "prompt_used": prompt,
                "prompt_type": prompt_type,
                "llm_output": raw,
            }
        )   



    final_data = {  
        "doc1": to_element_dict(merged["doc1"]),
        "doc2": to_element_dict(merged["doc2"]),
    }


    d1_stem = Path(docs["doc1"]["name"]).stem
    d2_stem = Path(docs["doc2"]["name"]).stem
    doc1_yaml, doc2_yaml = yaml_names(d1_stem, d2_stem, out_dir)
 


    with doc1_yaml.open("w", encoding="utf-8") as f1:
        yaml.safe_dump(final_data["doc1"], f1, sort_keys=False, allow_unicode=False)

    with doc2_yaml.open("w", encoding="utf-8") as f2:
        yaml.safe_dump(final_data["doc2"], f2, sort_keys=False, allow_unicode=False)

    txt_name = f"{d1_stem}-{d2_stem}-llm-output.txt"
    dump_llm_outputs_to_text(all_runs, str(out_dir / txt_name))

    return final_data










def dump_llm_outputs_to_text(records: list[dict[str, str]], output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    text_blocks: list[str] = []
    for rec in records:
        block = (
            "*LLM Name*\n"
            f"{rec.get('llm_name', '')}\n"
            "*Prompt Used*\n"
            f"{rec.get('prompt_used', '')}\n"
            "*Prompt Type*\n"
            f"{rec.get('prompt_type', '')}\n"
            "*LLM Output*\n"
            f"{rec.get('llm_output', '')}\n"
        )
        text_blocks.append(block)

    out.write_text("\n".join(text_blocks), encoding="utf-8")
    return str(out)








def run_all_input_combinations(
        
    input_dir: str,
    model_name: str = DEFAULT_MODEL_NAME,
    generator: Callable[[str], str] | None = None,
) -> dict[str, dict[str, dict[str, dict[str, Any]]]]:
    base = Path(input_dir)

    combos = [

        ("cis-r1.pdf", "cis-r1.pdf"),
        ("cis-r1.pdf", "cis-r2.pdf"),
        ("cis-r1.pdf", "cis-r3.pdf"),
        ("cis-r1.pdf", "cis-r4.pdf"),
        ("cis-r2.pdf", "cis-r2.pdf"),
        ("cis-r2.pdf", "cis-r3.pdf"),
        ("cis-r2.pdf", "cis-r4.pdf"),
        ("cis-r3.pdf", "cis-r3.pdf"),
        ("cis-r3.pdf", "cis-r4.pdf"),
    ]

    results: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for left, right in combos:
        key = f"{Path(left).stem}__{Path(right).stem}"
        results[key] = identify_kdes_with_prompts(
            str(base / left),
            str(base / right),
            model_name=model_name,
            generator=generator,
        )

    return results







def check_pdf(path_value: str) -> Path:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError("Document path must be a non-empty string")

    p = Path(path_value).expanduser().resolve()
    if p.suffix.lower() != ".pdf":
        raise ValueError(f"Expected .pdf, got: {p}")
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")

    with p.open("rb"):
        pass
    return p






def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pieces: list[str] = []
    for pg in reader.pages:
        pieces.append(pg.extract_text() or "")
    return "\n".join(pieces).strip()





def make_llm(model_name: str, max_new_tokens: int) -> Callable[[str], str]:
    from transformers import pipeline

    pipe = pipeline("text-generation", model = model_name)

    def run_one(prompt: str) -> str:
        response = pipe(
            prompt,
            max_new_tokens = max_new_tokens,
            return_full_text = False,
            do_sample = False,
        )
        return response[0]["generated_text"]

    return run_one






def safe_parse_output(raw_text: str) -> dict[str, list[dict[str, Any]]]:
    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return {"doc1": [], "doc2": []}

    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        return {"doc1": [], "doc2": []}

    fixed: dict[str, list[dict[str, Any]]] = {"doc1": [], "doc2": []}

    for doc_key in ["doc1", "doc2"]:

        items = data.get(doc_key, [])

        if not isinstance(items, list):
            continue

        for one in items:
            if isinstance(one, dict):
                fixed[doc_key].append(one)

    return fixed





def to_element_dict(merged: dict[str, set[str]]) -> dict[str, dict[str, Any]]:
      
    out: dict[str, dict[str, Any]] = {} 
    i = 1  
  
    for kde_name in sorted(merged.keys()):  
        
        out[f"element{i}"] = { 
            "name": kde_name, 
            "requirements": sorted(merged[kde_name]), 
        }

        i += 1  
 
    return out

 



def yaml_names(stem1: str, stem2: str, output_dir: Path) -> tuple[Path, Path]: 

    if stem1 == stem2:
        return output_dir / f"{stem1}-doc1-kdes.yaml", output_dir / f"{stem2}-doc2-kdes.yaml"
     
    return output_dir / f"{stem1}-kdes.yaml", output_dir / f"{stem2}-kdes.yaml" 
  

def copy_prompt_markdown_to_output(output_dir: Path) -> None:

    project_prompt = Path(__file__).resolve().parents[1] / "PROMPT.md"
    destination = output_dir / "PROMPT.md"

    if project_prompt.exists() and project_prompt.is_file():
        destination.write_text(project_prompt.read_text(encoding="utf-8"), encoding="utf-8")






