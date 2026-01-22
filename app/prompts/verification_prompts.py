"""
Structured prompt templates for LLM-based PII leak verification.

Contains multiple prompt versions for A/B testing and optimization.
"""
from app.prompts.few_shot_examples import get_formatted_examples


# Version 1: Basic Zero-Shot Prompt (Legacy - Boolean)
BASIC_PROMPT_V1 = """You are a Privacy Security Auditor. Your job is to find any UNREDACTED
Personally Identifiable Information (PII) in the text below.

PII includes: Names, Emails, SSNs, Phone Numbers, or ID numbers.

Text to check: "{text}"

Return ONLY a JSON object with:
"leaked": true/false,
"reason": "explanation of what was missed"
"""


# Version 1 Risk Scorer: Basic Risk Scoring Prompt
BASIC_RISK_PROMPT_V1 = """You are a Privacy Security Auditor. Analyze the redacted text below and assign a PII leak risk score.

PII includes: Names, Emails, SSNs, Phone Numbers, Addresses, ID numbers, Dates of Birth.

Text to analyze: "{text}"

Evaluate risk on a scale of 0.0 to 1.0:
- 0.0-0.3: Low risk (all PII properly redacted)
- 0.3-0.5: Medium risk (minor issues, contextual clues)
- 0.5-0.7: High risk (partial PII visible, format preservation)
- 0.7-1.0: Critical risk (clear PII leakage)

Return ONLY a JSON object with:
"risk_score": 0.0 to 1.0,
"risk_factors": ["list", "of", "specific", "risks"],
"recommended_action": "allow" or "alert" or "purge",
"confidence": 0.0 to 1.0
"""


# Version 2: Chain-of-Thought Reasoning (Legacy - Boolean)
CHAIN_OF_THOUGHT_PROMPT_V2 = """You are a Privacy Security Auditor analyzing redacted text for PII leaks.

## Task
Identify ANY unredacted Personally Identifiable Information (PII) in the text below.

## PII Categories to Check
- Names (full names, first names with last initial, nicknames)
- Email addresses
- Phone numbers (any format: (555) 123-4567, 555-123-4567, +1-555-123-4567)
- Social Security Numbers (SSNs, any format)
- Physical addresses
- ID numbers (employee IDs, customer IDs, account numbers, license plates)
- Dates of birth
- Medical record numbers
- IP addresses
- Partial identifiers (last 4 of SSN, partial credit card, etc.)

## Analysis Process (Think Step-by-Step)

**Text to analyze:**
"{text}"

**Your Analysis:**
1. **Scan for names:** Look for proper nouns, titles (Dr., Mr., Mrs.), and personal names
2. **Check emails:** Look for name@domain.com patterns
3. **Find phone numbers:** Check for digit patterns that match phone formats
4. **Identify numbers:** Look for SSNs, IDs, account numbers
5. **Check addresses:** Look for street addresses, zip codes
6. **Verify redaction tokens:** Ensure [REDACTED_xxxx] tokens are used for sensitive data

**Decision:**
Are there any PII values that are NOT redacted (not replaced with [REDACTED_xxxx] tokens)?

## Output Format
Return ONLY valid JSON:
{{"leaked": true/false, "reason": "specific explanation of what leaked or why it's clean"}}
"""


# Version 2 Risk Scorer: Chain-of-Thought Risk Scoring
CHAIN_OF_THOUGHT_RISK_PROMPT_V2 = """You are a Privacy Security Auditor performing risk analysis on redacted text.

## Task
Analyze the text below and assign a PII leak risk score from 0.0 (no risk) to 1.0 (critical risk).

## PII Categories to Check
- Names (full names, first names with last initial, nicknames)
- Email addresses
- Phone numbers (any format)
- Social Security Numbers (SSNs, any format)
- Physical addresses
- ID numbers (employee IDs, customer IDs, account numbers)
- Dates of birth
- Medical record numbers
- IP addresses
- Partial identifiers (last 4 of SSN, partial credit card)

## Risk Analysis Process (Think Step-by-Step)

**Text to analyze:**
"{text}"

**Step 1: Direct PII Detection**
- Are there any actual PII values visible (names, emails, phone numbers, SSNs)?
- If yes: HIGH RISK (0.7-1.0)

**Step 2: Format Preservation Analysis**
- Are PII formats preserved (e.g., XXX-XX-XXXX for SSN, (XXX) XXX-XXXX for phone)?
- If yes: MEDIUM-HIGH RISK (0.5-0.7)

**Step 3: Contextual Inference Risk**
- Can tokens be linked to identities through context?
- Example: "Patient [REDACTED_a1b2], DOB: [REDACTED_c3d4]" - tokens are linkable
- If yes: MEDIUM RISK (0.3-0.5)

**Step 4: Token Adjacency Analysis**
- Are multiple tokens close together (within 3 words)?
- This allows relationship inference between PII elements
- If yes: LOW-MEDIUM RISK (0.2-0.4)

**Step 5: Overall Assessment**
Combine all risk factors to determine final risk score and recommend action:
- 0.0-0.3: Low risk → "allow"
- 0.3-0.5: Medium risk → "allow" (but log for review)
- 0.5-0.7: High risk → "alert"
- 0.7-1.0: Critical risk → "purge"

## Output Format
Return ONLY valid JSON:
{{
  "risk_score": 0.0 to 1.0,
  "risk_factors": ["specific risk 1", "specific risk 2", ...],
  "recommended_action": "allow" or "alert" or "purge",
  "confidence": 0.0 to 1.0
}}
"""


