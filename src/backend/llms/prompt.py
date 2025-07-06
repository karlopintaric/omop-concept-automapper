DRUG_SYSTEM_PROMPT = """
#### **Task**
Match the given drug name to the most similar drug from a list of English drug names and evaluate the confidence of the match.
#### **Evaluation Criteria**
1. **Active Ingredients:** Must match exactly, including recognized alternative names (e.g., "paracetamol" = "acetaminophen").
2. **Dosage:** Dosages must be identical. Convert units if needed (e.g., 500mcg/5mL = 0.1mg/1mL).
3. **Formulation Type:** Must match (e.g., tablet, capsule, oral solution, extended-release).
4. **Route of Administration:** Must be the same (e.g., oral, injectable, topical).
#### **Additional Rules**
- If the input term is **not a branded name**, the selected match **must also not be branded**.
- When multiple candidates satisfy all criteria, prefer the **less specific or more general** equivalent over a narrowly defined version.
#### **Instructions**
- Ignore formatting or presentation differences that do not affect the evaluation.
- Assign a **Confidence Score (1–10)** reflecting how closely the drug matches the most similar English drug.
- If no suitable match is found, return `null` for both ID and Confidence Score.

## Output Format
Return your response as a JSON object with the following keys:
- `most_similar_item_id`: (string) The ID of the most similar English drug from the provided list, or `null` if no match is found.
- `confidence_score`: (integer, 1–10) Confidence score in the match, or `null` if no match is found.
"""

CONCEPT_SYSTEM_PROMPT = """
#### **Task**
Match the given input term to the most similar standardized term from a provided list of candidates. Evaluate the match based on core meaning, context, and linguistic similarity.
#### **Evaluation Criteria**
1. **Core Meaning:** The input term and candidate must describe the same concept or procedure.
2. **Context:** The matched term must align with the intended domain or application.
3. **Linguistic Similarity:** Consider similarities in wording, synonyms, and translation nuances.
#### **Additional Rules**
- The selected term should **not be more specific than the input term**.
- If unsure, prefer a **less specific but correct** term.
#### **Instructions**
- Ignore formatting or presentation differences that do not affect the evaluation.
- Assign a **Confidence Score (1–10)** reflecting match quality.
## Output Format
Return the result as a JSON object with the following fields:
- `most_similar_item_id` (string or integer): The ID of the most similar item from the provided list.
- `confidence_score` (integer, 1–10): The confidence score reflecting match quality.
"""


INPUT_PROMPT = """
#### **Input Parameters**  
- **Input Term:** `{input_term}`  
- **Candidate List:**  
`{candidate_list}`
"""
