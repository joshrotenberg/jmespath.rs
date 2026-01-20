//! Python bindings for jmespath.rs.
//!
//! Provides a fast Rust implementation of JMESPath accessible from Python.
//!
//! # Performance Characteristics
//!
//! The Rust implementation excels at:
//! - Complex filter expressions (`people[?age > `50`]`)
//! - Multi-step projections (`people[*].{n: name, a: age}`)
//! - Processing JSON string input directly (`search_json`)
//! - Batch operations on multiple documents
//!
//! For simple field access on Python dicts, the native Python jmespath
//! library may be faster due to FFI conversion overhead.

use std::collections::BTreeMap;
use std::sync::Arc;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyString};

/// Convert a jmespath Variable to a Python object.
#[allow(deprecated)] // to_object is deprecated but alternatives have borrowing issues
fn variable_to_python(py: Python<'_>, var: &jmespath::Variable) -> PyResult<PyObject> {
    use pyo3::conversion::ToPyObject;
    match var {
        jmespath::Variable::Null => Ok(py.None()),
        jmespath::Variable::Bool(b) => Ok(b.to_object(py)),
        jmespath::Variable::String(s) => Ok(s.to_object(py)),
        jmespath::Variable::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.to_object(py))
            } else if let Some(u) = n.as_u64() {
                Ok(u.to_object(py))
            } else if let Some(f) = n.as_f64() {
                Ok(f.to_object(py))
            } else {
                Err(PyValueError::new_err("Invalid number"))
            }
        }
        jmespath::Variable::Array(arr) => {
            let list = PyList::empty(py);
            for item in arr.iter() {
                list.append(variable_to_python(py, item)?)?;
            }
            Ok(list.to_object(py))
        }
        jmespath::Variable::Object(obj) => {
            let dict = PyDict::new(py);
            for (key, value) in obj.iter() {
                dict.set_item(key, variable_to_python(py, value)?)?;
            }
            Ok(dict.to_object(py))
        }
        jmespath::Variable::Expref(_) => Err(PyValueError::new_err(
            "Cannot convert expression reference to Python",
        )),
    }
}

/// Convert a Python object directly to a jmespath Variable.
fn python_to_variable(obj: &Bound<'_, PyAny>) -> PyResult<jmespath::Variable> {
    if obj.is_none() {
        return Ok(jmespath::Variable::Null);
    }

    // Check for bool before int (bool is a subclass of int in Python)
    if let Ok(b) = obj.downcast::<PyBool>() {
        return Ok(jmespath::Variable::Bool(b.is_true()));
    }

    if let Ok(i) = obj.downcast::<PyInt>() {
        if let Ok(val) = i.extract::<i64>() {
            return Ok(jmespath::Variable::Number(val.into()));
        }
        if let Ok(val) = i.extract::<u64>() {
            return Ok(jmespath::Variable::Number(val.into()));
        }
        if let Ok(val) = i.extract::<f64>() {
            return Ok(jmespath::Variable::Number(
                serde_json::Number::from_f64(val)
                    .ok_or_else(|| PyValueError::new_err("Invalid number"))?,
            ));
        }
    }

    if let Ok(f) = obj.downcast::<PyFloat>() {
        let val = f.value();
        return Ok(jmespath::Variable::Number(
            serde_json::Number::from_f64(val)
                .ok_or_else(|| PyValueError::new_err("Invalid float (NaN or Inf)"))?,
        ));
    }

    if let Ok(s) = obj.downcast::<PyString>() {
        return Ok(jmespath::Variable::String(s.to_string()));
    }

    if let Ok(list) = obj.downcast::<PyList>() {
        let mut arr = Vec::with_capacity(list.len());
        for item in list.iter() {
            arr.push(jmespath::Rcvar::new(python_to_variable(&item)?));
        }
        return Ok(jmespath::Variable::Array(arr));
    }

    if let Ok(dict) = obj.downcast::<PyDict>() {
        let mut map = BTreeMap::new();
        for (key, value) in dict.iter() {
            let key_str = key
                .extract::<String>()
                .map_err(|_| PyValueError::new_err("Dict keys must be strings"))?;
            map.insert(key_str, jmespath::Rcvar::new(python_to_variable(&value)?));
        }
        return Ok(jmespath::Variable::Object(map));
    }

    // Fallback to JSON serialization for other types
    let py = obj.py();
    let json_module = py.import("json")?;
    let json_str: String = json_module.call_method1("dumps", (obj,))?.extract()?;
    jmespath::Variable::from_json(&json_str)
        .map_err(|e| PyValueError::new_err(format!("Cannot convert to JMESPath variable: {}", e)))
}

/// A compiled JMESPath expression.
///
/// Compile an expression once and reuse it for multiple searches.
/// This is more efficient than using `search()` repeatedly with the same expression.
///
/// Example:
///     >>> from jmespath_rust import Expression
///     >>> expr = Expression("foo.bar")
///     >>> expr.search({"foo": {"bar": "baz"}})
///     'baz'
#[pyclass(name = "Expression")]
pub struct PyExpression {
    inner: Arc<jmespath::Expression<'static>>,
    expression: String,
}

#[pymethods]
impl PyExpression {
    /// Create a new compiled JMESPath expression.
    ///
    /// Args:
    ///     expression: The JMESPath expression string.
    ///
    /// Raises:
    ///     ValueError: If the expression is invalid.
    #[new]
    fn new(expression: &str) -> PyResult<Self> {
        let compiled = jmespath::compile(expression)
            .map_err(|e| PyValueError::new_err(format!("Invalid JMESPath expression: {}", e)))?;
        Ok(Self {
            inner: Arc::new(compiled),
            expression: expression.to_string(),
        })
    }

