# Потенциальные улучшения AST Index

Этот документ содержит список потенциальных улучшений проекта AST Index. Улучшения сгруппированы по категориям с оценкой приоритета и сложности.

---

## 1. References и Usages (поиск использований)

### 1.1 Добавить поле `confidence` (средний приоритет)

**Текущее состояние:** Все ссылки считаются равнозначными, нет информации о уверенности.

**Предложение:** Добавить числовое поле `confidence: float` (0.0-1.0) в модель `Reference`.

**Значения:**
- `1.0` — Точная ссылка (из LSP или точного анализа)
- `0.8` — Высокая уверенность (CamelCase тип с контекстом)
- `0.6` — Средняя уверенность (Вызов функции)
- `0.4` — Низкая уверенность (Общий identifier)
- `0.2` — Очень низкая (Возможный false positive)

**Пример использования:**
```python
@dataclass
class Reference:
    symbol_name: str
    symbol_file: str
    ref_file: str
    ref_line: int
    ref_col: int
    ref_kind: str
    context: Optional[str] = None
    confidence: float = 0.5  # ← Новое поле
```

**Фильтрация по уверенности:**
```bash
# Показать только ссылки с высокой уверенностью
ast-index usages "User" --min-confidence 0.8
```

**Плюсы:**
- ✅ Пользователь может контролировать точность
- ✅ Прозрачность системы (понятно насколько точны результаты)
- ✅ Возможность постепенного улучшения (начать с 0.5, добавлять точные методы → 1.0)

**Минусы:**
- ❌ Нужно настроить threshold'ы для разных ситуаций
- ❌ Усложняет UX (пользователю нужно понимать confidence)

**Сложность:** Низкая
**Влияние:** Среднее

---

### 1.2 Точное разрешение имён с учётом импортов (высокий приоритет)

**Текущее состояние:** `UserRepository` может ссылаться на любой класс с таким именем в проекте.

**Предложение:** Анализировать `using`, `import`, `from ... import` для точного разрешения.

**Пример:**
```csharp
using MyApp.Data;
using MyApp.Models;

var repo = new Repository(); // ← Должно определиться как MyApp.Data.Repository
```

**Реализация:**
1. Извлечь все import/using statements
2. Построить отображение: `короткое_имя → полное_имя`
3. При поиске ссылок заменять короткие имена на полные

**Плюсы:**
- ✅ Значительно снижает false positives
- ✅ Позволяет находить cross-file ссылки
- ✅ Полезно для рефакторинга

**Минусы:**
- ❌ Сложная реализация для каждого языка
- ❌ Учитывает только explicit imports (implicit using не обрабатываются)

**Сложность:** Высокая
**Влияние:** Высокое

---

### 1.3 Улучшенная фильтрация локальных переменных (средний приоритет)

**Текущее состояние:** Исключаются только symbols (классы, методы), но не локальные переменные.

**Предложение:** Извлекать локальные переменные через tree-sitter и исключать их.

**Пример:**
```python
def process():
    user = User()  # ← user - локальная переменная, не reference к User
    user.name      # ← user - локальная переменная, не reference к классу User
```

**Реализация:**
```python
def extract_local_variables(node, source):
    """Извлечь локальные переменные из функции/метода."""
    vars = set()
    # Найти assignment expressions
    # Найти for loop variables
    # Найти function parameters
    return vars
```

**Плюсы:**
- ✅ Снижает false positives для локальных переменных
- ✅ Улучшает точность для методов

**Минусы:**
- ❌ Требует глубокого AST анализа
- ❌ Language-specific логика

**Сложность:** Средняя
**Влияние:** Среднее

---

### 1.4 Tree-sitter семантический анализ (высокий приоритет)

**Текущее состояние:** Regex-based подход без понимания семантики.

**Предложение:** Использовать tree-sitter для точного определения типов ссылок.

**Типы ссылок:**
- `member_expression` → `object.method` (вызов метода объекта)
- `object_creation` → `new Class()` (создание объекта)
- `identifier` → просто имя (может быть переменная или тип)
- `call_expression` → вызов функции

**Пример:**
```python
# Tree-sitter node types:
repo.get_data()  # → member_expression (call on repo)
User()           # → call/object_creation (constructor)
user_name        # → identifier (variable or type reference)
```

**Реализация:**
```python
def extract_references_semantic(node, source, symbols):
    """Извлечь ссылки с учётом семантики tree-sitter."""
    refs = []
    for child in node.children:
        if child.type == "call_expression":
            func = child.child_by_field_name("function")
            if func.type == "member_expression":
                # Это вызов метода объекта
                refs.append(extract_method_reference(func, source))
        # ... другие типы
```

