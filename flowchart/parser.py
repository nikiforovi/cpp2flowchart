"""C++ -> AST converter built on tree-sitter (tree-sitter-cpp)."""

from __future__ import annotations

import re

from tree_sitter import Language, Node, Parser

import tree_sitter_cpp

from . import nodes as N

_LANGUAGE = Language(tree_sitter_cpp.language())

_IO_CALLS = {
    "printf": "output", "puts": "output", "putchar": "output",
    "fprintf": "output", "scanf": "input", "fscanf": "input",
}


class ParseError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(message)
        self.line = line


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class Converter:
    def __init__(self, source: str):
        self.src = source.encode("utf-8")

    def text(self, node: Node | None) -> str:
        if node is None:
            return ""
        return _clean_text(
            self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")
        )

    # ---- program ----------------------------------------------------------
    def program(self, root: Node) -> N.Program:
        funcs: list[N.FuncDef] = []
        self._collect_functions(root, funcs)
        return N.Program(funcs=funcs)

    def _collect_functions(self, node: Node, out: list[N.FuncDef]) -> None:
        for child in node.named_children:
            if child.type == "function_definition":
                fn = self.function(child)
                if fn is not None:
                    out.append(fn)
            elif child.type in ("namespace_definition", "linkage_specification"):
                self._collect_functions(
                    child.child_by_field_name("body") or child, out
                )
    def statement(self, node: Node):
        t = node.type
        line = node.start_point[0] + 1

        if t == "compound_statement":
            return self.block(node)
        if t == "expression_statement":
            return self.expression_statement(node)
        if t == "declaration":
            return self.declaration(node)
        if t == "if_statement":
            return self.if_statement(node, line)
        if t == "while_statement":
            body = node.child_by_field_name("body")
            return N.While(
                cond=self.condition_text(node.child_by_field_name("condition")),
                body=self._as_list(self.statement(body)),
                line=line,
            )
        if t == "do_statement":
            body = node.child_by_field_name("body")
            cond = node.child_by_field_name("condition")
            return N.DoWhile(
                body=self._as_list(self.statement(body)),
                cond=self.condition_text(cond),
                line=line,
            )
        if t == "for_statement":
            init_n = node.child_by_field_name("initializer")
            cond_n = node.child_by_field_name("condition")
            upd_n = node.child_by_field_name("update")
            body_n = node.child_by_field_name("body")
            init = ""
            if init_n is not None:
                if init_n.type == "declaration":
                    parts = []
                    type_t = self.text(init_n.child_by_field_name("type"))
                    for d in init_n.named_children:
                        if d.type == "init_declarator":
                            decl = d.child_by_field_name("declarator")
                            val = d.child_by_field_name("value")
                            s = (type_t + " " if type_t else "") + self.text(decl)
                            if val is not None:
                                s += " = " + self.text(val)
                            parts.append(s)
                    init = ", ".join(parts)
                else:
                    init = self.text(init_n)
            return N.For(
                init=init,
                cond=self.condition_text(cond_n),
                step=self.text(upd_n),
                body=self._as_list(self.statement(body_n)),
                line=line,
            )
        if t == "switch_statement":
            cond = node.child_by_field_name("condition")
            body_n = node.child_by_field_name("body")
            cases: list[tuple[list[str] | None, list]] = []
            if body_n is not None:
                for child in body_n.named_children:
                    if child.type == "case_statement":
                        val_n = child.child_by_field_name("value")
                        labels = None if val_n is None else [self.text(val_n)]
                        stmts: list = []
                        for sub in child.named_children:
                            if sub is val_n:
                                continue
                            self._append(stmts, self.statement(sub))
                        cases.append((labels, stmts))
                    elif cases:
                        self._append(cases[-1][1], self.statement(child))
            return N.Switch(
                expr=self.condition_text(cond), cases=cases, line=line
            )
        if t == "return_statement":
            v = node.child_by_field_name("value")
            if v is None and node.named_children:
                v = node.named_children[0]
            return N.Return(self.text(v) or None, line)
        if t == "break_statement":
            return N.Break(line)
        if t == "continue_statement":
            return N.Continue(line)
        if t == "labeled_statement":
            if node.named_children:
                return self.statement(node.named_children[-1])
            return None
        if t.startswith("preproc_"):
            return self._preproc_body(node)
        if t in (
            "using_declaration", "alias_declaration", "type_definition",
            "namespace_definition", "namespace_alias_definition",
            "class_specifier", "struct_specifier", "enum_specifier",
            "template_declaration", "access_specifier",
            "static_assert_declaration", "linkage_specification",
            "declaration_list",
            "ERROR",
        ):
            return None
        if t in ("try_statement", "throw_statement", "goto_statement"):
            raise ParseError(
                f"неподдерживаемая конструкция: {t.replace('_', ' ')}",
                line,
            )
        if t.endswith("_expression"):
            return N.ExprStmt(self.text(node), line)
        return None

    def _preproc_body(self, node: Node):
        first = node.child(0)
        if first is not None and first.type in (
            "preproc_include", "preproc_def", "preproc_function_def",
            "preproc_call",
        ):
            return None
        results: list = []
        for child in node.named_children:
            if child.type.startswith("preproc_"):
                sub = self._preproc_body(child)
                if sub:
                    results.extend(sub)
            else:
                self._append(results, self.statement(child))
        return results or None


    def function(self, node: Node) -> N.FuncDef | None:
        ret = self.text(node.child_by_field_name("type"))
        decl = node.child_by_field_name("declarator")
        name = ""
        params = ""
        d = decl
        while d is not None:
            if d.type == "function_declarator":
                p = d.child_by_field_name("parameters")
                if p is not None:
                    params = self.text(p).strip()[1:-1]
                d = d.child_by_field_name("declarator")
            elif d.type in (
                "pointer_declarator", "reference_declarator",
                "array_declarator", "attributed_declarator",
                "parenthesized_declarator", "template_function",
            ):
                d = d.child_by_field_name("declarator") or (
                    d.named_children[0] if d.named_children else None
                )
            elif d.type == "qualified_identifier":
                nm = d.child_by_field_name("name")
                name = self.text(nm) or self.text(d).split("::")[-1]
                break
            elif d.type == "identifier":
                name = self.text(d)
                break
            else:
                name = self.text(d)
                break
        if not name:
            return None
        body_node = node.child_by_field_name("body")
        body = self.block(body_node) if body_node is not None else []
        return N.FuncDef(
            name=name, ret=ret or "void", params=params, body=body,
            line=node.start_point[0] + 1,
        )

    # ---- statements --------------------------------------------------------
    def block(self, node: Node) -> list:
        body: list = []
        for child in node.named_children:
            self._append(body, self.statement(child))
        return body

    def _append(self, body: list, stmt) -> None:
        if stmt is None:
            return
        if isinstance(stmt, list):
            body.extend(stmt)
        else:
            body.append(stmt)

    @staticmethod
    def _as_list(stmt) -> list:
        if stmt is None:
            return []
        if isinstance(stmt, list):
            return stmt
        return [stmt]

    # ---- helpers ------------------------------------------------------------
    def condition_text(self, node: Node | None) -> str:
        if node is None:
            return ""
        if node.type == "condition_clause":
            v = node.child_by_field_name("value")
            return self.text(v) if v is not None else self.text(node)
        if node.type == "parenthesized_expression":
            t = self.text(node)
            return t[1:-1] if t.startswith("(") and t.endswith(")") else t
        return self.text(node)

    def if_statement(self, node: Node, line: int) -> N.If:
        cond = self.condition_text(node.child_by_field_name("condition"))
        cons = node.child_by_field_name("consequence")
        branches: list[tuple[str, list]] = [
            (cond, self._as_list(self.statement(cons)))
        ]
        else_body: list | None = None
        alt = node.child_by_field_name("alternative")
        while alt is not None:
            if alt.type == "else_clause":
                inner = alt.named_children[0] if alt.named_children else None
                if inner is not None and inner.type == "if_statement":
                    # else if -> chain it as another branch
                    c = self.condition_text(inner.child_by_field_name("condition"))
                    cons2 = inner.child_by_field_name("consequence")
                    branches.append((c, self._as_list(self.statement(cons2))))
                    alt = inner.child_by_field_name("alternative")
                    continue
                else_body = (
                    self._as_list(self.statement(inner))
                    if inner is not None else None
                )
                break
            break
        return N.If(branches=branches, else_body=else_body, line=line)

    # ---- declarations & expressions ------------------------------------------
    def declaration(self, node: Node) -> list:
        line = node.start_point[0] + 1
        type_n = node.child_by_field_name("type")
        type_text = self.text(type_n)
        out: list = []
        for d in node.named_children:
            if d.type == "init_declarator":
                decl = d.child_by_field_name("declarator")
                val = d.child_by_field_name("value")
                name = self.text(decl)
                init = self.text(val) if val is not None else None
                out.append(N.VarDecl(type_text, name, init, line))
            elif d.type in ("identifier", "array_declarator",
                            "pointer_declarator", "reference_declarator"):
                # plain declaration without initializer: int n;
                out.append(N.VarDecl(type_text, self.text(d), None, line))
        return out

    def expression_statement(self, node: Node) -> list:
        line = node.start_point[0] + 1
        if not node.named_children:
            return []
        expr = node.named_children[0]
        io = self._stream_expression(expr)
        if io is not None:
            return [io]
        out: list = []
        for part in self._split_comma(expr):
            out.append(self._simple_expression(part, line))
        return out

    def _split_comma(self, node: Node) -> list[Node]:
        if node.type == "comma_expression":
            return self._split_comma(node.child_by_field_name("left")) + \
                self._split_comma(node.child_by_field_name("right"))
        return [node]

    def _simple_expression(self, node: Node, line: int):
        t = node.type
        if t == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            op = "="
            for c in node.children:
                if not c.is_named and c.type not in ("(", ")"):
                    op = c.text.decode() if c.text else "="
                    break
            return N.Assign(self.text(left), op, self.text(right), line)
        if t == "call_expression":
            return self._call_node(node, line)
        if t == "update_expression":
            return N.ExprStmt(self.text(node), line)
        return N.ExprStmt(self.text(node), line)

    def _call_node(self, node: Node, line: int):
        fn = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        fn_text = self.text(fn)
        base = fn_text.split("::")[-1].split(".")[-1].split("->")[-1]
        arg_text = self.text(args).strip()[1:-1] if args is not None else ""
        kind = _IO_CALLS.get(base)
        if kind == "output":
            items = [p for p in self._split_args(arg_text)]
            return N.Output(items, line)
        if kind == "input":
            return N.Input(self._split_args(arg_text), line)
        return N.Call(base, arg_text, line)

    @staticmethod
    def _split_args(text: str) -> list[str]:
        parts: list[str] = []
        depth = 0
        cur = ""
        in_str: str | None = None
        for ch in text:
            if in_str:
                cur += ch
                if ch == in_str and (len(cur) < 2 or cur[-2] != "\\"):
                    in_str = None
                continue
            if ch in "\"'":
                in_str = ch
                cur += ch
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur.strip())
        return parts

    # ---- cin / cout -----------------------------------------------------------
    def _stream_expression(self, node: Node):
        """Detect `cin >> ...` / `cout << ...` chains at statement level."""
        if node.type != "binary_expression":
            return None
        root = node
        while root.type == "binary_expression":
            left = root.child_by_field_name("left")
            op = self._binop(root)
            if left is None or op not in ("<<", ">>"):
                return None
            root = left
        root_text = self.text(root)
        if not root_text:
            return None
        base = root_text.split("::")[-1]
        if base not in ("cin", "cout"):
            return None
        items = self._flatten_stream(node, None)
        if items and items[0].split("::")[-1] in ("cin", "cout"):
            items = items[1:]
        line = node.start_point[0] + 1
        if base == "cin":
            return N.Input([i for i in items if i], line)
        filtered = [i for i in items if i and i not in ("endl", "std::endl")]
        return N.Output(filtered, line)

    def _flatten_stream(self, node: Node, op: str | None) -> list[str]:
        if node.type == "binary_expression":
            cur_op = self._binop(node)
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if cur_op in ("<<", ">>") and left is not None and right is not None:
                items = self._flatten_stream(left, cur_op)
                rtext = self.text(right)
                if op == ">>":
                    # right-associative input: recurse right first
                    return items + self._flatten_stream(right, cur_op) + []
                items.append(rtext)
                return items
        return [self.text(node)]

    def _binop(self, node: Node) -> str:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None:
            return ""
        between = self.src[left.end_byte:right.start_byte].decode(
            "utf-8", "replace"
        )
        return between.strip()


# ---- module-level API ---------------------------------------------------------
def parse_cpp(source: str) -> N.Program:
    """Parse C++ source into a Program AST; raise ParseError on syntax errors."""
    parser = Parser(_LANGUAGE)
    tree = parser.parse(source.encode("utf-8"))
    root = tree.root_node
    if root.has_error:
        err = _find_error(root)
        if err is not None:
            line = err.start_point[0] + 1
            text = source.splitlines()[line - 1].strip() if source else ""
            raise ParseError(
                f"ошибка синтаксиса: {text or err.type}", line
            )
        raise ParseError("ошибка синтаксиса", 0)
    return Converter(source).program(root)


def _find_error(node: Node) -> Node | None:
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        found = _find_error(child)
        if found is not None:
            return found
    return None


