# c2fc — C++ → блок-схема

Конвертер исходного кода на C++ в блок-схемы (SVG или draw.io) с GUI на PyQt6.
Парсинг — tree-sitter (tree-sitter-cpp). Поддерживаемое подмножество C++:
переменные, присваивания, `if/else`, `while`, `do…while`, `for`,
`switch/case/default`, `break/continue/return`, функции, методы
структур/классов (каждый метод с телом — отдельная подпрограмма, его
вызов — блок «предопределённый процесс»), `cin/cout`, `scanf/printf`.

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

На Linux, если на машине есть системный Qt (например, Ubuntu `qt6-base`) и возникает
ошибка `undefined symbol ... Qt_6_PRIVATE_API`, используйте вместо этого:

```bash
./gui_main.sh
```

(Скрипт автоматически добавляет PyQt6's Qt6/lib в `LD_LIBRARY_PATH` перед запуском Python.
На Windows и macOS проблема не возникает.)

CLI (генерация SVG из файла):

```bash
python main.py examples/demo.cpp -o demo.svg
```

Экспорт в draw.io (diagrams.net) — формат выбирается по расширению
`-o` (`.drawio` / `.xml`) или флагом `-f drawio`:

```bash
python main.py examples/complex.cpp -o complex.drawio
python main.py examples/complex.cpp -f drawio   # -> examples/complex.drawio
```

Каждая функция — отдельная страница; блоки — штатные фигуры draw.io,
линии привязаны к блокам и сохраняют маршрут раскладки. В GUI —
кнопка «Сохранить draw.io…».

## Тесты

```bash
pytest
```

## Сборка бинарников (PyInstaller)

Зависимости фиксированы в `requirements.txt`; **PyQt6 держим на ветке 6.9.x**
(`PyQt6==6.9.1` + `PyQt6-Qt6==6.9.2`). Причина: начиная с Qt 6.10 Windows-сборка
`Qt6Core.dll` жёстко импортирует `icuuc.dll` — ICU-библиотеку, которую поставляет
сама Windows (System32, с 10 версии 1703+). В Wine (в т.ч. PortProton/Proton) этой
DLL нет, поэтому там `import PyQt6.QtCore` падает, а PyInstaller без возможности
импорта PyQt6 молча собирает «пустой» бандл без Qt-плагинов и без `pkgutil` — .exe
завершается с `ModuleNotFoundError: No module named 'pkgutil'`. Qt 6.9.2 ICU не
требует вовсе.

Linux:

```bash
pyinstaller c2fc.spec
# результат: dist/linux/c2fc-gui
```

Windows (сборка под wine на Linux-машине):

```bash
# префикс создаётся однократно; wine32:i386 обязателен даже для win64-префикса
sudo apt-get install wine32:i386

# установка Python (если python-installer.exe ещё не скачан — скачать
# python-3.14.6-amd64.exe с python.org и сохранить как python-installer.exe;
# Wine 9.0 из Ubuntu 24.04 не реализует KERNEL32!CopyFile2, поэтому установщик
# падает в конце, но Python и App Paths уже прописаны — это нормально)
WINEPREFIX=$HOME/.wine-c2fc WINEARCH=win64 wine python-installer.exe /quiet InstallAllUsers=0 PrependPath=1

# pip в Wine-Python: ensurepip падает на CopyFile2 (см. выше), поэтому — get-pip.py
curl -sL -o get-pip.py https://bootstrap.pypa.io/get-pip.py
WINEPREFIX=$HOME/.wine-c2fc wine python get-pip.py
rm get-pip.py

# зависимости и сборка (wine требует pty — без stdin Python падает с WinError 6,
# поэтому запускаем через script -qec)
script -qec 'env WINEPREFIX=$HOME/.wine-c2fc wine python -m pip install -r requirements.txt --no-input' /dev/null
script -qec 'env WINEPREFIX=$HOME/.wine-c2fc wine python -m PyInstaller c2fc.spec --distpath dist/win --noconfirm' /dev/null
# результат: dist/win/c2fc-gui.exe
```

Проверка перед запуском на Windows/Wine (сборка должна пройти без предупреждения
`failed to obtain Qt library info`):

```bash
# PyQt6 импортируется в сборочном окружении (иначе spec теперь падает сам)
script -qec 'env WINEPREFIX=$HOME/.wine-c2fc wine python -c "import PyQt6.QtCore; print(PyQt6.QtCore.QT_VERSION_STR)"' /dev/null

# в бандле обязаны быть pkgutil, runtime-hook pyi_rth_pkgutil и Qt-плагины
grep -c "'pkgutil'" build/c2fc/Analysis-00.toc        # > 0
grep -c pyi_rth_pkgutil build/c2fc/EXE-00.toc         # > 0
grep -c 'qwindows.dll' build/c2fc/EXE-00.toc         # > 0
grep -c 'icuuc' build/c2fc/EXE-00.toc                 # 0
```

Если `platforms/qwindows.dll` в бандл не попал, приложение на Windows/Wine
завершится с «could not find or load the Qt platform plugin "windows"» — значит
сборка шла с Qt >= 6.10 (см. выше) либо PyQt6 не импортировался в окружении сборки.

## Структура

```
flowchart/
  parser.py    # tree-sitter: C++ -> AST
  nodes.py     # AST-узлы
  graph.py     # AST -> топологический граф блок-схемы
  layout.py    # геометрия: размеры, колонки, маршрутизация рёбер
  svg.py       # рендер в SVG
  drawio.py    # экспорт в draw.io (mxfile XML)
  convert.py   # пайплайн source -> layout / SVG
gui.py         # PyQt6-интерфейс
main.py        # CLI
tests/         # pytest
examples/      # примеры .cpp
```
