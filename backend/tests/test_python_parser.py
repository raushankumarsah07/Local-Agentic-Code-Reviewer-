"""
Unit tests for the Python AST Parser (app/parsing/python_parser.py).
Tests extraction of functions, classes, inheritance, imports, calls, decorators,
and verifies syntax errors are marked as unparsable without crashing.
"""

from pathlib import Path
from app.parsing.python_parser import PythonParser


def test_parse_10_line_handcrafted_code():
    """
    Test parsing a clean handcrafted 10-line Python file.
    Verifies classes, bases, methods, parameters, return types, and calls.
    """
    code = (
        "import os\n"
        "from typing import List\n"
        "\n"
        "class Animal:\n"
        "    pass\n"
        "\n"
        "class Dog(Animal):\n"
        "    \"\"\"A dog class.\"\"\"\n"
        "    def bark(self, times: int = 1) -> str:\n"
        "        print('Woof!')\n"
        "        return 'Woof'\n"
    )

    parser = PythonParser()
    parsed = parser.parse_code(code, file_path="dog.py")

    assert parsed.is_parsable is True
    assert parsed.error_message is None

    # Check Imports
    assert len(parsed.imports) == 2
    assert parsed.imports[0].module == "os"
    assert parsed.imports[1].module == "typing"
    assert parsed.imports[1].imported_name == "List"

    # Check Classes and Inheritance
    assert len(parsed.classes) == 2
    animal_cls = parsed.classes[0]
    assert animal_cls.name == "Animal"
    assert animal_cls.bases == []

    dog_cls = parsed.classes[1]
    assert dog_cls.name == "Dog"
    assert dog_cls.bases == ["Animal"]
    assert dog_cls.has_docstring is True
    assert dog_cls.docstring == "A dog class."

    # Check Methods inside Dog
    assert len(dog_cls.methods) == 1
    bark_method = dog_cls.methods[0]
    assert bark_method.name == "bark"
    assert bark_method.is_method is True
    assert bark_method.class_name == "Dog"
    assert "self" in bark_method.params[0]
    assert "times: int" in bark_method.params[1]
    assert bark_method.return_type == "str"
    assert bark_method.calls == ["print"]


def test_parse_imports_absolute_and_relative():
    """
    Test extraction of absolute imports, aliases, and relative imports (levels 1 and 2).
    """
    code = (
        "import math\n"
        "import numpy as np\n"
        "from utils.helpers import validate_number\n"
        "from .local_mod import local_func\n"
        "from ..parent_pkg import ParentService\n"
        "from . import sibling\n"
    )

    parser = PythonParser()
    parsed = parser.parse_code(code, file_path="imports_test.py")

    assert parsed.is_parsable is True
    assert len(parsed.imports) == 6

    # 1. import math
    assert parsed.imports[0].module == "math"
    assert parsed.imports[0].is_relative is False
    assert parsed.imports[0].level == 0

    # 2. import numpy as np
    assert parsed.imports[1].module == "numpy"
    assert parsed.imports[1].alias == "np"

    # 3. from utils.helpers import validate_number
    assert parsed.imports[2].module == "utils.helpers"
    assert parsed.imports[2].imported_name == "validate_number"
    assert parsed.imports[2].is_relative is False

    # 4. from .local_mod import local_func
    assert parsed.imports[3].module == "local_mod"
    assert parsed.imports[3].imported_name == "local_func"
    assert parsed.imports[3].is_relative is True
    assert parsed.imports[3].level == 1

    # 5. from ..parent_pkg import ParentService
    assert parsed.imports[4].module == "parent_pkg"
    assert parsed.imports[4].imported_name == "ParentService"
    assert parsed.imports[4].is_relative is True
    assert parsed.imports[4].level == 2

    # 6. from . import sibling
    assert parsed.imports[5].module is None
    assert parsed.imports[5].imported_name == "sibling"
    assert parsed.imports[5].is_relative is True
    assert parsed.imports[5].level == 1


def test_deliberate_syntax_error_marked_unparsable():
    """
    Test that a file with broken syntax does not crash the parser
    and is flagged as is_parsable=False with a clear error message.
    """
    broken_code = (
        "def broken_function(\n"
        "    x = 10\n"
        "    if x > 5\n"  # Missing colon
        "        print('Broken syntax')\n"
    )

    parser = PythonParser()
    parsed = parser.parse_code(broken_code, file_path="broken.py")

    assert parsed.is_parsable is False
    assert parsed.error_message is not None
    assert "SyntaxError" in parsed.error_message
    assert "line " in parsed.error_message
    assert len(parsed.classes) == 0
    assert len(parsed.functions) == 0


def test_parse_calls_and_caller_context():
    """
    Test that function invocations accurately track caller context
    (module level vs method level vs top-level function).
    """
    code = (
        "global_setup()\n"
        "\n"
        "class Service:\n"
        "    def execute(self):\n"
        "        self.step_one()\n"
        "        helper_func()\n"
        "\n"
        "def runner():\n"
        "    s = Service()\n"
        "    s.execute()\n"
    )

    parser = PythonParser()
    parsed = parser.parse_code(code, file_path="service.py")

    assert parsed.is_parsable is True
    call_records = [(c.caller_context, c.callee) for c in parsed.calls]

    # global_setup() is called at module scope
    assert ("module", "global_setup") in call_records
    # self.step_one() inside Service.execute
    assert ("Service.execute", "self.step_one") in call_records
    # helper_func() inside Service.execute
    assert ("Service.execute", "helper_func") in call_records
    # Service() inside runner
    assert ("runner", "Service") in call_records
    # s.execute() inside runner
    assert ("runner", "s.execute") in call_records


def test_parse_empty_code():
    """Verify empty code produces valid, empty parsed structure."""
    parser = PythonParser()
    parsed = parser.parse_code("", file_path="empty.py")
    assert parsed.is_parsable is True
    assert parsed.classes == []
    assert parsed.functions == []
    assert parsed.imports == []
    assert parsed.calls == []


def test_dump_ast_utility():
    """Verify raw AST indented string dump works."""
    dump = PythonParser.dump_ast("x = 1 + 2")
    assert "Module" in dump
    assert "Assign" in dump
    assert "BinOp" in dump
