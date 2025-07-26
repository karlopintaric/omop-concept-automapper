#!/usr/bin/env python3
"""
Simple test runner for all auto-omop-mapper tests.
Just run: python3 run_simple_tests.py
"""

import sys
import os
import unittest

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def run_all_tests():
    """Run all simple tests"""
    print("🧪 Running Auto OMOP Mapper Tests...")
    print("=" * 50)

    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Test modules to run
    test_modules = [
        "tests.test_vector_store",
        "tests.test_embedding",
        "tests.test_chat",
        "tests.test_reranker",
        "tests.test_client",
    ]

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    loaded_count = 0
    # Load tests from each module
    for module_name in test_modules:
        try:
            module = __import__(module_name, fromlist=[""])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            loaded_count += 1
            print(f"✅ Loaded tests from {module_name}")
        except ImportError as e:
            print(f"❌ Failed to load {module_name}: {e}")
            continue
        except Exception as e:
            print(f"❌ Error loading {module_name}: {e}")
            continue

    if loaded_count == 0:
        print("❌ No test modules could be loaded!")
        return False

    print(f"\n📦 Successfully loaded {loaded_count} test modules")
    print("=" * 50)
    print("Running tests...")
    print("-" * 50)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("-" * 50)

    if result.wasSuccessful():
        print(f"✅ All {result.testsRun} tests passed!")
        print("✅ Your auto mapper is working correctly!")
    else:
        failed = len(result.failures + result.errors)
        print(f"❌ {failed} tests failed out of {result.testsRun}")
        print("❌ Check the output above for details")

        # Show failed tests
        if result.failures:
            print("\nFAILED TESTS:")
            for test, traceback in result.failures:
                print(f"  - {test}")

        if result.errors:
            print("\nERROR TESTS:")
            for test, traceback in result.errors:
                print(f"  - {test}")

    print("=" * 50)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
