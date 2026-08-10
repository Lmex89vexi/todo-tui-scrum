# AGENTS

## Architecture Rules: SOLID + Factory Pattern

# as Mandatory
This project enforces strict adherence to SOLID principles with Factory Pattern for object creation:

1. **Single Responsibility**: Each class has exactly one reason to change.
   - `TodoApp` handles UI only; `TodoRepository` handles data access; `UnitOfWork` handles transactions.
   - No class mixes business logic, UI, and infrastructure concerns.

2. **Open/Closed**: Use Factory Pattern to extend behavior without modifying existing code.
   - New repository implementations (e.g., `MongoDbTodoRepository`) must be added via factory, NOT by editing `TodoApp`.

3. **Liskov Substitution**: All repository implementations must be interchangeable via `TodoRepository` protocol.
   - Both `SqlAlchemyTodoRepository` and hypothetical `InMemoryTodoRepository` implement the same interface.

4. **Interface Segregation**: Repositories expose only the methods they implement.
   - `TodoRepository` protocol defines `list()`, `get()`, `add()`, `remove()` — nothing more.

5. **Dependency Inversion**: Depend on abstractions (`TodoRepository`, `AbstractUnitOfWork`), not concrete implementations.
   - `TodoApp` never instantiates `SqlAlchemyUnitOfWork` directly; it uses the factory.

**Factory Pattern Implementation**:
- `RepositoryFactory` creates repository instances (currently `SqlAlchemyTodoRepository`).
- `UnitOfWorkFactory` creates UnitOfWork instances (currently `SqlAlchemyUnitOfWork`).
- All object creation flows through factories — zero hardcoded `SqlAlchemy*()` in business logic.
- Factories are singletons or static methods to avoid pollution.

---


# as Mandatory 
use codegraph to visualize the architecture and dependencies of the project. This will help ensure that the SOLID principles are being followed and that the Factory Pattern is correctly implemented, 
use codegraph over you own tools calls unless query is not satified fall back to your own tools, and provide a visual representation of the architecture and dependencies of the project.


## Documentation Rules: PEP-257 (Mandatory)

This project enforces PEP-257 docstrings **always** for Python code.

1. Every Python module, public class, function, and method **MUST** have a proper docstring.
2. Use triple double quotes (`"""`) and a one-line summary in imperative mood ending with a period.
3. Multi-line docstrings must include:
   - one-line summary,
   - blank line,
   - detailed behavior/contract.
4. For non-trivial callables, document `Args`, `Returns`, and `Raises` explicitly.
5. Docstrings must explain intent and contract (the **why/what**), not duplicate obvious implementation details.
6. Any code change that adds/modifies Python symbols must add/update docstrings in the same change.

---

## Commit Rules: Conventional Commits (Mandatory)

This project enforces the **Conventional Commits 1.0.0** specification for all commits.

1. **Format**: `<type>[optional scope]: <description>`

   ```
   feat: allow provided config object to extend other configs
   ^--^  ^--------------------------------------------^
   |     |
   |     +-> Summary in imperative mood, no period
   |
   +-------> Type: feat, fix, build, chore, ci, docs, style, refactor, perf, test, revert
   ```

2. **Types** (mandatory for all commits):
   - `feat` — new feature (SemVer MINOR)
   - `fix` — bug fix (SemVer PATCH)
   - `build` — build system or external dependency changes
   - `chore` — maintenance, tooling, config changes
   - `ci` — CI configuration or scripts
   - `docs` — documentation only
   - `style` — formatting, whitespace (no logic change)
   - `refactor` — code change that neither fixes a bug nor adds a feature
   - `perf` — performance improvement
   - `test` — adding or fixing tests
   - `revert` — reverts a previous commit

3. **Breaking changes**: Append `!` after type/scope (e.g., `feat!:`) or add a `BREAKING CHANGE:` footer. Correlates with SemVer MAJOR.

4. **Atomic commits**: Each commit must be a **logically separate change**. If the description grows too long, split into finer-grained commits.

5. **Subject line**: 50-character soft limit, imperative mood ("add feature" not "added feature" or "adds feature"), no trailing period.

6. **Body** (optional but encouraged): Blank line after subject, then explain **why** the change was made (context, rationale, alternatives considered).

7. **Footers** (optional): Use for issue references, co-authors, breaking change notes.

---

## How to use

1. Create a venv and install dependencies:
   - `uv venv`
   - `uv sync`
2. Run the TUI:
   - `uv run todo`
3. Use the app:
   - Add tasks by typing in the new task input (shown with `i` or `a`).
   - Filter with `/` and queries like `status:pending`, `tag:work`, `#work`, or `deleted:true`.
   - Toggle done with `x`, cancel with `c`, restore cancelled tasks with `u`, delete with `d`.

## Runtime notes

- DB URL: default `sqlite:///./todo.db`, override with `TODO_DB_URL` (Postgres uses `postgresql+psycopg://...`).
- Schema is created at startup via `Base.metadata.create_all(engine)` (no Alembic).
- Startup always acquires a DB lock; if no writes occurred, the lock is released on exit; use `--force-unlock` to override.
- Logs: loguru writes to `pytodo.log`; configure with `TODO_LOG_LEVEL`, `TODO_LOG_FILE`, `TODO_LOG_ROTATION`, `TODO_LOG_RETENTION`.

## Filters

- Filter syntax: `status:pending`, `status:completed`, `status:cancelled`, `stat:completed`, `s:done`, `tag:work`, `t:work`, `#work`, `deleted:true`, `deleted:false`, `deleted:all`, plain text matches task.
- Default tag for existing tasks: `TODO_DEFAULT_TASK_TAGS` (default `work`); set empty to disable; runs once via `app_settings` marker; re-run with `--apply-default-tags`.
- Filter defaults: `TODO_FILTER_DEFAULT_TAGS` overrides default tags for filtering; `TODO_FILTER_ALIASES` adds alias pairs like `status=st;tag=label`.
