"""
Benchmark datasets for evaluating PII redaction performance.

Each test case includes:
- id: Unique identifier
- text: Input text containing (or not containing) PII
- ground_truth: List of PII entities with type, position, and text
- category: Type of test case (standard, edge_case, negative, etc.)
"""

BENCHMARK_CASES = [
    # ========== STANDARD EMAIL CASES ==========
    {
        "id": "email_001",
        "text": "Contact me at john.doe@example.com for more information",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 14, "end": 35, "text": "john.doe@example.com"}
        ],
        "category": "standard"
    },
    {
        "id": "email_002",
        "text": "Send reports to alice.smith@company.org and bob@test.com",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 16, "end": 39, "text": "alice.smith@company.org"},
            {"type": "EMAIL_ADDRESS", "start": 44, "end": 57, "text": "bob@test.com"}
        ],
        "category": "standard"
    },
    {
        "id": "email_003",
        "text": "My personal email is jane_doe123@gmail.com",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 21, "end": 42, "text": "jane_doe123@gmail.com"}
        ],
        "category": "standard"
    },

    # ========== STANDARD PHONE NUMBER CASES ==========
    {
        "id": "phone_001",
        "text": "Call me at (555) 123-4567 anytime",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 11, "end": 25, "text": "(555) 123-4567"}
        ],
        "category": "standard"
    },
    {
        "id": "phone_002",
        "text": "Contact: 555-987-6543 or 555.111.2222",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 9, "end": 21, "text": "555-987-6543"},
            {"type": "PHONE_NUMBER", "start": 25, "end": 37, "text": "555.111.2222"}
        ],
        "category": "standard"
    },
    {
        "id": "phone_003",
        "text": "Office phone: +1-415-555-0123",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 14, "end": 29, "text": "+1-415-555-0123"}
        ],
        "category": "standard"
    },

    # ========== STANDARD PERSON NAME CASES ==========
    {
        "id": "name_001",
        "text": "My name is Jane Smith and I work at Acme Corp",
        "ground_truth": [
            {"type": "PERSON", "start": 11, "end": 21, "text": "Jane Smith"}
        ],
        "category": "standard"
    },
    {
        "id": "name_002",
        "text": "Dr. Robert Johnson will see you now",
        "ground_truth": [
            {"type": "PERSON", "start": 4, "end": 18, "text": "Robert Johnson"}
        ],
        "category": "standard"
    },
    {
        "id": "name_003",
        "text": "Please contact Mary Ann Williams or John Q. Public",
        "ground_truth": [
            {"type": "PERSON", "start": 15, "end": 33, "text": "Mary Ann Williams"},
            {"type": "PERSON", "start": 37, "end": 50, "text": "John Q. Public"}
        ],
        "category": "standard"
    },
    {
        "id": "name_004",
        "text": "The patient, Michael Chen, was admitted yesterday",
        "ground_truth": [
            {"type": "PERSON", "start": 13, "end": 25, "text": "Michael Chen"}
        ],
        "category": "standard"
    },

    # ========== LOCATION/ADDRESS CASES ==========
    {
        "id": "location_001",
        "text": "I live at 123 Main Street, Springfield, IL 62701",
        "ground_truth": [
            {"type": "LOCATION", "start": 10, "end": 48, "text": "123 Main Street, Springfield, IL 62701"}
        ],
        "category": "standard"
    },
    {
        "id": "location_002",
        "text": "Visit us at 456 Oak Avenue, New York, NY 10001",
        "ground_truth": [
            {"type": "LOCATION", "start": 12, "end": 46, "text": "456 Oak Avenue, New York, NY 10001"}
        ],
        "category": "standard"
    },

    # ========== MULTIPLE ENTITIES ==========
    {
        "id": "multi_001",
        "text": "Jane Doe (jane@example.com, 555-1234) is the contact person",
        "ground_truth": [
            {"type": "PERSON", "start": 0, "end": 8, "text": "Jane Doe"},
            {"type": "EMAIL_ADDRESS", "start": 10, "end": 26, "text": "jane@example.com"},
            {"type": "PHONE_NUMBER", "start": 28, "end": 36, "text": "555-1234"}
        ],
        "category": "multiple"
    },
    {
        "id": "multi_002",
        "text": "Employee Alice Brown (alice.b@corp.com) works in Building 5, Room 301",
        "ground_truth": [
            {"type": "PERSON", "start": 9, "end": 20, "text": "Alice Brown"},
            {"type": "EMAIL_ADDRESS", "start": 22, "end": 38, "text": "alice.b@corp.com"}
        ],
        "category": "multiple"
    },
    {
        "id": "multi_003",
        "text": "Customer John Smith called from 415-555-0100 regarding account #12345",
        "ground_truth": [
            {"type": "PERSON", "start": 9, "end": 19, "text": "John Smith"},
            {"type": "PHONE_NUMBER", "start": 32, "end": 44, "text": "415-555-0100"}
        ],
        "category": "multiple"
    },

    # ========== EDGE CASES ==========
    {
        "id": "edge_001",
        "text": "Contact José García at josé@example.com",
        "ground_truth": [
            {"type": "PERSON", "start": 8, "end": 19, "text": "José García"},
            {"type": "EMAIL_ADDRESS", "start": 23, "end": 39, "text": "josé@example.com"}
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_002",
        "text": "My SSN is 123-45-6789 for verification",
        "ground_truth": [
            {"type": "US_SSN", "start": 10, "end": 21, "text": "123-45-6789"}
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_003",
        "text": "Employee ID EMP-12345 belongs to the new hire",
        "ground_truth": [
            # Note: Employee IDs may not be detected by Presidio
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_004",
        "text": "Date of birth: 03/15/1985",
        "ground_truth": [
            {"type": "DATE_TIME", "start": 15, "end": 25, "text": "03/15/1985"}
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_005",
        "text": "Credit card ending in 4567",
        "ground_truth": [
            # Partial credit card not typically detected
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_006",
        "text": "IP address 192.168.1.100 accessed the system",
        "ground_truth": [
            {"type": "IP_ADDRESS", "start": 11, "end": 24, "text": "192.168.1.100"}
        ],
        "category": "edge_case"
    },
    {
        "id": "edge_007",
        "text": "UK phone number +44-20-7946-0958",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 16, "end": 32, "text": "+44-20-7946-0958"}
        ],
        "category": "edge_case"
    },

    # ========== NEGATIVE CASES (NO PII) ==========
    {
        "id": "negative_001",
        "text": "This is a clean text with no personal information.",
        "ground_truth": [],
        "category": "negative"
    },
    {
        "id": "negative_002",
        "text": "The product costs $99.99 and ships in 3-5 business days.",
        "ground_truth": [],
        "category": "negative"
    },
    {
        "id": "negative_003",
        "text": "Meeting scheduled for 2:00 PM in Conference Room B.",
        "ground_truth": [],
        "category": "negative"
    },
    {
        "id": "negative_004",
        "text": "Error code 500: Internal server error occurred.",
        "ground_truth": [],
        "category": "negative"
    },
    {
        "id": "negative_005",
        "text": "Please refer to document section 4.2 for details.",
        "ground_truth": [],
        "category": "negative"
    },

    # ========== AMBIGUOUS CASES ==========
    {
        "id": "ambiguous_001",
        "text": "Contact Apple Support for assistance",
        "ground_truth": [
            # "Apple" is a company, not a person - should not be redacted as PERSON
        ],
        "category": "ambiguous"
    },
    {
        "id": "ambiguous_002",
        "text": "The patient, referred to as Patient X, was treated",
        "ground_truth": [
            # "Patient X" is an anonymized reference, not actual PII
        ],
        "category": "ambiguous"
    },
    {
        "id": "ambiguous_003",
        "text": "Robert Johnson Company announced new product",
        "ground_truth": [
            # May detect "Robert Johnson" as person when it's actually company name
        ],
        "category": "ambiguous"
    },

    # ========== CONTEXT-DEPENDENT CASES ==========
    {
        "id": "context_001",
        "text": "Patient Jane Smith shows signs of acute insomnia",
        "ground_truth": [
            {"type": "PERSON", "start": 8, "end": 18, "text": "Jane Smith"}
        ],
        "category": "context"
    },
    {
        "id": "context_002",
        "text": "Dr. Martinez prescribed medication for the condition",
        "ground_truth": [
            {"type": "PERSON", "start": 4, "end": 12, "text": "Martinez"}
        ],
        "category": "context"
    },

    # ========== ADDITIONAL STANDARD CASES FOR BETTER COVERAGE ==========
    {
        "id": "email_004",
        "text": "Support email: support@company.com",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 15, "end": 34, "text": "support@company.com"}
        ],
        "category": "standard"
    },
    {
        "id": "email_005",
        "text": "Reply to admin.user@test-domain.co.uk for access",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 9, "end": 38, "text": "admin.user@test-domain.co.uk"}
        ],
        "category": "standard"
    },
    {
        "id": "name_005",
        "text": "Thank you, Sarah Johnson, for your contribution",
        "ground_truth": [
            {"type": "PERSON", "start": 11, "end": 24, "text": "Sarah Johnson"}
        ],
        "category": "standard"
    },
    {
        "id": "name_006",
        "text": "Mr. David Lee submitted the application",
        "ground_truth": [
            {"type": "PERSON", "start": 4, "end": 13, "text": "David Lee"}
        ],
        "category": "standard"
    },
    {
        "id": "phone_004",
        "text": "Emergency contact: 800-555-0199",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 19, "end": 31, "text": "800-555-0199"}
        ],
        "category": "standard"
    },
    {
        "id": "mixed_001",
        "text": "For questions, email help@site.com or call 1-888-555-1212",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 21, "end": 34, "text": "help@site.com"},
            {"type": "PHONE_NUMBER", "start": 43, "end": 57, "text": "1-888-555-1212"}
        ],
        "category": "multiple"
    },
    {
        "id": "complex_001",
        "text": "Dr. Emily Watson (emily.watson@hospital.org, ext. 5523) will review your file",
        "ground_truth": [
            {"type": "PERSON", "start": 4, "end": 16, "text": "Emily Watson"},
            {"type": "EMAIL_ADDRESS", "start": 18, "end": 43, "text": "emily.watson@hospital.org"}
        ],
        "category": "multiple"
    },
    {
        "id": "url_email_001",
        "text": "Visit https://example.com or email contact@example.com",
        "ground_truth": [
            {"type": "EMAIL_ADDRESS", "start": 35, "end": 54, "text": "contact@example.com"}
            # URL typically not considered PII
        ],
        "category": "standard"
    },

    # ========== TRICKY FORMAT VARIATIONS ==========
    {
        "id": "phone_variation_001",
        "text": "Call 555 123 4567 for support",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 5, "end": 17, "text": "555 123 4567"}
        ],
        "category": "edge_case"
    },
    {
        "id": "phone_variation_002",
        "text": "Mobile: 5551234567",
        "ground_truth": [
            {"type": "PHONE_NUMBER", "start": 8, "end": 18, "text": "5551234567"}
        ],
        "category": "edge_case"
    },
    {
        "id": "name_variation_001",
        "text": "J. Smith signed the document",
        "ground_truth": [
            {"type": "PERSON", "start": 0, "end": 8, "text": "J. Smith"}
        ],
        "category": "edge_case"
    },
]


