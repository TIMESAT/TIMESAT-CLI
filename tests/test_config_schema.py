import json
import sys
import tempfile
import types
import unittest

from timesat_cli.config import (
    build_param_array,
    ConfigError,
    LEGACY_MIGRATION_HINT,
    load_config,
    load_config_data,
    migrate_legacy_config_data,
)
from timesat_cli.vpp_layout import (
    TIMESAT_VPP_NAMES,
    build_vpp_layer_transform_info,
    build_vpp_output_filenames,
    build_vpp_season_years,
    convert_date_vpp_layers_to_layer_doy,
)

import numpy as np


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
            "vpp_dtype": "float32",
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
        self.assertEqual(s.classes[0].p_lowrangemode, 0)
        self.assertEqual(s.classes[0].p_highrangemode, 0)
        self.assertEqual(s.classes[0].p_rangedownweight, 0.5)

    def test_range_mode_arrays_use_defaults_for_old_config(self):
        cfg = load_config_data(_grouped_config())
        s = cfg.settings

        low = build_param_array(s, "p_lowrangemode", "int32")
        high = build_param_array(s, "p_highrangemode", "int32")
        downweight = build_param_array(s, "p_rangedownweight", "double", fill_value=0.5)

        self.assertEqual(low.shape, (255,))
        self.assertEqual(high.shape, (255,))
        self.assertEqual(downweight.shape, (255,))
        self.assertEqual(low.dtype, np.int32)
        self.assertEqual(high.dtype, np.int32)
        self.assertEqual(downweight.dtype, np.float64)
        self.assertTrue(np.all(low == 0))
        self.assertTrue(np.all(high == 0))
        self.assertTrue(np.all(downweight == 0.5))

    def test_range_mode_arrays_accept_explicit_class_values(self):
        cfg_data = _grouped_config()
        cfg_data["general"]["classes"][0]["lowrangemode"] = 2
        cfg_data["general"]["classes"][0]["highrangemode"] = 1
        cfg_data["general"]["classes"][0]["rangedownweight"] = 0.25

        cfg = load_config_data(cfg_data)
        s = cfg.settings
        low = build_param_array(s, "p_lowrangemode", "int32")
        high = build_param_array(s, "p_highrangemode", "int32")
        downweight = build_param_array(s, "p_rangedownweight", "double", fill_value=0.5)

        self.assertEqual(low[0], 2)
        self.assertEqual(high[0], 1)
        self.assertEqual(downweight[0], 0.25)
        self.assertTrue(np.all(low[1:] == 0))
        self.assertTrue(np.all(high[1:] == 0))
        self.assertTrue(np.all(downweight[1:] == 0.5))

    def test_range_mode_arrays_accept_prefixed_class_values(self):
        cfg_data = _grouped_config()
        cfg_data["general"]["classes"][0]["p_lowrangemode"] = 2
        cfg_data["general"]["classes"][0]["p_highrangemode"] = 1
        cfg_data["general"]["classes"][0]["p_rangedownweight"] = 0.25

        cfg = load_config_data(cfg_data)

        self.assertEqual(cfg.settings.classes[0].p_lowrangemode, 2)
        self.assertEqual(cfg.settings.classes[0].p_highrangemode, 1)
        self.assertEqual(cfg.settings.classes[0].p_rangedownweight, 0.25)

    def test_single_pixel_tsfprocess_argument_order_includes_range_modes(self):
        from timesat_cli.single_pixel import run_single_pixel

        calls = []

        def fake_tsfprocess(*args):
            calls.append(args)
            yfit = np.zeros((1, 1, 1), dtype=np.float32)
            return (
                np.zeros((1, 1, 1), dtype=np.float32),
                np.zeros((1, 1, 1), dtype=np.uint8),
                np.zeros((1, 1), dtype=np.uint8),
                yfit,
                np.zeros_like(yfit, dtype=np.uint8),
                np.zeros_like(yfit),
                np.arange(1),
            )

        old_timesat = sys.modules.get("timesat")
        sys.modules["timesat"] = types.SimpleNamespace(tsfprocess=fake_tsfprocess)
        try:
            run_single_pixel(
                raw_y=np.array([[[0.2]]], dtype=np.float64),
                raw_w=np.array([[[1]]], dtype=np.uint16),
                raw_lc=np.array([[1]], dtype=np.uint8),
                tv_yyyydoy=np.array([2020001], dtype=np.int32),
                yrstart=2020,
                nyear=1,
                npt=1,
                p_outststep=365,
                p_ignoreday=366,
                p_ylu=[0.0, 1.0],
                p_a=[],
                p_printflag=0,
                p_fitmethod=np.ones(255, dtype=np.uint8),
                p_smooth=np.ones(255, dtype=np.float64),
                p_nodata=-9999,
                p_davailwin=45,
                p_outlier=0,
                p_nenvi=np.ones(255, dtype=np.uint8),
                p_wfactnum=np.ones(255, dtype=np.float64),
                p_startmethod=np.ones(255, dtype=np.uint8),
                p_startcutoff=np.ones((255, 2), dtype=np.float64, order="F"),
                p_low_percentile=np.zeros(255, dtype=np.float64),
                p_fillbase=np.zeros(255, dtype=np.uint8),
                p_hrvppformat=1,
                p_seasonmethod=np.ones(255, dtype=np.uint8),
                p_seapar=np.ones(255, dtype=np.float64),
                p_lowrangemode=np.full(255, 2, dtype=np.int32),
                p_highrangemode=np.full(255, 1, dtype=np.int32),
                p_rangedownweight=np.full(255, 0.25, dtype=np.float64),
            )
        finally:
            if old_timesat is None:
                del sys.modules["timesat"]
            else:
                sys.modules["timesat"] = old_timesat

        args = calls[0]
        self.assertTrue(np.all(args[25] == 2))
        self.assertTrue(np.all(args[26] == 1))
        self.assertTrue(np.all(args[27] == 0.25))
        self.assertEqual(args[25].shape, (255,))
        self.assertEqual(args[26].shape, (255,))
        self.assertEqual(args[27].shape, (255,))
        self.assertEqual(args[25].dtype, np.int32)
        self.assertEqual(args[26].dtype, np.int32)
        self.assertEqual(args[27].dtype, np.float64)

    def test_output_prefixes_are_configurable(self):
        cfg_data = _grouped_config()
        cfg_data["output"]["yfit_prefix"] = "YFIT"
        cfg_data["output"]["vpp_prefix"] = "VPP"

        cfg = load_config_data(cfg_data)

        self.assertEqual(cfg.settings.yfit_prefix, "YFIT")
        self.assertEqual(cfg.settings.vpp_prefix, "VPP")

    def test_vpp_dtype_defaults_to_float32(self):
        cfg_data = _grouped_config()
        del cfg_data["output"]["vpp_dtype"]

        cfg = load_config_data(cfg_data)

        self.assertEqual(cfg.settings.vpp_dtype, "float32")

    def test_vpp_dtype_is_configurable(self):
        cfg_data = _grouped_config()
        cfg_data["output"]["vpp_dtype"] = "uint16"

        cfg = load_config_data(cfg_data)

        self.assertEqual(cfg.settings.vpp_dtype, "uint16")

    def test_invalid_vpp_dtype_is_rejected(self):
        cfg_data = _grouped_config()
        cfg_data["output"]["vpp_dtype"] = "badtype"

        with self.assertRaises(ConfigError) as ctx:
            load_config_data(cfg_data)
        self.assertIn("output.vpp_dtype", str(ctx.exception))

    def test_st_profile_uses_configured_p_nodata(self):
        rasterio_fake = types.ModuleType("rasterio")
        rasterio_fake.float32 = np.float32
        rasterio_fake.uint8 = np.uint8
        windows_fake = types.ModuleType("rasterio.windows")
        windows_fake.Window = object
        old_rasterio = sys.modules.get("rasterio")
        old_rasterio_windows = sys.modules.get("rasterio.windows")
        old_writers = sys.modules.get("timesat_cli.writers")
        sys.modules["rasterio"] = rasterio_fake
        sys.modules["rasterio.windows"] = windows_fake
        sys.modules.pop("timesat_cli.writers", None)
        try:
            from timesat_cli.writers import prepare_profiles
        finally:
            if old_rasterio is None:
                del sys.modules["rasterio"]
            else:
                sys.modules["rasterio"] = old_rasterio
            if old_rasterio_windows is None:
                del sys.modules["rasterio.windows"]
            else:
                sys.modules["rasterio.windows"] = old_rasterio_windows
            if old_writers is not None:
                sys.modules["timesat_cli.writers"] = old_writers
            else:
                sys.modules.pop("timesat_cli.writers", None)

        img_profile = {
            "driver": "GTiff",
            "dtype": "uint16",
            "nodata": 0,
            "width": 1,
            "height": 1,
            "count": 3,
        }

        st_profile, _vpp_profile, _qa_profile = prepare_profiles(
            img_profile,
            p_nodata=-9999,
            scale=1,
            offset=0,
        )

        self.assertEqual(st_profile["nodata"], -9999)

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
        self.assertEqual(grouped["output"]["vpp_dtype"], "float32")
        self.assertEqual(grouped["output"]["yfit_prefix"], "TIMESAT")
        self.assertEqual(grouped["output"]["vpp_prefix"], "TIMESAT")
        self.assertEqual(grouped["general"]["classes"][0]["lowrangemode"], 0)
        self.assertEqual(grouped["general"]["classes"][0]["highrangemode"], 0)
        self.assertEqual(grouped["general"]["classes"][0]["rangedownweight"], 0.5)

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

    def test_optional_class_fields_use_defaults(self):
        cfg = _grouped_config()
        del cfg["general"]["classes"][0]["p_smooth"]

        parsed = load_config_data(cfg)

        self.assertEqual(parsed.settings.classes[0].p_smooth, 1000)

    def test_landuse_is_required_for_class_mapping(self):
        cfg = _grouped_config()
        del cfg["general"]["classes"][0]["landuse"]
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
        outvppfn, outvppqafn = build_vpp_output_filenames(
            vpp_folder="out",
            yrstart=2020,
            yrend=2020,
            variable_names=["SOSD"],
            prefix="VPP",
        )

        self.assertEqual(outvppfn, ["out/VPP_SOSD_2020_season_1.tif", "out/VPP_SOSD_2020_season_2.tif"])
        self.assertEqual(outvppqafn, ["out/VPP_QA_2020_season_1.tif", "out/VPP_QA_2020_season_2.tif"])

    def test_vpp_output_filenames_do_not_include_numseason(self):
        output_groups = build_vpp_output_filenames(
            vpp_folder="out",
            yrstart=2020,
            yrend=2022,
            variable_names=["SOSD", "EOSD"],
            prefix="VPP",
        )

        self.assertEqual(len(output_groups), 2)
        self.assertTrue(
            all("numseason" not in path for output_group in output_groups for path in output_group)
        )

    def test_build_vpp_season_years_matches_filename_order(self):
        self.assertEqual(build_vpp_season_years(2020, 2021), [2020, 2020, 2021, 2021])

    def test_build_vpp_layer_transform_info_matches_source_order(self):
        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2020)
        self.assertEqual(date_indices, [0, 3, 8])
        self.assertEqual(scaled_indices, [11, 12])
        self.assertTrue(np.array_equal(layer_years, np.array([2020.0] * 6)))

    def test_date_vpp_layers_are_converted_to_layer_relative_doy(self):
        vpp_layers = np.zeros((len(TIMESAT_VPP_NAMES) * 4, 1, 1), dtype=np.float32)

        def set_layer(season_i: int, name: str, value: float) -> None:
            layer_idx = season_i * len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index(name)
            vpp_layers[layer_idx, 0, 0] = value

        set_layer(0, "SOSD", 2020010)
        set_layer(1, "EOSD", 2020360)
        set_layer(2, "MAXD", 2021005)
        set_layer(3, "SOSD", 2021360)

        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2021)
        converted = convert_date_vpp_layers_to_layer_doy(
            vpp_layers, layer_years, date_indices, scaled_indices, p_nodata=-9999
        )

        self.assertEqual(converted[TIMESAT_VPP_NAMES.index("SOSD"), 0, 0], 10)
        self.assertEqual(converted[len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("EOSD"), 0, 0], 360)
        self.assertEqual(converted[2 * len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("MAXD"), 0, 0], 5)
        self.assertEqual(converted[3 * len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("SOSD"), 0, 0], 360)

    def test_date_vpp_layers_keep_cross_year_offset_with_layer_year(self):
        vpp_layers = np.zeros((len(TIMESAT_VPP_NAMES) * 2, 1, 1), dtype=np.float32)
        season2_sosd = len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("SOSD")
        vpp_layers[season2_sosd, 0, 0] = 2019360

        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2020)
        converted = convert_date_vpp_layers_to_layer_doy(
            vpp_layers, layer_years, date_indices, scaled_indices, p_nodata=-9999
        )

        self.assertEqual(converted[season2_sosd, 0, 0], -5)

    def test_date_vpp_layers_skip_nodata_and_non_yyyydoy_values(self):
        vpp_layers = np.zeros((len(TIMESAT_VPP_NAMES) * 2, 1, 3), dtype=np.float32)
        sosd = TIMESAT_VPP_NAMES.index("SOSD")
        vpp_layers[sosd, 0, 0] = -9999
        vpp_layers[sosd, 0, 1] = 123
        vpp_layers[sosd, 0, 2] = 2020123

        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2020)
        converted = convert_date_vpp_layers_to_layer_doy(
            vpp_layers, layer_years, date_indices, scaled_indices, p_nodata=-9999
        )

        self.assertEqual(converted[sosd, 0, 0], -9999)
        self.assertEqual(converted[sosd, 0, 1], 123)
        self.assertEqual(converted[sosd, 0, 2], 123)

    def test_date_vpp_layers_support_fractional_doy(self):
        vpp_layers = np.zeros((len(TIMESAT_VPP_NAMES) * 2, 1, 1), dtype=np.float32)
        sosd = len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("SOSD")
        vpp_layers[sosd, 0, 0] = 2016120.5

        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2020)
        converted = convert_date_vpp_layers_to_layer_doy(
            vpp_layers, layer_years, date_indices, scaled_indices, p_nodata=-9999
        )

        self.assertEqual(converted[sosd, 0, 0], -1339.5)

    def test_product_vpp_layers_are_scaled_by_one_thousand(self):
        vpp_layers = np.zeros((len(TIMESAT_VPP_NAMES) * 2, 1, 2), dtype=np.float32)
        tprod = TIMESAT_VPP_NAMES.index("TPROD")
        sprod = len(TIMESAT_VPP_NAMES) + TIMESAT_VPP_NAMES.index("SPROD")
        vpp_layers[tprod, 0, 0] = 2500
        vpp_layers[tprod, 0, 1] = -9999
        vpp_layers[sprod, 0, 0] = 1250

        layer_years, date_indices, scaled_indices = build_vpp_layer_transform_info(2020, 2020)
        converted = convert_date_vpp_layers_to_layer_doy(
            vpp_layers, layer_years, date_indices, scaled_indices, p_nodata=-9999
        )

        self.assertEqual(converted[tprod, 0, 0], 2.5)
        self.assertEqual(converted[tprod, 0, 1], -9999)
        self.assertEqual(converted[sprod, 0, 0], 1.25)


if __name__ == "__main__":
    unittest.main()
