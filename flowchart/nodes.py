"""Shared AST definitions for the C++ subset used by the converter."""


from __future__ import annotations

from dataclasses import dataclass, field


class Node:
    line: int = 0


@dataclass
class VarDecl(Node):
    type: str
    name: str
    init: str | None = None
    line: int = 0


@dataclass
class Assign(Node):
    target: str
    op: str  # = += -= *= /= %= etc.
    value: str
    line: int = 0


@dataclass
class ExprStmt(Node):
    text: str
    line: int = 0


@dataclass
class Call(Node):
    name: str
    args: str = ""
    line: int = 0


@dataclass
class Input(Node):
    items: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class Output(Node):
    items: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class If(Node):
    # list of (condition, body); else_body is the final "else" block (or None)
    branches: list[tuple[str, list]] = field(default_factory=list)
    else_body: list | None = None
    line: int = 0


@dataclass
class While(Node):
    cond: str = ""
    body: list = field(default_factory=list)
    line: int = 0


@dataclass
class DoWhile(Node):
    body: list = field(default_factory=list)
    cond: str = ""
    line: int = 0


@dataclass
class For(Node):
    init: str = ""
    cond: str = ""
    step: str = ""
    body: list = field(default_factory=list)
    line: int = 0


@dataclass
class Switch(Node):
    expr: str = ""
    # each case: (list of case values (None = default), body)
    cases: list[tuple[list[str] | None, list]] = field(default_factory=list)
    line: int = 0


@dataclass
class Break(Node):
    line: int = 0


@dataclass
class Continue(Node):
    line: int = 0


@dataclass
class Return(Node):
    value: str | None = None
    line: int = 0


@dataclass
class FuncDef(Node):
    name: str = ""
    ret: str = "void"
    params: str = ""
    body: list = field(default_factory=list)
    line: int = 0


@dataclass
class Program(Node):
    funcs: list[FuncDef] = field(default_factory=list)
