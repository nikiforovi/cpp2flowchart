"""Parser tests (tree-sitter based)."""

import pytest

from flowchart import nodes as N
from flowchart.parser import ParseError, parse_cpp


def funcs(src):
    return parse_cpp(src).funcs


def test_simple_function():
    fs = funcs("int main() { return 0; }")
    assert len(fs) == 1
    f = fs[0]
    assert (f.ret, f.name, f.params) == ("int", "main", "")
    assert len(f.body) == 1
    assert isinstance(f.body[0], N.Return)
    assert f.body[0].value == "0"


def test_declaration_multi():
    fs = funcs("void f() { int a, b = 2; }")
    decls = fs[0].body
    assert len(decls) == 2
    assert decls[0].name == "a" and decls[0].init is None
    assert decls[1].name == "b" and decls[1].init == "2"


def test_assignment_and_call():
    fs = funcs("void f() { int x; x = g(1, 2); x += 3; }")
    body = fs[0].body
    assert isinstance(body[1], N.Assign) and body[1].op == "="
    assert isinstance(body[2], N.Assign) and body[2].op == "+="


def test_cin_cout():
    fs = funcs('void f() { int a, b; cin >> a >> b; cout << a << b; }')
    inp, out = fs[0].body[2], fs[0].body[3]
    assert isinstance(inp, N.Input) and inp.items == ["a", "b"]
    assert isinstance(out, N.Output) and out.items == ["a", "b"]


def test_cout_literals_filtered():
    fs = funcs('void f() { cout << "x=" << 42 << endl; }')
    out = fs[0].body[0]
    assert isinstance(out, N.Output)
    assert out.items == ['"x="', "42"]


def test_printf_input():
    fs = funcs('void f() { scanf("%d", &a); printf("%d", a); }')
    assert isinstance(fs[0].body[0], N.Input)
    assert isinstance(fs[0].body[1], N.Output)


def test_if_elif_else():
    src = """
    void f(int x) {
        if (x == 1) { g(); }
        else if (x == 2) { h(); }
        else { k(); }
    }
    """
    node = funcs(src)[0].body[0]
    assert isinstance(node, N.If)
    assert [c for c, _ in node.branches] == ["x == 1", "x == 2"]
    assert node.else_body is not None


def test_if_without_braces():
    fs = funcs("void f() { if (a) b = 1; else b = 2; }")
    node = fs[0].body[0]
    assert isinstance(node, N.If)
    assert len(node.branches[0][1]) == 1
    assert len(node.else_body) == 1


def test_loops():
    src = """
    void f() {
        while (a) a--;
        do { a++; } while (a < 5);
        for (int i = 0; i < 10; i++) { a += i; }
    }
    """
    body = funcs(src)[0].body
    assert isinstance(body[0], N.While) and body[0].cond == "a"
    assert isinstance(body[1], N.DoWhile) and body[1].cond == "a < 5"
    assert isinstance(body[2], N.For)
    assert (body[2].init, body[2].cond, body[2].step) == (
        "int i = 0", "i < 10", "i++"
    )


def test_switch_cases_and_default():
    src = """
    void f(int x) {
        switch (x) {
            case 1: g(); break;
            case 2:
            case 3: h(); break;
            default: k();
        }
    }
    """
    node = funcs(src)[0].body[0]
    assert isinstance(node, N.Switch)
    assert node.expr == "x"
    labels = [labels for labels, _ in node.cases]
    assert labels == [["1"], ["2"], ["3"], None]
    # case 2 has empty body, case 3 has call+break
    assert node.cases[1][1] == []
    kinds = [type(s) for s in node.cases[2][1]]
    assert kinds == [N.Call, N.Break]


def test_break_continue_return():
    fs = funcs("void f() { while (a) { if (b) break; continue; } return; }")
    loop = fs[0].body[0]
    inner = loop.body
    assert isinstance(inner[0], N.If)
    assert isinstance(inner[0].branches[0][1][0], N.Break)
    assert isinstance(inner[1], N.Continue)
    assert isinstance(fs[0].body[1], N.Return)
    assert fs[0].body[1].value is None


def test_function_params():
    fs = funcs("int add(int a, int b) { return a + b; }")
    f = fs[0]
    assert f.name == "add"
    assert f.params == "int a, int b"


def test_multiple_functions():
    fs = funcs("void a() {} int b() { return 1; }")
    assert [f.name for f in fs] == ["a", "b"]


def test_skips_preproc_and_using():
    fs = funcs("""
    #include <iostream>
    #define N 10
    using namespace std;
    int main() { return N; }
    """)
    assert len(fs) == 1
    assert fs[0].body[0].value == "N"


def test_syntax_error_reports_line():
    with pytest.raises(ParseError) as exc:
        parse_cpp("int main() {\n  int x = ;\n}")
    assert exc.value.line == 2


def test_comments_ignored():
    fs = funcs("int main() { // comment\n /* block */ return 0; }")
    assert len(fs[0].body) == 1
