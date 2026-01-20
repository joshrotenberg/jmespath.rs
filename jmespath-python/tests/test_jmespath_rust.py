"""Tests for jmespath-rust Python bindings."""

import json

import pytest
from jmespath_rust import Expression, compile, search, search_json


class TestSearch:
    """Tests for the search() function."""

    def test_simple_field_access(self):
        assert search("foo", {"foo": "bar"}) == "bar"

    def test_nested_field_access(self):
        assert search("foo.bar", {"foo": {"bar": "baz"}}) == "baz"

    def test_array_index(self):
        assert search("[0]", ["a", "b", "c"]) == "a"

    def test_array_wildcard(self):
        data = {"people": [{"name": "Alice"}, {"name": "Bob"}]}
        assert search("people[*].name", data) == ["Alice", "Bob"]

    def test_filter_expression(self):
        data = {"items": [{"x": 1}, {"x": 2}, {"x": 3}]}
        assert search("items[?x > `1`].x", data) == [2, 3]

    def test_projection(self):
        data = {"a": 1, "b": 2}
        assert search("{first: a, second: b}", data) == {"first": 1, "second": 2}

    def test_pipe_expression(self):
        data = {"items": [1, 2, 3, 4, 5]}
        assert search("items | [0]", data) == 1

    def test_builtin_functions(self):
        assert search("length(@)", [1, 2, 3]) == 3
        assert search("sort(@)", [3, 1, 2]) == [1, 2, 3]
        assert search("reverse(@)", [1, 2, 3]) == [3, 2, 1]

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="Invalid JMESPath"):
            search("[invalid", {})


class TestSearchJson:
    """Tests for the search_json() function."""

    def test_basic_json_search(self):
        json_str = '{"foo": "bar"}'
        assert search_json("foo", json_str) == "bar"

    def test_complex_json_search(self):
        data = {"people": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}
        json_str = json.dumps(data)
        assert search_json("people[?age > `26`].name", json_str) == ["Alice"]

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            search_json("foo", "not valid json")


class TestCompile:
    """Tests for the compile() function."""

    def test_compile_returns_expression(self):
        expr = compile("foo.bar")
        assert isinstance(expr, Expression)

    def test_compiled_search(self):
        expr = compile("foo.bar")
        assert expr.search({"foo": {"bar": "baz"}}) == "baz"

    def test_compiled_reuse(self):
        expr = compile("x")
        assert expr.search({"x": 1}) == 1
        assert expr.search({"x": 2}) == 2
        assert expr.search({"x": 3}) == 3

    def test_invalid_expression(self):
        with pytest.raises(ValueError, match="Invalid JMESPath"):
            compile("[[[")


class TestExpression:
    """Tests for the Expression class."""

    def test_expression_property(self):
        expr = Expression("foo.bar")
        assert expr.expression == "foo.bar"

    def test_repr(self):
        expr = Expression("foo")
        assert repr(expr) == "Expression('foo')"

    def test_str(self):
        expr = Expression("foo.bar")
        assert str(expr) == "foo.bar"

    def test_search_json(self):
        expr = Expression("items[*].id")
        json_str = '{"items": [{"id": 1}, {"id": 2}]}'
        assert expr.search_json(json_str) == [1, 2]

    def test_search_many(self):
        expr = Expression("value")
        data_list = [{"value": 1}, {"value": 2}, {"value": 3}]
        assert expr.search_many(data_list) == [1, 2, 3]

    def test_search_many_json(self):
        expr = Expression("x")
        json_strings = ['{"x": 1}', '{"x": 2}', '{"x": 3}']
        assert expr.search_many_json(json_strings) == [1, 2, 3]


class TestTypeConversions:
    """Tests for Python<->Rust type conversions."""

    def test_null(self):
        assert search("a", {"a": None}) is None

    def test_boolean_true(self):
        result = search("a", {"a": True})
        assert result is True
        assert isinstance(result, bool)

    def test_boolean_false(self):
        result = search("a", {"a": False})
        assert result is False
        assert isinstance(result, bool)

    def test_integer(self):
        result = search("a", {"a": 42})
        assert result == 42
        assert isinstance(result, int)

    def test_negative_integer(self):
        result = search("a", {"a": -42})
        assert result == -42

    def test_float(self):
        result = search("a", {"a": 3.14})
        assert result == 3.14
        assert isinstance(result, float)

    def test_string(self):
        result = search("a", {"a": "hello"})
        assert result == "hello"
        assert isinstance(result, str)

    def test_empty_string(self):
        assert search("a", {"a": ""}) == ""

    def test_array(self):
        result = search("a", {"a": [1, 2, 3]})
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_empty_array(self):
        assert search("a", {"a": []}) == []

    def test_object(self):
        result = search("a", {"a": {"b": "c"}})
        assert result == {"b": "c"}
        assert isinstance(result, dict)

    def test_empty_object(self):
        assert search("a", {"a": {}}) == {}

    def test_nested_structure(self):
        data = {
            "items": [
                {"name": "Alice", "scores": [95, 87, 92]},
                {"name": "Bob", "scores": [78, 85, 90]},
            ]
        }
        result = search("items[0].scores", data)
        assert result == [95, 87, 92]

    def test_mixed_types_in_array(self):
        data = {"a": [1, "two", True, None, {"x": 1}]}
        result = search("a", data)
        assert result == [1, "two", True, None, {"x": 1}]


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_missing_field_returns_none(self):
        assert search("missing", {"foo": "bar"}) is None

    def test_unicode_strings(self):
        data = {"name": "hello"}
        assert search("name", data) == "hello"

    def test_large_integer(self):
        big_num = 2**53
        assert search("a", {"a": big_num}) == big_num

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        assert search("a.b.c.d.e", data) == "deep"

    def test_special_characters_in_string(self):
        data = {"msg": 'hello "world"\nand\ttabs'}
        assert search("msg", data) == 'hello "world"\nand\ttabs'
