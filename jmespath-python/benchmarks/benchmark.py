"""Benchmark comparing jmespath-rust to native Python jmespath."""

import json
import time

import jmespath as jmespath_py
import jmespath_rust


def make_data(size):
    """Generate test data with nested structures."""
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


def benchmark(func, iterations=1000):
    """Benchmark a function and return elapsed time."""
    # Warmup
    for _ in range(10):
        func()

    start = time.perf_counter()
    for _ in range(iterations):
        func()
    return time.perf_counter() - start


def main():
    # Simple to complex expressions
    expressions = [
        # Simple
        ("Simple: field access", "people[0].name"),
        ("Simple: array slice", "people[0:5]"),
        ("Simple: length", "length(people)"),
        # Medium
        ("Medium: wildcard project", "people[*].name"),
        ("Medium: nested access", "people[*].metadata.tags"),
        ("Medium: multi-select", "people[*].{n: name, a: age}"),
        # Complex
        ("Complex: filter", "people[?age > `50`].name"),
        ("Complex: filter + nested", "people[?metadata.active].name"),
        ("Complex: filter + sort", "sort_by(people, &age)[*].name"),
        # Very complex
        ("Very complex: chained", "people[?age > `30`] | [?metadata.active] | [0:5].name"),
        (
            "Very complex: multi-filter",
            "people[?age > `25`][?metadata.active][?contains(metadata.tags, 'tag_1')].name",
        ),
    ]

    sizes = [100, 1000, 5000, 10000]

    print("=" * 95)
    print("JMESPath Benchmark: Python vs Rust (RELEASE BUILD)")
    print("=" * 95)

    for size in sizes:
        data = make_data(size)
        json_data = json.dumps(data)

        print(f"\n{'=' * 95}")
        print(f"Data size: {size} records")
        print("-" * 95)
        print(
            f"{'Expression':<35} {'Python (ms)':<14} {'Rust (ms)':<14} {'Rust JSON':<14} {'Winner':<12}"
        )
        print("-" * 95)

        for name, expr_str in expressions:
            py_expr = jmespath_py.compile(expr_str)
            rust_expr = jmespath_rust.compile(expr_str)

            iterations = 100

            # Benchmark Python
            py_time = benchmark(lambda e=py_expr, d=data: e.search(d), iterations)

            # Benchmark Rust (Python objects)
            rust_time = benchmark(lambda e=rust_expr, d=data: e.search(d), iterations)

            # Benchmark Rust (JSON string input)
            rust_json_time = benchmark(
                lambda e=rust_expr, d=json_data: e.search_json(d), iterations
            )

            py_ms = (py_time / iterations) * 1000
            rust_ms = (rust_time / iterations) * 1000
            rust_json_ms = (rust_json_time / iterations) * 1000

            best_rust = min(rust_ms, rust_json_ms)
            if py_ms < best_rust:
                winner = f"Python {best_rust / py_ms:.1f}x"
            else:
                winner = f"Rust {py_ms / best_rust:.1f}x"

            print(f"{name:<35} {py_ms:<14.3f} {rust_ms:<14.3f} {rust_json_ms:<14.3f} {winner:<12}")

    # Batch operations test
    print("\n" + "=" * 95)
    print("Batch Operations")
    print("=" * 95)

    for doc_count in [100, 500, 1000]:
        documents = [
            {"id": i, "value": i * 10, "name": f"item_{i}", "active": i % 2 == 0}
            for i in range(doc_count)
        ]
        json_documents = [json.dumps(d) for d in documents]

        # Test with simple and complex expressions
        for expr_name, expr_str in [
            ("simple", "value"),
            ("filter", "[?active].id"),
        ]:
            py_expr = jmespath_py.compile(expr_str)
            rust_expr = jmespath_rust.compile(expr_str)

            iterations = 50

            py_time = benchmark(lambda: [py_expr.search(d) for d in documents], iterations)
            rust_time = benchmark(lambda: [rust_expr.search(d) for d in documents], iterations)
            rust_batch_time = benchmark(lambda: rust_expr.search_many(documents), iterations)
            rust_json_batch_time = benchmark(
                lambda: rust_expr.search_many_json(json_documents), iterations
            )

            py_ms = (py_time / iterations) * 1000
            rust_ms = (rust_time / iterations) * 1000
            rust_batch_ms = (rust_batch_time / iterations) * 1000
            rust_json_ms = (rust_json_batch_time / iterations) * 1000

            print(f"\n{doc_count} docs, {expr_name} expr ({expr_str}):")
            print(f"  Python loop:      {py_ms:>8.3f} ms")
            print(f"  Rust loop:        {rust_ms:>8.3f} ms")
            print(f"  Rust batch:       {rust_batch_ms:>8.3f} ms")
            print(f"  Rust batch JSON:  {rust_json_ms:>8.3f} ms")

    # Real-world scenario: API response processing
    print("\n" + "=" * 95)
    print("Real-world Scenario: Processing JSON API Response")
    print("=" * 95)

    for size in [100, 1000, 5000]:
        api_response = json.dumps(make_data(size))

        scenarios = [
            ("Extract names", "people[*].name"),
            ("Filter active users", "people[?metadata.active].name"),
            (
                "Complex transform",
                "people[?age > `30`] | sort_by(@, &age) | [-10:].{name: name, age: age}",
            ),
        ]

        print(f"\nAPI response with {size} records:")
        print("-" * 70)

        for name, expr_str in scenarios:
            py_expr = jmespath_py.compile(expr_str)
            rust_expr = jmespath_rust.compile(expr_str)

            iterations = 100

            # Python: parse JSON then search
            def python_workflow(resp=api_response, e=py_expr):
                data = json.loads(resp)
                return e.search(data)

            # Rust: search JSON directly
            py_time = benchmark(python_workflow, iterations)
            rust_time = benchmark(lambda e=rust_expr, r=api_response: e.search_json(r), iterations)

            py_ms = (py_time / iterations) * 1000
            rust_ms = (rust_time / iterations) * 1000
            speedup = py_ms / rust_ms

            print(
                f"  {name:<25} Python: {py_ms:>7.3f}ms  Rust: {rust_ms:>7.3f}ms  ({speedup:.2f}x)"
            )


if __name__ == "__main__":
    main()
