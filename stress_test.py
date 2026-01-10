import httpx
import asyncio
import time

# The "Tricky" Dataset: Things that standard NLP might miss
STRESS_TEST_CASES = [
    "My name is John Doe, but my friends call me The Nightingale.",
    "Contact the lead dev at dev-alpha-99@internal-secure.net.",
    "The secret passcode is 8822-XM and my employee ID is EMP-12345.",
    "The target is located at 123 Stealth Street, Sector 7G.",
    "Please send the files to 'The ghost in the machine' at ghost@anon.com.",
    "My social security is three-four-five, two-two, eight-eight-nine-nine.", # Written out numbers
    "Patient Jane Smith shows signs of acute insomnia.",
    "The encrypted key is 'Alpha-Bravo-992' and it belongs to Sarah.",
    "I am working with Agent 007 on the London project.",
    "The billing address is 456 Corporate Plaza, NY, 10001."
]

API_URL = "http://localhost:8000/redact"
RESTORE_URL = "http://localhost:8000/restore"

async def run_test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Starting Stress Test on {len(STRESS_TEST_CASES)} cases...\n")
        
        for i, text in enumerate(STRESS_TEST_CASES):
            print(f"Test Case {i+1}: '{text}'")
            
            # 1. Send to Redact Endpoint
            response = await client.post(API_URL, json={"text": text})
            res_data = response.json()
            redacted = res_data["redacted_text"]
            
            print(f"   [Primary] Redacted: {redacted}")
            
            # 2. Wait for Background Verification Agent (Phi-3) to think
            # We wait 5 seconds because LLM inference takes time
            print("   [System] Waiting for Verification Agent audit...")
            await asyncio.sleep(5)
            
            # 3. Verify if the record still exists in Redis
            # If the Auditor purged it, the 'restore' endpoint will return the same text
            restore_response = await client.post(RESTORE_URL, params={"redacted_text": redacted})
            restored_text = restore_response.json().get("original_text")
            
            if restored_text == redacted:
                print("   [Result] ALERT: Auditor detected a leak and PURGED the record.")
            else:
                print("   [Result] SAFE: Auditor cleared the redaction.")
            
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_test())