# Version 3: Few-Shot Learning (Legacy - Boolean)
def get_few_shot_prompt_v3(text: str, num_examples: int = 3) -> str:
    """
    Generate few-shot prompt with examples.

    Args:
        text: Text to analyze
        num_examples: Number of few-shot examples to include

    Returns:
        Formatted prompt with examples
    """
    examples = get_formatted_examples(count=num_examples, include_analysis=True)

    return f"""You are a Privacy Security Auditor specialized in detecting PII leaks in redacted text.

## Your Task
Analyze text to find ANY unredacted Personally Identifiable Information (PII).
Properly redacted text uses tokens like [REDACTED_xxxx].

## PII Types
- Names, Emails, Phone Numbers, SSNs, Addresses, IDs, Dates of Birth, Medical Records, IP Addresses

## Examples of Correct Analysis

{examples}

## Now Analyze This Text

Text: "{text}"

Think through each PII category systematically. Are there any identifiers that are NOT redacted?

Return ONLY valid JSON:
{{"leaked": true/false, "reason": "specific explanation"}}
"""


# Version 3 Risk Scorer: Few-Shot Risk Scoring (Best Performance)
def get_few_shot_risk_prompt_v3(text: str, num_examples: int = 3) -> str:
    """
    Generate few-shot risk scoring prompt with examples.

    Args:
        text: Text to analyze
        num_examples: Number of few-shot examples to include

    Returns:
        Formatted risk scoring prompt
    """
    return f"""You are a Privacy Security Auditor performing PII leak risk analysis on redacted text.

## Your Task
Assign a risk score (0.0-1.0) based on PII exposure risk. Properly redacted text uses [REDACTED_xxxx] tokens.

## Risk Scoring Examples

**Example 1: Low Risk (Score: 0.1)**
Text: "Contact [REDACTED_a1b2c3] at [REDACTED_d4e5f6]"
Analysis: {{
  "risk_score": 0.1,
  "risk_factors": ["All PII properly tokenized", "No visible identifiers"],
  "recommended_action": "allow",
  "confidence": 0.95
}}

**Example 2: Medium Risk (Score: 0.45)**
Text: "Patient [REDACTED_a1b2], DOB: [REDACTED_c3d4], Room 302"
Analysis: {{
  "risk_score": 0.45,
  "risk_factors": ["Token adjacency suggests PHI relationship", "Room number could be quasi-identifier", "Contextual word 'Patient' links tokens"],
  "recommended_action": "allow",
  "confidence": 0.88
}}

**Example 3: High Risk (Score: 0.65)**
Text: "SSN: XXX-XX-1234, Phone: (555) XXX-XXXX"
Analysis: {{
  "risk_score": 0.65,
  "risk_factors": ["Format preservation: SSN pattern visible (XXX-XX-XXXX)", "Format preservation: Phone pattern visible", "Partial SSN exposed (last 4 digits)", "Combining patterns increases re-identification risk"],
  "recommended_action": "alert",
  "confidence": 0.92
}}

**Example 4: Critical Risk (Score: 0.95)**
Text: "Contact John Doe at john.doe@email.com or 555-123-4567"
Analysis: {{
  "risk_score": 0.95,
  "risk_factors": ["Direct PII leak: full name 'John Doe'", "Direct PII leak: email 'john.doe@email.com'", "Direct PII leak: phone '555-123-4567'", "Multiple PII elements linkable to single identity"],
  "recommended_action": "purge",
  "confidence": 0.98
}}

## Now Analyze This Text

Text: "{text}"

**Analysis Steps:**
1. Check for direct PII leaks (names, emails, phones, SSNs visible)
2. Check for format preservation (patterns like XXX-XX-XXXX, (XXX) XXX-XXXX)
3. Check for token adjacency (multiple tokens within 3 words)
4. Check for contextual inference risk (keywords linking tokens)
5. Assess partial identifiers (last 4 of SSN, partial credit cards)

**Risk Score Guidelines:**
- 0.0-0.3: Low risk (properly redacted) → "allow"
- 0.3-0.5: Medium risk (contextual clues) → "allow"
- 0.5-0.7: High risk (format preservation, adjacency) → "alert"
- 0.7-1.0: Critical risk (direct PII visible) → "purge"

Return ONLY valid JSON:
{{
  "risk_score": 0.0 to 1.0,
  "risk_factors": ["specific", "risk", "factors"],
  "recommended_action": "allow" or "alert" or "purge",
  "confidence": 0.0 to 1.0
}}
"""