**Плюсы:**
- ✅ Более точное определение типа ссылки
- ✅ Понимание контекста (метод vs тип vs переменная)
- ✅ Возможность добавить confidence поле

**Минусы:**
- ❌ Сложно в реализации
- ❌ Language-specific node types

**Сложность:** Высокая
**Влияние:** Высокое

---

### 1.5 LSP интеграция для 100% точности (низкий приоритет)

**Текущее состояние:** AST-based анализ с ограниченной точностью.

**Предложение:** Интегрировать с Language Server Protocol для точных ссылок.

**LSP серверы:**
- **C#:** OmniSharp
- **Python:** pylsp
- **TypeScript:** tsserver
- **JavaScript:** eslint-language-server, typescript-language-server

**Реализация:**
```python
class LSPReferenceExtractor:
    def find_references(self, file_path, line, col):
        response = self.lsp_client.call("textDocument/references", {
            "textDocument": {"uri": file_path},
            "position": {"line": line, "character": col}
        })
        return [Location(r["uri"], r["range"]) for r in response]
```

**Плюсы:**
- ✅ 100% точность
- ✅ Полная семантика (разрешает перегрузки, generics)
- ✅ Работает с complex scenarios

**Минусы:**
- ❌ Требует установки LSP серверов
- ❌ Медленно (нужен запуск процессов)
- ❌ Сложная настройка

**Сложность:** Очень высокая
**Влияние:** Очень высокое

---

### 1.6 Улучшенная обработка строковых литералов (средний приоритет)

**Текущее состояние:** Строковые литералы удаляются полностью, что может удалить полезный контекст.

**Предложение:** Более умная обработка — сохранять контекст, но игнорировать содержимое строк.

**Пример:**
```python
message = "UserRepository not found"  # ← Не индексировать "UserRepository" внутри строки
```

**Текущее решение:**
```python
# Удаляем все строковые литералы
content = remove_string_literals(content)  # "..." заменяются на " "
```

**Улучшение:**
```python
# Сохранять структуру, но игнорировать содержимое
def smart_handle_strings(content):
    # Заменить содержимое строк на placeholder, но сохранить позиции
    # для корректной нумерации строк
    pass
```

**Плюсы:**
- ✅ Лучший контекст для ссылок
- ✅ Не теряет информацию о структуре кода

**Минусы:**
- ❌ Сложнее в реализации
- ❌ Минимальное влияние на точность

**Сложность:** Низкая
**Влияние:** Низкое

---

## 2. Производительность

### 2.1 Параллельная индексация (высокий приоритет)

**Текущее состояние:** Последовательная обработка файлов (или ограниченный parallel).

**Предложение:** Использовать все CPU cores для параллельной индексации.

**Реализация:**
```python
from concurrent.futures import ProcessPoolExecutor

def index_parallel(files, max_workers=None):
    """Индексировать файлы параллельно."""
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(parse_file, f) for f in files]
        results = [f.result() for f in futures]
```

**Плюсы:**
- ✅ Значительное ускорение на многоядерных системах
- ✅ Лучшая утилизация ресурсов

**Минусы:**
- ❌ Увеличенное потребление памяти
- ❌ Сложнее отладка

**Сложность:** Средняя
**Влияние:** Высокое

---

### 2.2 Инкрементная индексация при изменении файлов (средний приоритет)

**Текущее состояние:** `ast-index update` перепарсивает все изменённые файлы.

**Предложение:** Использовать file system watchers для автоматической индексации.

**Реализация:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class IndexWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(('.py', '.cs', '.js')):
            indexer.index_file(event.src_path)

observer = Observer()
observer.schedule(IndexWatcher(), project_path, recursive=True)
observer.start()
```

**Плюсы:**
- ✅ Индекс всегда актуален
- ✅ Быстрый отклик на изменения

**Минусы:**
- ❌ Постоянно работающий процесс
- ❌ Увеличенное потребление ресурсов

**Сложность:** Средняя
**Влияние:** Среднее

---

### 2.3 Оптимизация БД (индексы, запросы) (средний приоритет)

**Текущее состояние:** Базовые индексы в SQLite.

**Предложение:** Оптимизировать запросы и добавить compound индексы.

**Примеры:**
```sql
-- Compound индекс для частых запросов
CREATE INDEX idx_refs_symbol_file ON refs(symbol_name, file_id);

-- Covering индекс для search
CREATE INDEX idx_symbols_search ON symbols(name, kind, file_path);

