"""
LLM prompts for intelligent policy recommendation based on text content.

Analyzes text to determine the most appropriate policy context (general, healthcare, finance).
"""


# Policy Recommendation Prompt
POLICY_RECOMMENDATION_PROMPT = """You are a Privacy Policy Advisor analyzing text to recommend the most appropriate PII redaction policy.

## Available Policy Contexts

**1. General Policy**
- Purpose: Default policy for general-purpose PII redaction
- Use cases: Customer support, marketing, general communications
- Entities: PERSON, EMAIL, PHONE, CREDIT_CARD, SSN, LOCATION, IP_ADDRESS, URL, etc.
- Restoration: Disabled by default (opt-in required)
- Min confidence: 0.0 (detect all)

**2. Healthcare Policy (HIPAA-Compliant)**
- Purpose: Protected Health Information (PHI) redaction for medical data
- Use cases: Patient records, medical communications, healthcare providers
- Entities: PERSON, PHONE, EMAIL, SSN, DATE_TIME, LOCATION, IP_ADDRESS
- Restoration: Disabled (irreversible for compliance)
- Min confidence: 0.5 (stricter detection)
- Keywords: patient, doctor, hospital, diagnosis, treatment, medical, PHI, HIPAA, health

**3. Finance Policy (PCI-DSS-Compliant)**
- Purpose: Financial data redaction for payment card industry compliance
- Use cases: Banking, credit cards, financial transactions, payment processing
- Entities: PERSON, SSN, CREDIT_CARD, IBAN_CODE, PHONE, EMAIL, BANK_NUMBER, DRIVER_LICENSE
- Restoration: Disabled (irreversible for compliance)
- Min confidence: 0.6 (high confidence to protect financial PII)
- Keywords: credit card, payment, transaction, account, bank, financial, PCI-DSS, invoice

## Analysis Task

Analyze the text below and determine:
1. Which domain(s) are present (general, healthcare, finance)
2. Which policy context is most appropriate
3. Confidence in the recommendation (0.0-1.0)
4. Reasoning for the recommendation

**Text to analyze:**
"{text}"

## Analysis Guidelines

**Single Domain Detection:**
- If text contains ONLY healthcare terms → recommend "healthcare"
- If text contains ONLY finance terms → recommend "finance"
- If text is generic/mixed → recommend "general"

**Multi-Domain Detection:**
- If text contains BOTH healthcare AND finance terms → recommend the stricter policy (finance has higher threshold)
- Example: "Patient billing for credit card payment" → recommend "finance" (stricter)

**Confidence Scoring:**
- 0.9-1.0: Strong domain-specific keywords present (patient, diagnosis, credit card, transaction)
- 0.7-0.9: Moderate domain indicators (doctor, hospital, payment, account)
- 0.5-0.7: Weak domain indicators (some keywords but ambiguous)
- 0.0-0.5: No clear domain, default to general

**Alternative Contexts:**
- List other reasonable policy choices if applicable
- Example: "Patient credit card" could use healthcare OR finance

## Output Format

Return ONLY valid JSON:
{{
  "recommended_context": "general" or "healthcare" or "finance",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of why this policy was chosen",
  "detected_domains": ["list", "of", "domains"],
  "alternative_contexts": ["optional", "alternatives"],
  "risk_warning": "Optional warning if text contains cross-domain PII"
}}

## Examples

**Example 1: Healthcare Text**
Text: "Patient John Doe, DOB: 1990-05-15, diagnosis: hypertension"
Output: {{
  "recommended_context": "healthcare",
  "confidence": 0.95,
  "reasoning": "Contains clear PHI indicators (Patient, DOB, diagnosis). HIPAA compliance required.",
  "detected_domains": ["healthcare"],
  "alternative_contexts": [],
  "risk_warning": null
}}

**Example 2: Finance Text**
Text: "Credit card payment for $500, account #123456789"
Output: {{
  "recommended_context": "finance",
  "confidence": 0.92,
  "reasoning": "Contains financial PII (credit card, account number). PCI-DSS compliance required.",
  "detected_domains": ["finance"],
  "alternative_contexts": [],
  "risk_warning": null
}}

**Example 3: General Text**
Text: "Please contact Sarah at sarah@example.com for more info"
Output: {{
  "recommended_context": "general",
  "confidence": 0.85,
  "reasoning": "Generic communication with basic PII (name, email). No specific compliance domain detected.",
  "detected_domains": ["general"],
  "alternative_contexts": [],
  "risk_warning": null
}}

**Example 4: Multi-Domain Text**
Text: "Patient billing: credit card ending in 1234 for medical services"
Output: {{
  "recommended_context": "finance",
  "confidence": 0.88,
  "reasoning": "Mixed healthcare (Patient, medical) and finance (credit card, billing) data. Finance policy recommended as it has stricter thresholds (0.6 vs 0.5) and includes both healthcare entities plus financial PII.",
  "detected_domains": ["healthcare", "finance"],
  "alternative_contexts": ["healthcare"],
  "risk_warning": "Text contains cross-domain PII - consider using strictest policy or custom configuration"
}}

Now analyze the provided text and return your recommendation in JSON format.
"""


def get_policy_recommendation_prompt(text: str) -> str:
    """
    Get policy recommendation prompt for given text.

    Args:
        text: Text to analyze for policy recommendation

    Returns:
        Formatted prompt string
    """
    return POLICY_RECOMMENDATION_PROMPT.format(text=text)
