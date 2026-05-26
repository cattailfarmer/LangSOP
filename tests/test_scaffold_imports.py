"""No-op import smoke tests for the inert LangSOP scaffold."""

import importlib
import pathlib
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class ScaffoldImportTests(unittest.TestCase):
    def test_inert_modules_import(self) -> None:
        module_names = (
            "langsop",
            "langsop.authority",
            "langsop.kernel",
            "langsop.projections",
            "langsop.operators",
            "langsop.runtime",
            "langsop.surfaces",
            "langsop.coordination",
            "langsop.operations",
        )

        for module_name in module_names:
            with self.subTest(module_name=module_name):
                module = importlib.import_module(module_name)
                self.assertTrue(hasattr(module, "__all__"))

    def test_imports_do_not_create_generated_artifacts(self) -> None:
        import langsop  # noqa: F401

        self.assertFalse((PROJECT_ROOT / ".langsop").exists())

    def test_operations_module_exposes_no_live_control_api(self) -> None:
        operations = importlib.import_module("langsop.operations")

        forbidden_names = {
            "control",
            "deploy",
            "dispatch",
            "execute",
            "gpu",
            "job",
            "network",
            "run",
            "shell",
            "subprocess",
        }

        exposed_names = set(dir(operations))
        self.assertTrue(forbidden_names.isdisjoint(exposed_names))


if __name__ == "__main__":
    unittest.main()