    /// Search Python data (dict/list) with this expression.
    ///
    /// Args:
    ///     data: The data to search (dict, list, or any JSON-compatible value).
    ///
    /// Returns:
    ///     The result of the JMESPath query.
    ///
    /// Raises:
    ///     ValueError: If the data cannot be converted or the search fails.
    fn search(&self, py: Python<'_>, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
        let var = python_to_variable(data)?;
        let result = self
            .inner
            .search(var)
            .map_err(|e| PyValueError::new_err(format!("Search error: {}", e)))?;
        variable_to_python(py, &result)
    }

    /// Search a JSON string with this expression.
    ///
    /// This is faster than `search()` when you have JSON string input,
    /// such as API responses or file contents.
    ///
    /// Args:
    ///     json_str: A valid JSON string.
    ///
    /// Returns:
    ///     The result of the JMESPath query.
    ///
    /// Raises:
    ///     ValueError: If the JSON is invalid or the search fails.
    fn search_json(&self, py: Python<'_>, json_str: &str) -> PyResult<PyObject> {
        let var = jmespath::Variable::from_json(json_str)
            .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;
        let result = self
            .inner
            .search(var)
            .map_err(|e| PyValueError::new_err(format!("Search error: {}", e)))?;
        variable_to_python(py, &result)
    }

    /// Search multiple data items with this expression (batch operation).
    ///
    /// More efficient than calling `search()` multiple times due to
    /// reduced Python/Rust boundary crossings.
    ///
    /// Args:
    ///     data_list: A list of data items to search.
    ///
    /// Returns:
    ///     A list of results, one for each input item.
    fn search_many(&self, py: Python<'_>, data_list: &Bound<'_, PyList>) -> PyResult<PyObject> {
        let results = PyList::empty(py);
        for item in data_list.iter() {
            let var = python_to_variable(&item)?;
            let result = self
                .inner
                .search(var)
                .map_err(|e| PyValueError::new_err(format!("Search error: {}", e)))?;
            results.append(variable_to_python(py, &result)?)?;
        }
        #[allow(deprecated)]
        Ok(pyo3::conversion::ToPyObject::to_object(&results, py))
    }

    /// Search multiple JSON strings with this expression (batch operation).
    ///
    /// Args:
    ///     json_strings: A list of JSON strings to search.
    ///
    /// Returns:
    ///     A list of results, one for each input string.
    fn search_many_json(&self, py: Python<'_>, json_strings: Vec<String>) -> PyResult<PyObject> {
        let results = PyList::empty(py);
        for json_str in &json_strings {
            let var = jmespath::Variable::from_json(json_str)
                .map_err(|e| PyValueError::new_err(format!("Invalid JSON: {}", e)))?;
            let result = self
                .inner
                .search(var)
                .map_err(|e| PyValueError::new_err(format!("Search error: {}", e)))?;
            results.append(variable_to_python(py, &result)?)?;
        }
        #[allow(deprecated)]
        Ok(pyo3::conversion::ToPyObject::to_object(&results, py))
    }

    /// Get the original expression string.
    #[getter]
    fn expression(&self) -> &str {
        &self.expression
    }

    fn __repr__(&self) -> String {
        format!("Expression('{}')", self.expression)
    }

    fn __str__(&self) -> &str {
        &self.expression
    }
}

/// Compile a JMESPath expression for repeated use.
///
/// Args:
///     expression: The JMESPath expression string.
///
/// Returns:
///     A compiled Expression object.
///
/// Raises:
///     ValueError: If the expression is invalid.
///
/// Example:
///     >>> from jmespath_rust import compile
///     >>> expr = compile("foo.bar")
///     >>> expr.search({"foo": {"bar": "baz"}})
///     'baz'
#[pyfunction]
fn compile(expression: &str) -> PyResult<PyExpression> {
    PyExpression::new(expression)
}

/// Search data with a JMESPath expression.
///
/// This is a convenience function that compiles and executes in one step.
/// For repeated searches with the same expression, use `compile()` instead.
///
/// Args:
///     expression: The JMESPath expression string.
///     data: The data to search.
///
/// Returns:
///     The result of the JMESPath query.
#[pyfunction]
fn search(py: Python<'_>, expression: &str, data: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    let expr = PyExpression::new(expression)?;
    expr.search(py, data)
}

/// Search a JSON string with a JMESPath expression.
///
/// Faster than `search()` when input is already a JSON string,
/// such as API responses or file contents.
///
/// Args:
///     expression: The JMESPath expression string.
///     json_str: A valid JSON string.
///
/// Returns:
///     The result of the JMESPath query.
#[pyfunction]
fn search_json(py: Python<'_>, expression: &str, json_str: &str) -> PyResult<PyObject> {
    let expr = PyExpression::new(expression)?;
    expr.search_json(py, json_str)
}

/// Python bindings for jmespath.rs.
#[pymodule]
fn _internal(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyExpression>()?;
    m.add_function(wrap_pyfunction!(compile, m)?)?;
    m.add_function(wrap_pyfunction!(search, m)?)?;
    m.add_function(wrap_pyfunction!(search_json, m)?)?;
    Ok(())
}
