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

# Search JSON strings directly (fastest for API responses)
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

The Rust implementation has different performance characteristics compared to the pure Python `jmespath` library:

### Where Rust Excels (1.5-2x faster)

- **Complex filter expressions**: `people[?age > `50`].name`
- **Multi-step projections**: `people[*].{name: name, age: age}`
- **JSON string input**: When data is already JSON (API responses, files)
- **Batch operations**: Processing many documents with the same expression

### Where Python is Faster

- **Simple field access**: `foo.bar`, `items[0]`
- **Trivial expressions**: `length(@)`, array slicing

The performance difference is due to the overhead of converting Python objects to Rust types. When data arrives as a JSON string (common with API responses), `search_json()` avoids this overhead and is nearly 2x faster than Python's `json.loads()` + `jmespath.search()`.

### Recommendation

Use `jmespath-rust` when:
- Processing JSON API responses or file contents directly
- Running complex queries with filters, projections, or pipes
- Batch processing many documents
- The expression complexity justifies the conversion overhead

Use the pure Python `jmespath` library when:
- Data is already Python dicts/lists
- Queries are simple field access
- Minimal dependencies are preferred

## Development

```bash
# Create virtualenv and install dependencies
cd jmespath-python
python -m venv .venv
source .venv/bin/activate
pip install maturin pytest

# Build and install in development mode
maturin develop

# Run tests
pytest tests/

# Build release wheel
maturin build --release
```

## License

MIT
