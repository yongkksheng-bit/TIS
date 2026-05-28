#!/usr/bin/env python3
"""
Circular Import Checker for app/ directory.

Detects circular import dependencies by:
1. Importing all modules in app/
2. Tracking the import order
3. Detecting when a module is being imported while already being imported
"""

import sys
import os
import importlib
import importlib.util
from pathlib import Path
from collections import defaultdict


class CircularImportDetector:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.modules_found = []
        self.modules_failed = []
        self.circular_imports = []
        self.import_graph = defaultdict(set)  # module -> set of modules it imports
        self.import_stack = []  # Current import stack for cycle detection

    def _get_all_py_files(self) -> list[Path]:
        """Get all Python files in the app directory."""
        py_files = []
        for py_file in self.root_dir.rglob("*.py"):
            # Skip __pycache__ and other special directories
            if "__pycache__" in py_file.parts:
                continue
            py_files.append(py_file)
        return sorted(py_files)

    def _path_to_module(self, path: Path) -> str:
        """Convert a file path to a module path."""
        try:
            rel_path = path.relative_to(self.root_dir.parent)
        except ValueError:
            rel_path = path
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]  # Remove .py extension
        return ".".join(parts)

    def _load_module_from_file(self, module_name: str, py_file: Path) -> bool:
        """Load a module directly from a file, bypassing normal import mechanism."""
        # Check if we're already importing this module (circular import)
        if module_name in self.import_stack:
            cycle_start = self.import_stack.index(module_name)
            cycle = self.import_stack[cycle_start:] + [module_name]
            self.circular_imports.append({
                "module": module_name,
                "cycle": cycle,
            })
            return False

        # Check if already fully imported
        if module_name in sys.modules:
            return True

        self.import_stack.append(module_name)

        try:
            # Create a fresh module spec from the file
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create spec for {py_file}")

            module = importlib.util.module_from_spec(spec)

            # Add to sys.modules BEFORE executing to handle circular imports
            sys.modules[module_name] = module

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                # Remove from sys.modules if import fails
                if module_name in sys.modules:
                    del sys.modules[module_name]
                raise

            return True
        except Exception as e:
            if not any(f["module"] == module_name for f in self.modules_failed):
                self.modules_failed.append({
                    "module": module_name,
                    "error": str(e),
                })
            return False
        finally:
            if self.import_stack and self.import_stack[-1] == module_name:
                self.import_stack.pop()

    def _try_import_file(self, py_file: Path) -> bool:
        """Try to import a single Python file as a module."""
        module_name = self._path_to_module(py_file)
        return self._load_module_from_file(module_name, py_file)

    def run(self):
        """Run the circular import check."""
        print(f"Scanning {self.root_dir} for Python modules...")
        print("-" * 60)

        # First, collect all modules
        py_files = self._get_all_py_files()
        print(f"Found {len(py_files)} Python files")

        # Try to import each module
        for py_file in py_files:
            module_name = self._path_to_module(py_file)
            print(f"  Importing: {module_name}...", end=" ")
            sys.stdout.flush()

            success = self._try_import_file(py_file)

            if success:
                print("OK")
                self.modules_found.append(module_name)
            else:
                # Check if it was a circular import or an error
                if any(c["module"] == module_name for c in self.circular_imports):
                    print("CIRCULAR")
                else:
                    print("FAILED")

        print("-" * 60)
        return self.generate_report()

    def generate_report(self) -> dict:
        """Generate the final report."""
        report = {
            "total_modules": len(self.modules_found),
            "failed_modules": len(self.modules_failed),
            "circular_imports": len(self.circular_imports),
            "modules_found": self.modules_found,
            "modules_failed": self.modules_failed,
            "circular_imports_list": self.circular_imports,
        }

        # Print summary
        print(f"\n=== CIRCULAR IMPORT CHECK REPORT ===")
        print(f"Total modules scanned: {len(self.modules_found) + len(self.modules_failed)}")
        print(f"Successfully imported: {len(self.modules_found)}")
        print(f"Failed to import: {len(self.modules_failed)}")
        print(f"Circular imports detected: {len(self.circular_imports)}")

        if self.circular_imports:
            print("\n=== CIRCULAR IMPORTS DETECTED ===")
            for i, ci in enumerate(self.circular_imports, 1):
                print(f"\n{i}. Module: {ci['module']}")
                print(f"   Cycle: {' -> '.join(ci['cycle'])}")

        if self.modules_failed:
            print("\n=== FAILED IMPORTS ===")
            for f in self.modules_failed:
                print(f"\n  Module: {f['module']}")
                print(f"  Error: {f['error']}")

        if not self.circular_imports and not self.modules_failed:
            print("\nNo circular imports or import errors detected!")

        return report


def main():
    # Get the app directory relative to this script
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    app_dir = project_root / "app"

    if not app_dir.exists():
        print(f"Error: {app_dir} does not exist!")
        sys.exit(1)

    # Create detector and run
    detector = CircularImportDetector(str(app_dir))

    # Suppress warnings during import
    import warnings
    warnings.filterwarnings("ignore")

    # Clear any existing app modules from sys.modules to get clean slate
    modules_to_clear = [k for k in sys.modules.keys() if k.startswith("app.")]
    for mod in modules_to_clear:
        del sys.modules[mod]

    report = detector.run()

    # Exit with error code if issues found
    if report["circular_imports"] > 0 or report["failed_modules"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()