# Corel Layout Optimizer

Desktop and command-line tools for arranging print artwork on a CorelDRAW
material roll. The PySide6 application manages the print database and order
basket, while the optimizer evaluates several arrangement strategies with a
genetic algorithm and `rectpack`. Accepted layouts can be exported through
CorelDRAW's COM interface.

## Usage

Install the dependencies from `pyproject.toml`, then start the desktop UI:

```powershell
python app.py
```

The UI writes a temporary order, runs `main.py` in the background, previews
the best layouts, and saves the selected result as
`data/accepted_layouts/final_production_layout.json`. The command-line entry point can also process
an order JSON directly:

```powershell
python main.py zlecenie.json
```

### Generate AI training layouts

Generate a fixed number of reproducible orders using a roll width of 443:

```powershell
python generate_orders.py --count 100 --output training_orders.json
```

Run the genetic algorithm sequentially, one order after another. Each result
is saved in `data/training/` using the same layout JSON format as the
existing training files, including `wysokosc_rolki`, `szerokosc_maszyny`, and
all element coordinates and dimensions:

```powershell
python generate_training_data.py training_orders.json --seed 42
```

For a quick test, reduce the search effort:

```powershell
python generate_training_data.py training_orders.json --population-size 20 --generations 10
```

## Architecture

- `ui/` contains the PySide6 basket, result tabs, and layout preview.
- `services/` handles order/database persistence and CorelDRAW export.
- `optimizer/` contains strategy generation, genetic search, fitness scoring,
  and layout serialization.
- `integrations/` contains the lazy CorelDRAW COM connection.
- `data/` contains the print database, training layouts, and accepted
  production layouts.
- `parameter_search/` contains Optuna search code and its saved profiles.
- `experiments/` contains notebooks and benchmark artifacts.

The application uses English internal names and user-facing text. Existing
Polish JSON keys (for example `szerokosc_maszyny` and `elementy`) are
intentionally preserved so existing orders remain compatible. Runtime and
production file names use English names.

### Managing products from CorelDRAW

The PySide6 database window provides three CorelDRAW workflows:

- **New product from CorelDRAW** reads the active CorelDRAW selection, converts
  its dimensions to millimetres, and saves the entered name and category.
- **Split product into parts** creates a table of parts. Each row is scanned
  separately from CorelDRAW and is saved with `czesc_z` pointing to its parent
  product.
- **Create combo** accepts multiple database products with quantities, scans
  the complete combo selection for its real dimensions, and saves the
  composition in `sklad_combo`.

The CorelDRAW document path is stored in `plik`; the `typ` field remains the
slash-separated category path used by the database tree. The active selection
must be present in CorelDRAW when a scan button is pressed.

The **Text generator** accepts one inscription per line and uses one selected
font for all lines. Its test button creates temporary CorelDRAW text objects
to measure every line. A reference line defines the main height (for example,
the visible `O` height in a font); all lines are scaled relative to that
reference. Width limiting can be flat (only lines exceeding the limit are
narrowed) or percentage-based (the same percentage is applied to every line).
The reference text defaults to `O` and can be changed independently of the
generated lines. Saving generated prints is optional. When enabled, each line
has its own database name and CDR file path, both of which are required.

## Algorithm notebooks

The `experiments/notebooks/` directory contains two experiment notebooks:

- `layout_algorithm_lab.ipynb` compares the existing genetic algorithm
  baseline with first-fit decreasing, area decreasing, and random search.
  It displays a pandas results table, matplotlib charts, and SVG layout
  previews.
- `generate_layout_benchmarks.ipynb` creates reproducible random orders from
  `data/print_database.json`. It excludes combo/component records, selects several
  different ordinary prints from one deepest category, and gives each print
  a typical quantity of 7–13, with occasional quantities up to 20. It
  evaluates the baseline and saves `benchmark_orders.json` for fair
  comparisons.

Open either notebook in VS Code with the Jupyter extension, select the project
`.venv` interpreter, and run the cells from top to bottom. The dependencies
`pandas`, `matplotlib`, and `numpy` are included in `pyproject.toml`.

### Automatic settings by size category

The parameter search creates independent Optuna studies for the `short`,
`medium`, and `tall` training categories. After the category searches have
produced their results JSON files, the optimizer can use the best settings
from the selected category:

```python
from new_optimizer import run_genetic_algorithm_auto

height, packer = run_genetic_algorithm_auto(
    items,
    machine_width=443,
    parameter_results_path="parameter_search/artifacts/parameter_search_category_3s_results.json",
)
```

The results path can be the common base path; sibling files ending in
`_short.json`, `_medium.json`, and `_tall.json` are loaded automatically.
The category is inferred from the order's estimated occupied height. You can
also pass `size_category="short"`, `"medium"`, or `"tall"` explicitly.
Explicit keyword arguments override the selected Optuna profile.