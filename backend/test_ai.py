#!/usr/bin/env python3
"""
Quick test script to verify AI processing is working.
Run this from the backend directory: python3 test_ai.py
"""

import os
import sys

# Check if API key is set
api_key = os.environ.get("ANTHROPIC_API_KEY", "")
print("=" * 60)
print("AI Processing Test")
print("=" * 60)

if not api_key:
    print("❌ ANTHROPIC_API_KEY is not set in environment")
    print("   Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
    sys.exit(1)

if api_key == "your-anthropic-api-key-here":
    print("❌ ANTHROPIC_API_KEY is still the placeholder value")
    print("   Update your .env file with a real API key")
    sys.exit(1)

print(f"✅ API key is set: {api_key[:20]}...{api_key[-10:]}")
print()

# Try to import and test the AI module
try:
    from ai import answer_request
    from graph import GraphState
    from rag import RAGIndex, SentenceTransformersEmbedder

    print("✅ AI modules imported successfully")
    print()

    # Create minimal test setup
    print("Testing AI with a simple query...")
    print()

    # Note: This will make a real API call!
    test_subject = "Climate change policies"
    test_description = "What are the current climate change policies?"

    print(f"Subject: {test_subject}")
    print(f"Description: {test_description}")
    print()
    print("Calling AI (this may take a few seconds)...")
    print()

    try:
        response = answer_request(
            subject=test_subject,
            description=test_description,
            rag_index=None,  # No RAG index for this test
            graph_retriever=None,  # No graph for this test
        )

        print("✅ AI call successful!")
        print()
        print("Response:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print()
        print("✅ AI is working correctly!")

    except Exception as e:
        print(f"❌ AI call failed: {e}")
        print()
        print("Common issues:")
        print("- Invalid API key")
        print("- API quota exceeded")
        print("- Network connectivity issues")
        sys.exit(1)

except ImportError as e:
    print(f"❌ Failed to import modules: {e}")
    print("   Make sure you're in the backend directory")
    sys.exit(1)

print()
print("=" * 60)
print("All tests passed! AI is configured correctly.")
print("=" * 60)