-- Оптимизация FTS5
CREATE VIRTUAL TABLE symbols_fts USING fts5(
    name, signature, file_path,
    content=symbols,
    content_rowid=id
);
```

**Плюсы:**
- ✅ Быстрее запросы
- ✅ Меньше I/O

**Минусы:**
- ❌ Больший размер БД
- ❌ Медленнее запись

**Сложность:** Низкая
**Влияние:** Среднее

---

## 3. UX и CLI

### 3.1 Интерактивный режим (TUI) (низкий приоритет)

**Текущее состояние:** Только CLI команды.

**Предложение:** Добавить интерактивный терминальный интерфейс для навигации по коду.

**Функции:**
- Поиск символов с автодополнением
- Просмотр наследования в виде дерева
- Переход к определению (открыть файл в редакторе)

**Реализация:**
```python
# Используя textual или prompt_toolkit
from textual.app import App

class ASTIndexTUI(App):
    def on_search(self, query):
        results = self.search_engine.search(query)
        self.show_results(results)
```

**Плюсы:**
- ✅ Лучший UX для интерактивного использования
- ✅ Быстрый feedback

**Минусы:**
- ❌ Сложная реализация
- ❌ Не подходит для скриптов

**Сложность:** Высокая
**Влияние:** Среднее

---

### 3.2 Визуализация зависимостей (средний приоритет)

**Текущее состояние:** Текстовый вывод иерархии.

**Предложение:** Генерировать графы зависимостей (DOT, SVG).

**Пример:**
```bash
# Сгенерировать граф наследования
ast-index inheritance "BaseClass" --output graph.dot

# Или SVG
ast-index inheritance "BaseClass" --output graph.svg
```

**Реализация:**
```python
def generate_inheritance_graph(symbol, format="dot"):
    """Сгенерировать граф наследования."""
    # Используя graphviz
    from graphviz import Digraph
    dot = Digraph()
    # ... построение графа
    return dot.source
```

**Плюсы:**
- ✅ Визуальное представление зависимостей
- ✅ Полезно для документации

**Минусы:**
- ❌ Требует graphviz
- ❌ Сложно для больших проектов

**Сложность:** Средняя
**Влияние:** Низкое

---

### 3.3 Поддержка конфигурационных файлов (средний приоритет)

**Текущее состояние:** Есть `.ast-index.yaml`, но ограниченная функциональность.

**Предложение:** Расширить конфигурацию для более тонкой настройки.

**Пример:**
```yaml
# .ast-index.yaml
project_type: csharp

exclude:
  - "vendor/**"
  - "**/*.min.js"

# Новые опции:
references:
  min_confidence: 0.7
  include_standard_library: false
  follow_imports: true

indexing:
  parallel_jobs: 8
  batch_size: 1000
  max_file_size: 5MB

search:
  default_kind: ["class", "interface"]
  fuzzy_threshold: 0.8
