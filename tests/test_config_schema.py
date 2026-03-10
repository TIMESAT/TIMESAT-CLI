import json
import tempfile
import unittest

from timesat_cli.config import (
    ConfigError,
    LEGACY_MIGRATION_HINT,
    load_config,
    load_config_data,
    migrate_legacy_config_data,
)
from timesat_cli.vpp_layout import build_vpp_output_filenames


def _grouped_config() -> dict:
    return {
        "input": {
            "s3env": "",
            "tv_list": "time.txt",
            "image_file_list": "img.txt",
            "quality_file_list": "qa.txt",
            "lc_file": "lc.tif",
        },
        "output": {
            "outputfolder": "out",
            "outputvariables": 1,
            "p_st_timestep": 1,
            "p_nodata": -9999,
            "p_hrvppformat": 1,
            "yfit_prefix": "TIMESAT",
            "vpp_prefix": "TIMESAT",
            "vpp_variables": [{"source": "SOSD"}, {"source": "TPROD", "name": "TI_PPI"}],
        },
        "general": {
            "imwindow": [0, 0, 0, 0],
            "p_band_id": 1,
            "p_ignoreday": 366,
            "p_ylu": [0.0, 1.0],
            "p_a": [],
            "p_davailwin": 45,
            "p_outlier": 0,
            "p_printflag": 0,
            "max_memory_gb": 1,
            "scale": 1,
            "offset": 0,
            "p_nclasses": 1,
            "classes": [
                {
                    "landuse": 1,
                    "p_fitmethod": 2,
                    "p_smooth": 1000,
                    "p_nenvi": 1,
                    "p_wfactnum": 1,
                    "p_startmethod": 1,
                    "p_startcutoff": [0.25, 0.15],
                    "p_low_percentile": 0.0,
                    "p_fillbase": 0,
                    "p_seasonmethod": 1,
                    "p_seapar": 1,
                }
            ],
        },
    }


class ConfigSchemaTests(unittest.TestCase):
    def test_grouped_schema_parses_successfully(self):
        cfg = load_config_data(_grouped_config())
        s = cfg.settings
        self.assertEqual(s.p_nclasses, 1)
        self.assertEqual(len(s.classes), 1)
        self.assertEqual(s.vpp_variables[1].name, "TI_PPI")
        self.assertEqual(s.yfit_prefix, "TIMESAT")
        self.assertEqual(s.vpp_prefix, "TIMESAT")

    def test_output_prefixes_are_configurable(self):
        cfg_data = _grouped_config()
        cfg_data["output"]["yfit_prefix"] = "YFIT"
        cfg_data["output"]["vpp_prefix"] = "VPP"

        cfg = load_config_data(cfg_data)

        self.assertEqual(cfg.settings.yfit_prefix, "YFIT")
        self.assertEqual(cfg.settings.vpp_prefix, "VPP")

    def test_legacy_schema_is_rejected_with_migration_hint(self):
        legacy = {
            "settings": {"p_nclasses": {"value": 1}},
            "class1": {"landuse": {"value": 1}},
        }
        with self.assertRaises(ConfigError) as ctx:
            load_config_data(legacy)
        self.assertIn(LEGACY_MIGRATION_HINT, str(ctx.exception))

    def test_migrate_config_converts_legacy_to_grouped(self):
        legacy = {
            "settings": {
                "tv_list": {"value": "t.txt"},
                "image_file_list": {"value": "i.txt"},
                "quality_file_list": {"value": "q.txt"},
                "lc_file": {"value": "lc.tif"},
                "outputfolder": {"value": "out"},
                "p_nclasses": {"value": 1},
                "output_hrvpp2": {"value": 1},
            },
            "class1": {
                "landuse": {"value": 7},
                "p_fitmethod": {"value": 2},
                "p_smooth": {"value": 111},
                "p_nenvi": {"value": 1},
                "p_wfactnum": {"value": 1},
                "p_startmethod": {"value": 1},
                "p_startcutoff": {"value": [0.3, 0.2]},
                "p_low_percentile": {"value": 0.1},
                "p_fillbase": {"value": 1},
                "p_seasonmethod": {"value": 1},
                "p_seapar": {"value": 1},
            },
        }
        grouped = migrate_legacy_config_data(legacy)
        self.assertEqual(set(grouped.keys()), {"input", "output", "general"})
        self.assertEqual(grouped["general"]["p_nclasses"], 1)
        self.assertEqual(len(grouped["general"]["classes"]), 1)
        self.assertEqual(grouped["general"]["classes"][0]["landuse"], 7)
        self.assertEqual(grouped["output"]["vpp_variables"][-1]["name"], "TI_PPI")
        self.assertEqual(grouped["output"]["yfit_prefix"], "TIMESAT")
        self.assertEqual(grouped["output"]["vpp_prefix"], "TIMESAT")

    def test_p_nclasses_must_match_classes_length(self):
        cfg = _grouped_config()
        cfg["general"]["p_nclasses"] = 2
        with self.assertRaises(ConfigError) as ctx:
            load_config_data(cfg)
        self.assertIn("must match len(general.classes)", str(ctx.exception))

    def test_general_classes_required_and_non_empty(self):
        cfg = _grouped_config()
        del cfg["general"]["classes"]
        with self.assertRaises(ConfigError) as ctx_missing:
            load_config_data(cfg)
        self.assertIn("general.classes", str(ctx_missing.exception))

        cfg2 = _grouped_config()
        cfg2["general"]["classes"] = []
        with self.assertRaises(ConfigError) as ctx_empty:
            load_config_data(cfg2)
        self.assertIn("non-empty", str(ctx_empty.exception))

    def test_class_field_missing_reports_clear_error(self):
        cfg = _grouped_config()
        del cfg["general"]["classes"][0]["p_smooth"]
        with self.assertRaises(ConfigError) as ctx:
            load_config_data(cfg)
        self.assertIn("missing required key", str(ctx.exception))

    def test_load_config_from_file(self):
        cfg = _grouped_config()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(cfg, f)
            path = f.name
        loaded = load_config(path)
        self.assertEqual(loaded.settings.outputfolder, "out")

    def test_vpp_output_filenames_use_custom_prefix(self):
        outvppfn, outvppqafn, outnsfn = build_vpp_output_filenames(
            vpp_folder="out",
            yrstart=2020,
            yrend=2020,
            variable_names=["SOSD"],
            prefix="VPP",
        )

        self.assertEqual(outvppfn, ["out/VPP_SOSD_2020_season_1.tif", "out/VPP_SOSD_2020_season_2.tif"])
        self.assertEqual(outvppqafn, ["out/VPP_QA_2020_season_1.tif", "out/VPP_QA_2020_season_2.tif"])
        self.assertEqual(outnsfn, ["out/VPP_2020_numseason.tif"])


if __name__ == "__main__":
    unittest.main()