def get_benchmark_cases(category=None):
    """
    Get benchmark cases, optionally filtered by category.

    Args:
        category: Optional category filter (standard, edge_case, negative, etc.)

    Returns:
        List of test cases
    """
    if category is None:
        return BENCHMARK_CASES
    return [case for case in BENCHMARK_CASES if case["category"] == category]


def get_categories():
    """Get all unique categories in the benchmark."""
    return list(set(case["category"] for case in BENCHMARK_CASES))


def get_statistics():
    """Get statistics about the benchmark dataset."""
    total_cases = len(BENCHMARK_CASES)
    categories = get_categories()

    category_counts = {cat: len(get_benchmark_cases(cat)) for cat in categories}

    total_entities = sum(len(case["ground_truth"]) for case in BENCHMARK_CASES)
    cases_with_pii = sum(1 for case in BENCHMARK_CASES if len(case["ground_truth"]) > 0)
    cases_without_pii = total_cases - cases_with_pii

    entity_types = {}
    for case in BENCHMARK_CASES:
        for entity in case["ground_truth"]:
            entity_type = entity["type"]
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    return {
        "total_cases": total_cases,
        "cases_with_pii": cases_with_pii,
        "cases_without_pii": cases_without_pii,
        "total_entities": total_entities,
        "categories": category_counts,
        "entity_types": entity_types
    }


if __name__ == "__main__":
    # Print dataset statistics
    stats = get_statistics()
    print("=== Benchmark Dataset Statistics ===")
    print(f"Total test cases: {stats['total_cases']}")
    print(f"Cases with PII: {stats['cases_with_pii']}")
    print(f"Cases without PII: {stats['cases_without_pii']}")
    print(f"Total PII entities: {stats['total_entities']}")
    print("\nCases by category:")
    for cat, count in stats['categories'].items():
        print(f"  {cat}: {count}")
    print("\nEntity types:")
    for entity_type, count in stats['entity_types'].items():
        print(f"  {entity_type}: {count}")
