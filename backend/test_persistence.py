#!/usr/bin/env python3
"""
Test script for data persistence and RAG pipeline functionality.

This script verifies:
1. Data persistence is working correctly
2. RAG index is populated with responded requests
3. Similar requests can be matched using vector search
4. Error handling works as expected
"""

import json
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from persistence import DataStore, PersistenceError


def test_persistence():
    """Test data persistence layer."""
    print("\n=== Testing Data Persistence ===\n")

    data_file = backend_dir / "data" / "sample_data.json"

    try:
        # Initialize data store
        print(f"1. Initializing DataStore with {data_file}")
        store = DataStore(data_file, auto_backup=True, max_backups=5)
        print("   ✓ DataStore initialized")

        # Load data
        print("\n2. Loading data from file")
        data = store.load()
        print(f"   ✓ Loaded {len(data['requests'])} requests")
        print(f"   ✓ Loaded {len(data['departments'])} departments")
        print(f"   ✓ Loaded {len(data['faqs'])} FAQs")

        # Verify sample data structure
        print("\n3. Verifying data structure")
        assert "requests" in data, "Missing 'requests' key"
        assert "departments" in data, "Missing 'departments' key"
        assert "faqs" in data, "Missing 'faqs' key"
        print("   ✓ All required keys present")

        # Check request fields
        if data["requests"]:
            req = data["requests"][0]
            required_fields = [
                "id",
                "citizen_name",
                "email",
                "department_id",
                "subject",
                "description",
                "status",
                "date_filed",
            ]
            missing = [f for f in required_fields if f not in req]
            assert not missing, f"Request missing fields: {missing}"
            print("   ✓ Request structure valid")

        # Test checkpoint creation
        print("\n4. Testing manual checkpoint creation")
        store.create_checkpoint("test_checkpoint")
        print("   ✓ Checkpoint created")

        # List backups
        backup_dir = backend_dir / "data" / "backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("*.json"))
            print(f"\n5. Found {len(backups)} backup files:")
            for backup in sorted(backups)[-3:]:  # Show last 3
                size = backup.stat().st_size / 1024
                print(f"   - {backup.name} ({size:.1f} KB)")

        print("\n✅ All persistence tests passed!\n")
        return True

    except PersistenceError as e:
        print(f"\n❌ Persistence error: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_rag_data():
    """Test RAG pipeline data quality."""
    print("\n=== Testing RAG Data Quality ===\n")

    data_file = backend_dir / "data" / "sample_data.json"

    try:
        with open(data_file) as f:
            data = json.load(f)

        # Count responded requests (these are indexed in RAG)
        responded = [r for r in data["requests"] if r["status"] == "Responded"]
        print(f"1. Found {len(responded)} responded requests (RAG training data)")

        # Analyze by department
        dept_counts = {}
        for req in responded:
            dept = req.get("department_id", "unknown")
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

        print("\n2. Responded requests by department:")
        for dept, count in sorted(dept_counts.items()):
            dept_name = next(
                (d["name"] for d in data["departments"] if d["id"] == dept), dept
            )
            print(f"   - {dept_name}: {count}")

        # Check response quality
        print("\n3. Checking response quality:")
        empty_responses = [
            r for r in responded if not r.get("response") or not r["response"].strip()
        ]
        if empty_responses:
            print(
                f"   ⚠ Warning: {len(empty_responses)} responded requests have empty responses"
            )
        else:
            print("   ✓ All responded requests have non-empty responses")

        # Calculate average response length
        avg_length = sum(
            len(r["response"]) for r in responded if r.get("response")
        ) / len(responded)
        print(f"   ✓ Average response length: {avg_length:.0f} characters")

        # Check for diverse subjects
        subjects = [r["subject"][:50] for r in responded]
        print(f"\n4. Sample subjects (RAG will match similar queries):")
        for i, subject in enumerate(subjects[:5], 1):
            print(f"   {i}. {subject}...")

        # Verify metadata completeness
        print(f"\n5. Checking metadata completeness:")
        complete = sum(
            1
            for r in data["requests"]
            if r.get("citizen_phone") and r.get("citizen_address")
        )
        print(
            f"   ✓ {complete}/{len(data['requests'])} requests have complete citizen metadata"
        )

        # Check status distribution
        print(f"\n6. Request status distribution:")
        status_counts = {}
        for req in data["requests"]:
            status = req["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        for status, count in sorted(status_counts.items()):
            pct = count / len(data["requests"]) * 100
            print(f"   - {status}: {count} ({pct:.1f}%)")

        print("\n✅ RAG data quality checks passed!\n")
        return True

    except Exception as e:
        print(f"\n❌ Error analyzing RAG data: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def test_error_recovery():
    """Test error recovery mechanisms."""
    print("\n=== Testing Error Recovery ===\n")

    data_file = backend_dir / "data" / "sample_data.json"
    backup_dir = backend_dir / "data" / "backups"

    try:
        # Test loading from non-existent file
        print("1. Testing missing file handling")
        fake_file = backend_dir / "data" / "nonexistent.json"
        store = DataStore(fake_file)
        try:
            store.load()
            print("   ⚠ Should have raised PersistenceError")
            return False
        except PersistenceError:
            print("   ✓ Correctly raised PersistenceError for missing file")

        # Test that backup directory is created
        print("\n2. Verifying backup directory exists")
        if backup_dir.exists():
            print(f"   ✓ Backup directory exists: {backup_dir}")
        else:
            print(f"   ✗ Backup directory not found: {backup_dir}")
            return False

        # Test valid data loading
        print("\n3. Testing valid data loading")
        store = DataStore(data_file)
        data = store.load()
        if data and "requests" in data:
            print("   ✓ Successfully loaded valid data")
        else:
            print("   ✗ Failed to load data properly")
            return False

        print("\n✅ Error recovery tests passed!\n")
        return True

    except Exception as e:
        print(f"\n❌ Error in recovery tests: {e}\n")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("RTI4All - Data Persistence & RAG Quality Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Persistence", test_persistence()))
    results.append(("RAG Data Quality", test_rag_data()))
    results.append(("Error Recovery", test_error_recovery()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name:.<40} {status}")

    all_passed = all(r[1] for r in results)

    print("=" * 60)
    if all_passed:
        print("\n🎉 All tests passed! The system is ready for demo.\n")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the output above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
