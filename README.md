# c2fc — C++ → блок-схема

Конвертер исходного кода на C++ в блок-схемы (SVG) с GUI на PyQt6.
Парсинг — tree-sitter (tree-sitter-cpp). Поддерживаемое подмножество C++:
переменные, присваивания, `if/else`, `while`, `do…while`, `for`,
`switch/case/default`, `break/continue/return`, функции,
`cin/cout`, `scanf/printf`.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python — 3.14.6 (задан через pyenv, см. `.python-version`).

## Запуск

GUI:

```bash
python gui.py
```

CLI (генерация SVG из файла):

```bash
python main.py examples/demo.cpp -o demo.svg
```

Если на машине есть системный Qt (например, Ubuntu qt6-base) и PyQt6
выдаёт ошибку `undefined symbol ... Qt_6_PRIVATE_API`, добавьте в путь
библиотеки Qt из колёсиков PyQt6:

```bash
export LD_LIBRARY_PATH="$PWD/.venv/lib/python3.14/site-packages/PyQt6/Qt6/lib:$LD_LIBRARY_PATH"
```

## Тесты

```bash
pytest
```

## Сборка бинарников (PyInstaller)

Linux:

```bash
pyinstaller c2fc.spec
# результат: dist/linux/c2fc-gui
```

Windows (сборка под wine на Linux-машине):

```bash
WINEPREFIX=$HOME/.wine-c2fc WINEARCH=win64 wine64 python-installer.exe /quiet InstallAllUsers=0 PrependPath=1
# затем в wine-окружении:
WINEPREFIX=$HOME/.wine-c2fc wine64 python -m pip install -r requirements.txt
WINEPREFIX=$HOME/.wine-c2fc wine64 python -m PyInstaller c2fc.spec --distpath dist/win
```

## Структура

```
flowchart/
  parser.py    # tree-sitter: C++ -> AST
  nodes.py     # AST-узлы
  graph.py     # AST -> топологический граф блок-схемы
  layout.py    # геометрия: размеры, колонки, маршрутизация рёбер
  svg.py       # рендер в SVG
  convert.py   # пайплайн source -> layout / SVG
gui.py         # PyQt6-интерфейс
main.py        # CLI
tests/         # pytest
examples/      # примеры .cpp
```
