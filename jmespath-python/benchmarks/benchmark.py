"""Benchmark comparing jmespath-rust to native Python jmespath.

Key finding: Data structure complexity (not just size) determines performance.
- Simple flat data + complex queries = Rust wins
- Nested/complex data = Python wins (conversion overhead dominates)
"""

import json
import time

import jmespath as jmespath_py
import jmespath_rust


def make_simple_data(size):
    """Generate simple flat data (3 fields per record)."""
    return {
        "people": [
            {"name": f"person_{i}", "age": i % 100, "city": f"city_{i % 50}"} for i in range(size)
        ]
    }


def make_complex_data(size):
    """Generate complex nested data (nested objects + arrays)."""
    return {
        "people": [
            {
                "name": f"person_{i}",
                "age": i % 100,
                "city": f"city_{i % 50}",
                "department": f"dept_{i % 10}",
                "scores": [i % 100, (i * 2) % 100, (i * 3) % 100],
                "metadata": {
                    "created": f"2024-01-{(i % 28) + 1:02d}",
                    "active": i % 2 == 0,
                    "tags": [f"tag_{i % 5}", f"tag_{(i + 1) % 5}"],
                },
            }
            for i in range(size)
        ]
    }


def benchmark(func, iterations=100):
    """Benchmark a function and return elapsed time."""
    # Warmup
    for _ in range(10):
        func()

    start = time.perf_counter()
    for _ in range(iterations):
        func()
    return time.perf_counter() - start


def run_comparison(name, data, expressions, iterations=100):
    """Run benchmark comparison for a dataset."""
    json_data = json.dumps(data)
    json_size = len(json_data)

    print(f"\n{'=' * 80}")
    print(f"{name} (JSON size: {json_size:,} bytes)")
    print("=" * 80)
    print(f"{'Expression':<40} {'Python':<12} {'Rust':<12} {'Winner':<15}")
    print("-" * 80)

    for expr_name, expr_str in expressions:
        py_expr = jmespath_py.compile(expr_str)
        rust_expr = jmespath_rust.compile(expr_str)

        py_time = benchmark(lambda e=py_expr, d=data: e.search(d), iterations)
        rust_time = benchmark(lambda e=rust_expr, d=data: e.search(d), iterations)

        py_ms = (py_time / iterations) * 1000
        rust_ms = (rust_time / iterations) * 1000

        if py_ms < rust_ms:
            winner = f"Python {rust_ms / py_ms:.1f}x"
        else:
            winner = f"Rust {py_ms / rust_ms:.1f}x"

        print(f"{expr_name:<40} {py_ms:<12.3f} {rust_ms:<12.3f} {winner:<15}")


def main():
    print("=" * 80)
    print("JMESPath Benchmark: Python vs Rust")
    print("Key factor: DATA STRUCTURE COMPLEXITY")
    print("=" * 80)

    # Expressions from simple to complex
    expressions = [
        ("Simple: field access", "people[0].name"),
        ("Simple: length", "length(people)"),
        ("Medium: wildcard", "people[*].name"),
        ("Medium: multi-select", "people[*].{n: name, a: age}"),
        ("Complex: filter", "people[?age > `50`].name"),
        ("Complex: filter + sort", "sort_by(people, &age)[0:10].name"),
        ("Very complex: chained", "people[?age > `30`] | [0:10].{n: name, a: age}"),
    ]

    # Test with different data complexities
    for size in [500, 1000, 2000]:
        simple_data = make_simple_data(size)
        complex_data = make_complex_data(size)

        run_comparison(
            f"SIMPLE DATA - {size} records, 3 fields each",
            simple_data,
            expressions,
        )

        run_comparison(
            f"COMPLEX DATA - {size} records, nested objects + arrays",
            complex_data,
            expressions,
        )

    # Batch operations - where Rust shines
    print("\n" + "=" * 80)
    print("BATCH OPERATIONS (many small documents)")
    print("=" * 80)

    for doc_count in [100, 500, 1000]:
        # Small simple documents
        documents = [{"id": i, "value": i * 10, "active": i % 2 == 0} for i in range(doc_count)]
        json_documents = [json.dumps(d) for d in documents]

        expr_str = "[?active].id"
        py_expr = jmespath_py.compile(expr_str)
        rust_expr = jmespath_rust.compile(expr_str)

        iterations = 50

        py_time = benchmark(lambda: [py_expr.search(d) for d in documents], iterations)
        rust_batch_time = benchmark(lambda: rust_expr.search_many(documents), iterations)

        py_ms = (py_time / iterations) * 1000
        rust_ms = (rust_batch_time / iterations) * 1000

        if py_ms < rust_ms:
            winner = f"Python {rust_ms / py_ms:.1f}x"
        else:
            winner = f"Rust {py_ms / rust_ms:.1f}x"

        print(
            f"{doc_count} small docs, filter query: Python {py_ms:.3f}ms, Rust {rust_ms:.3f}ms - {winner}"
        )

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
Key finding: Data structure COMPLEXITY determines performance, not just size.

When Rust wins:
  - Simple flat data (few fields per record) with complex queries
  - Batch operations on many small documents

When Python wins:
  - Nested/complex data structures (objects within objects, arrays)
  - Simple queries on any data structure
  - Large documents with many fields (even if query only touches a few)

Why? The entire data structure must be converted from Python to Rust
before any query runs - even fields the query doesn't touch.
""")


if __name__ == "__main__":
    main()