# Version 4: Optimized Few-Shot (Legacy - Boolean)
def get_optimized_few_shot_prompt_v4(text: str) -> str:
    """
    Optimized few-shot prompt (shorter, faster inference).

    Args:
        text: Text to analyze

    Returns:
        Optimized prompt
    """
    # Use only 2 best examples (leaked + clean)
    return f"""You are a PII leak detector. Find unredacted PII (names, emails, phones, SSNs, IDs).

Examples:
- "[REDACTED_a1] at [REDACTED_b2]" → {{"leaked": false, "reason": "All PII redacted"}}
- "Email john@test.com" → {{"leaked": true, "reason": "Email john@test.com exposed"}}
- "Call 555-1234" → {{"leaked": true, "reason": "Phone 555-1234 exposed"}}

Text: "{text}"

JSON only:"""


# Version 4 Risk Scorer: Optimized Risk Scoring (Fast)
def get_optimized_risk_prompt_v4(text: str) -> str:
    """
    Optimized risk scoring prompt (concise, fast inference).

    Args:
        text: Text to analyze

    Returns:
        Optimized risk scoring prompt
    """
    return f"""PII Risk Scorer. Rate 0.0-1.0. Check: names, emails, phones, SSNs, addresses, IDs.

Examples:
- "[REDACTED_a1] at [REDACTED_b2]" → {{"risk_score": 0.1, "risk_factors": ["All redacted"], "recommended_action": "allow", "confidence": 0.95}}
- "Email john@test.com" → {{"risk_score": 0.95, "risk_factors": ["Email exposed"], "recommended_action": "purge", "confidence": 0.98}}
- "SSN: XXX-XX-1234" → {{"risk_score": 0.65, "risk_factors": ["Format preserved", "Partial SSN"], "recommended_action": "alert", "confidence": 0.90}}

Text: "{text}"

Risk levels: 0.0-0.3=allow, 0.3-0.5=allow, 0.5-0.7=alert, 0.7-1.0=purge

JSON only:"""


def get_prompt(version: str, text: str, risk_mode: bool = False, **kwargs) -> str:
    """
    Get prompt by version with support for risk scoring mode.

    Args:
        version: Prompt version (v1_basic, v2_cot, v3_few_shot, v4_optimized)
        text: Text to analyze
        risk_mode: If True, use risk scoring prompts instead of boolean leak detection
        **kwargs: Additional parameters (e.g., num_examples for few-shot)

    Returns:
        Formatted prompt string
    """
    # Risk scoring mode
    if risk_mode:
        if version == "v1_basic":
            return BASIC_RISK_PROMPT_V1.format(text=text)
        elif version == "v2_cot":
            return CHAIN_OF_THOUGHT_RISK_PROMPT_V2.format(text=text)
        elif version == "v3_few_shot":
            num_examples = kwargs.get("num_examples", 3)
            return get_few_shot_risk_prompt_v3(text, num_examples)
        elif version == "v4_optimized":
            return get_optimized_risk_prompt_v4(text)
        else:
            # Default to basic risk prompt
            return BASIC_RISK_PROMPT_V1.format(text=text)

    # Legacy boolean leak detection mode
    else:
        if version == "v1_basic":
            return BASIC_PROMPT_V1.format(text=text)
        elif version == "v2_cot":
            return CHAIN_OF_THOUGHT_PROMPT_V2.format(text=text)
        elif version == "v3_few_shot":
            num_examples = kwargs.get("num_examples", 3)
            return get_few_shot_prompt_v3(text, num_examples)
        elif version == "v4_optimized":
            return get_optimized_few_shot_prompt_v4(text)
        else:
            # Default to basic
            return BASIC_PROMPT_V1.format(text=text)


if __name__ == "__main__":
    # Test prompts
    test_text = "Contact [REDACTED_a1b2] at john.doe@example.com"

    print("=" * 70)
    print("PROMPT VERSION COMPARISON")
    print("=" * 70)
    print()

    for version in ["v1_basic", "v2_cot", "v3_few_shot", "v4_optimized"]:
        print(f"### {version.upper()} ###")
        print()
        prompt = get_prompt(version, test_text)
        print(prompt)
        print()
        print("-" * 70)
        print()