```

**Плюсы:**
- ✅ Гибкость настройки
- ✅ Удобство для разных проектов

**Минусы:**
- ❌ Сложнее поддержка
- ❌ Больше конфигурационных опций

**Сложность:** Низкая
**Влияние:** Среднее

---

## 4. Новые языки

### 4.1 Go (средний приоритет)

**Популярность:** Высокая

**Tree-sitter:** tree-sitter-go

**Специфика:**
- Interfaces
- Goroutines
- Go routines
- Structs
- Modules (go.mod)

**Сложность:** Средняя

---

### 4.2 Rust (средний приоритет)

**Популярность:** Высокая

**Tree-sitter:** tree-sitter-rust

**Специфика:**
- Traits
- Macros
- Lifetimes
- Modules
- Crate system

**Сложность:** Высокая (сложный синтаксис)

---

### 4.3 Java (высокий приоритет)

**Популярность:** Очень высокая

**Tree-sitter:** tree-sitter-java

**Специфика:**
- Packages
- Interfaces
- Annotations
- Generics
- Enums

**Сложность:** Средняя

---

### 4.4 PHP (низкий приоритет)

**Популярность:** Средняя

**Tree-sitter:** tree-sitter-php

**Специфика:**
- Namespaces
- Traits
- Interfaces
- Arrays

**Сложность:** Средняя

---

## 5. Интеграции

### 5.1 VS Code расширение (высокий приоритет)

**Функциональность:**
- Peek definition (Alt+Click)
- Find references
- Go to symbol
- Outline view

**Реализация:** vscode-language-client

**Сложность:** Высокая
**Влияние:** Высокое

---

### 5.2 Vim/Neovim плагин (средний приоритет)

**Функциональность:**
- `:GD` — Go to Definition
- `:GR` — Find References
- `:GS` — Search symbols

**Реализация:** Vimscript/Lua

**Сложность:** Средняя
**Влияние:** Среднее

---

### 5.3 Emacs режим (низкий приоритет)

**Функциональность:**
- `ast-index-find-symbol`
- `ast-index-find-references`
- Integration with xref

**Реализация:** Elisp

**Сложность:** Средняя
**Влияние:** Низкое

---

## 6. Экспорт и анализ

### 6.1 Экспорт в JSON Schema (средний приоритет)

**Текущее состояние:** Базовый JSON вывод.

**Предложение:** Поддержка JSON Schema для валидации.

**Пример:**
```json
{
  "$schema": "https://example.com/ast-index.schema.json",
  "symbols": [...],
  "metadata": {...}
}
```

**Плюсы:**
- ✅ Валидация данных
- ✅ Лучшая интеграция с инструментами

**Минусы:**
- ❌ Нужно поддерживать schema

**Сложность:** Низкая
**Влияние:** Низкое

---

### 6.2 Метрики проекта (средний приоритет)

**Текущее состояние:** Базовая статистика (`ast-index stats`).

**Предложение:** Расширенные метрики и аналитика.

**Метрики:**
- Количество классов/методов на файл
- Глубина наследования
- Связность между модулями
- Дублирование кода (потенциальное)

**Пример:**
```bash
ast-index metrics --complexity
# Output:
# Average methods per class: 8.5
# Max inheritance depth: 5
# Most coupled module: Services/UserService.cs
```

**Плюсы:**
- ✅ Полезная аналитика проекта
- ✅ Выявление проблемных мест

**Минусы:**
- ❌ Сложная реализация
- ❌ Может быть медленно на больших проектах

**Сложность:** Высокая
**Влияние:** Среднее

---

## 7. Тестирование и качество

### 7.1 Property-based тесты (средний приоритет)

**Текущее состояние:** Примерные тесты с фиксированными данными.

**Предложение:** Использовать property-based testing (hypothesis).

**Пример:**
```python
from hypothesis import given, strategies as st

@given(st.text())
def test_strip_comments_never_crashes(content):
    """Удаление комментариев не должно падать на любом вводе."""
    result = strip_comments(content, "python")
    assert isinstance(result, str)

@given(st.lists(st.from_type(Symbol)))
def test_extract_references_handles_empty_symbols(symbols):
    """Извлечение ссылок должно работать с пустым списком символов."""
    refs = extract_references_universal("", "test.py", "python", {s.name for s in symbols})
    assert isinstance(refs, list)
```

**Плюсы:**
- ✅ Находит edge cases
- ✅ Проверяет свойства функций

**Минусы:**
- ❌ Дольше выполняются
- ❌ Требует гипотез о свойствах

**Сложность:** Средняя
**Влияние:** Среднее

---

### 7.2 Golden tests (средний приоритет)

**Текущее состояние:** Юнит тесты.

**Предложение:** Добавить golden tests для реальных проектов.

**Реализация:**
```
tests/golden/
  ├── small_python_project/
  │   ├── expected_output.json
  │   └── (файлы проекта)
  ├── medium_csharp_project/
  │   ├── expected_output.json
  │   └── (файлы проекта)
```

**Плюсы:**
- ✅ Тестирование на реальных проектах
- ✅ Быстрое обнаружение регрессий

**Минусы:**
- ❌ Нужно поддерживать golden files
- ❌ Большие данные в репозитории

**Сложность:** Низкая
**Влияние:** Высокое

---

## Приоритеты внедрения

### Краткосрочные (1-2 недели):
1. **1.4** Tree-sitter семантический анализ
2. **3.3** Расширенная конфигурация
3. **7.2** Golden tests

### Среднесрочные (1-2 месяца):
1. **1.2** Точное разрешение имён с учётом импортов
2. **2.1** Параллельная индексация
3. **5.1** VS Code расширение

### Долгосрочные (3-6 месяцев):
1. **1.5** LSP интеграция
2. **2.2** File system watchers
3. **6.2** Метрики проекта

---

## Как добавить улучшение

1. Создайте issue в репозитории с описанием
2. Обсудите подход и реализацию
3. Создайте feature branch
4. Реализуйте улучшение
5. Добавьте тесты
6. Обновите документацию
7. Создайте Pull Request

---

## Обратная связь

Если вы хотите добавить улучшение в этот список или реализовать существующее, пожалуйста:
- Создайте issue или PR
- Обсудите приоритет и сложность
- Уточните детали реализации

Последнее обновление: 2026-03-24
