# jmespath-rust

Python bindings for [jmespath.rs](https://github.com/jmespath/jmespath.rs) - a Rust implementation of JMESPath.

## Installation

```bash
pip install jmespath-rust
```

## Usage

```python
from jmespath_rust import search, compile, search_json

# One-shot search
result = search("foo.bar", {"foo": {"bar": "baz"}})
print(result)  # "baz"

# Compile for repeated use (more efficient)
expr = compile("people[*].name")
data = {"people": [{"name": "Alice"}, {"name": "Bob"}]}
result = expr.search(data)
print(result)  # ["Alice", "Bob"]

# Search JSON strings directly
json_data = '{"items": [{"id": 1}, {"id": 2}]}'
result = search_json("items[*].id", json_data)
print(result)  # [1, 2]
```

## API

### Functions

- `search(expression: str, data: Any) -> Any` - Search data with a JMESPath expression
- `search_json(expression: str, json_str: str) -> Any` - Search a JSON string directly
- `compile(expression: str) -> Expression` - Compile an expression for repeated use

### Expression Class

- `Expression(expression: str)` - Create a compiled expression
- `search(data: Any) -> Any` - Search Python data
- `search_json(json_str: str) -> Any` - Search a JSON string
- `search_many(data_list: list) -> list` - Batch search multiple items
- `search_many_json(json_strings: list[str]) -> list` - Batch search JSON strings
- `expression` - Property returning the original expression string

## Performance Characteristics

The Rust bindings have nuanced performance characteristics due to Python/Rust FFI overhead.

### The Key Factor: Data Structure Complexity

The conversion overhead scales with **data complexity**, not just record count:

| Data Type | Complex Query | Winner |
|-----------|---------------|--------|
| Simple (3 fields/record) | `people[?age > 50].name` | **Rust 1.7x faster** |
| Nested (with arrays, objects) | Same query | **Python 2x faster** |

This is because the entire data structure must be converted from Python to Rust before any query runs - even fields the query doesn't touch.

### When Rust Wins

1. **Simple, flat data structures** with complex queries (filters, projections, sorts)
2. **Batch operations** on many small documents - amortizes FFI overhead
3. **Data originating as JSON strings** - avoids Python object conversion

### When Python Wins

1. **Nested/complex data structures** - conversion overhead dominates
2. **Simple queries** on any data - Python operates directly on dicts
3. **Large documents** with deeply nested fields

### Benchmark Summary (1000 records)

```
Simple data (3 fields per record):
  Filter query: Rust 1.7x faster

Complex data (nested objects + arrays):  
  Filter query: Python 2x faster

Batch ops (1000 small docs):
  Rust 1.6-2.2x faster
```

## Development

```bash
# Create virtualenv and install dependencies
cd jmespath-python
python -m venv .venv
source .venv/bin/activate
pip install maturin pytest

# Build and install in development mode
maturin develop --release

# Run tests
pytest tests/

# Run benchmarks
pip install jmespath
python benchmarks/benchmark.py
```

## License

MIT
