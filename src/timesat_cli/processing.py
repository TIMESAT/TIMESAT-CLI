from __future__ import annotations
import math, os, datetime

def run(jsfile: str) -> None:

    import numpy as np
    import rasterio
    import timesat  # external dependency

    from .config import load_config, build_param_array
    from .readers import read_file_lists, open_image_data, strip_band_ref
    from .qa import assign_qa_weight
    from .fsutils import create_output_folders, memory_plan
    from .writers import prepare_profiles, write_layers_paths
    from .dateutils import date_with_ignored_day, generate_output_timeseries_dates
    from .vpp_layout import (
        TIMESAT_VPP_NAMES,
        build_vpp_layer_transform_info,
        build_vpp_output_filenames,
        convert_date_vpp_layers_to_layer_doy,
        select_vpp_layers,
    )

    def _build_output_filenames(
        st_folder: str,
        vpp_folder: str,
        p_outindex,
        yrstart: int,
        yrend: int,
        p_ignoreday: int,
        yfit_prefix: str,
        vpp_prefix: str,
        vpp_output_names,
    ):
        outyfitfn = []
        outyfitqafn = []
        for i_tv in p_outindex:
            yfitdate = date_with_ignored_day(yrstart, int(i_tv), p_ignoreday)
            outyfitfn.append(os.path.join(st_folder, f"{yfit_prefix}_{yfitdate.strftime('%Y%m%d')}.tif"))
            outyfitqafn.append(os.path.join(st_folder, f"{yfit_prefix}_{yfitdate.strftime('%Y%m%d')}_QA.tif"))

        outvppfn, outvppqafn = build_vpp_output_filenames(
            vpp_folder=vpp_folder,
            yrstart=yrstart,
            yrend=yrend,
            variable_names=vpp_output_names,
            prefix=vpp_prefix,
        )
        return outyfitfn, outyfitqafn, outvppfn, outvppqafn


    print(jsfile)
    cfg = load_config(jsfile)
    s = cfg.settings

    if s.outputfolder == '':
        print('Nothing to do...')
        return

    # Precompute arrays once per block to pass into timesat
    landuse_arr          = build_param_array(s, 'landuse', 'uint8')
    p_fitmethod_arr      = build_param_array(s, 'p_fitmethod', 'uint8')
    p_smooth_arr         = build_param_array(s, 'p_smooth', 'double')
    p_nenvi_arr          = build_param_array(s, 'p_nenvi', 'uint8')
    p_wfactnum_arr       = build_param_array(s, 'p_wfactnum', 'double')
    p_startmethod_arr    = build_param_array(s, 'p_startmethod', 'uint8')
    p_startcutoff_arr    = build_param_array(s, 'p_startcutoff', 'double', shape=(2,), fortran_2d=True)
    p_low_percentile_arr = build_param_array(s, 'p_low_percentile', 'double')
    p_fillbase_arr       = build_param_array(s, 'p_fillbase', 'uint8')
    p_seasonmethod_arr   = build_param_array(s, 'p_seasonmethod', 'uint8')
    p_seapar_arr         = build_param_array(s, 'p_seapar', 'double')
    p_lowrangemode_arr   = build_param_array(s, 'p_lowrangemode', 'int32', fill_value=1)
    p_highrangemode_arr  = build_param_array(s, 'p_highrangemode', 'int32')
    p_rangedownweight_arr = build_param_array(s, 'p_rangedownweight', 'double', fill_value=0.5)


    timevector, flist, qlist, yr, yrstart, yrend = read_file_lists(s.tv_list, s.image_file_list, s.quality_file_list)
 
    z = len(flist)
    print(f'num of images: {z}')
    print('First image: ' + os.path.basename(flist[0]))
    print('Last  image: ' + os.path.basename(flist[-1]))
    print(yrstart)

    # -------load inputs----------------
    s3env  = getattr(s, "s3env", None)
    if s3env:
        from .config_s3 import load_s3_config, build_rasterio_s3_opts, to_vsis3_paths
        cfg_s3 = load_s3_config(s3env)
        s3_opts = build_rasterio_s3_opts(cfg_s3)
        flist = [to_vsis3_paths(s3_opts, cfg_s3["S3_BUCKET"], k) for k in flist]
        qlist = [to_vsis3_paths(s3_opts, cfg_s3["S3_BUCKET"], k) for k in qlist] if qlist else []
    else:
        s3_opts = None

    # batch_size = int(getattr(s, "read_batch_size", 32))  # recommended: 16–32 (S3), 64–128 (local SSD)

    # ------load image info---------------
    with rasterio.open(strip_band_ref(flist[0]), "r") as temp:
        img_profile = temp.profile

    if sum(s.imwindow) == 0:
        dx, dy = img_profile['width'], img_profile['height']
    else:
        dx, dy = int(s.imwindow[2]), int(s.imwindow[3])


    # ------output-----------------
    st_folder, vpp_folder = create_output_folders(s.outputfolder)
    selected_vpp_sources = [v.source for v in s.vpp_variables]
    selected_vpp_output_names = [v.name for v in s.vpp_variables]
    if s.outputvariables == 1:
        source_to_output = ", ".join(
            f"{src}->{dst}" if src != dst else src
            for src, dst in zip(selected_vpp_sources, selected_vpp_output_names)
        )
        print(f"Selected VPP variables: {source_to_output}")

    p_outindex, p_outindex_num = generate_output_timeseries_dates(
        s.p_st_timestep,
        yr,
        yrstart,
        time_sampling=s.time_sampling,
        time_step_days=s.time_step_days,
        monthly_days=s.monthly_days,
        drop_first_year=s.drop_first_year,
        drop_last_year=s.drop_last_year,
    )
    date_layer_years = None
    date_layer_indices = None
    scaled_layer_indices = None
    if s.outputvariables == 1 and s.p_hrvppformat == 1:
        date_layer_years, date_layer_indices, scaled_layer_indices = build_vpp_layer_transform_info(
            yrstart,
            yrend,
            src_names=TIMESAT_VPP_NAMES,
        )

    outyfitfn, outyfitqafn, outvppfn, outvppqafn = _build_output_filenames(
        st_folder,
        vpp_folder,
        p_outindex,
        yrstart,
        yrend,
        s.p_ignoreday,
        s.yfit_prefix,
        s.vpp_prefix,
        selected_vpp_output_names,
    )

    img_profile_st, img_profile_vpp, img_profile_qa = prepare_profiles(
        img_profile,
        s.p_nodata,
        s.scale,
        s.offset,
        s.vpp_dtype,
    )
    # Create output datasets upfront, then close immediately.
    if s.outputvariables == 1:
        for path in outvppfn:
            with rasterio.open(path, "w", **img_profile_vpp):
                pass
        for path in outvppqafn:
            with rasterio.open(path, "w", **img_profile_qa):
                pass

    for path in outyfitfn:
        with rasterio.open(path, "w", **img_profile_st):
            pass
    for path in outyfitqafn:
        with rasterio.open(path, "w", **img_profile_qa):
            pass

    
    # compute blocks
    y_slice_size, num_block = memory_plan(dx, dy, z, p_outindex_num, yr, s.max_memory_gb)
    y_slice_end = dy % y_slice_size if (dy % y_slice_size) > 0 else y_slice_size
    print('y_slice_size = ' + str(y_slice_size))

    for iblock in range(num_block):
        print(f'Processing block: {iblock + 1}/{num_block}  starttime: {datetime.datetime.now()}')
        x = dx
        y = int(y_slice_size) if iblock != num_block - 1 else int(y_slice_end)
        x_map = int(s.imwindow[0])
        y_map = int(iblock * y_slice_size + s.imwindow[1])

        # vi, qa, lc = open_image_data_batched(
        #     x_map, y_map, x, y,
        #     flist,
        #     qlist,
        #     (s.lc_file if s.lc_file else None),
        #     img_profile['dtype'],
        #     s.p_a,
        #     s.p_band_id,
        #     batch_size=batch_size,
        #     s3_opts=s3_opts,
        # )
        vi, qa, lc = open_image_data(
            x_map, y_map, x, y,
            flist,
            qlist,
            (s.lc_file if s.lc_file else None),
            img_profile['dtype'],
            s.p_band_id,
        )

        qa = assign_qa_weight(s.p_a, qa)

        print('--- start TIMESAT processing ---  starttime: ' + str(datetime.datetime.now()))

        if s.scale != 1 or s.offset != 0:
            vi = vi * s.scale + s.offset

        vpp, vppqa, _nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
            yr, vi, qa, timevector, lc, s.p_nclasses, landuse_arr, p_outindex,
            s.p_ignoreday, s.p_ylu, s.p_printflag, p_fitmethod_arr, p_smooth_arr,
            s.p_nodata, s.p_davailwin, s.p_outlier,
            p_nenvi_arr, p_wfactnum_arr, p_startmethod_arr, p_startcutoff_arr,
            p_low_percentile_arr, p_fillbase_arr, s.p_hrvppformat,
            p_seasonmethod_arr, p_seapar_arr,
            p_lowrangemode_arr, p_highrangemode_arr, p_rangedownweight_arr,
            s.outputvariables)

        print('--- start writing geotif ---  starttime: ' + str(datetime.datetime.now()))
        window = (x_map, y_map, x, y)

        if s.outputvariables == 1:
            vpp  = np.moveaxis(vpp, -1, 0)
            if s.p_hrvppformat == 1:
                vpp = convert_date_vpp_layers_to_layer_doy(
                    vpp,
                    date_layer_years,
                    date_layer_indices,
                    scaled_layer_indices,
                    p_nodata=s.p_nodata,
                    src_names=TIMESAT_VPP_NAMES,
                )
            vpp = select_vpp_layers(
                vpp,
                src_names=TIMESAT_VPP_NAMES,
                dst_names=selected_vpp_sources,
            )
            write_layers_paths(outvppfn, vpp, window)

            vppqa  = np.moveaxis(vppqa, -1, 0)
            write_layers_paths(outvppqafn, vppqa, window)

        # Move to (t, y, x)
        yfit = np.moveaxis(yfit, -1, 0)

        # nodata_val = img_profile_st.get("nodata", s.p_nodata)
        # try:
        #     nodata_val = float(nodata_val)
        # except Exception:
        #     nodata_val = -9999.0 
        # nodata_val = np.float32(nodata_val)
        # yfit = np.nan_to_num(yfit, nan=nodata_val, posinf=nodata_val, neginf=nodata_val)

        if s.scale == 1 and s.offset == 0:
            yfit = yfit.astype(img_profile['dtype'])
        else:
            yfit = yfit.astype('float32')
        write_layers_paths(outyfitfn, yfit, window)

        yfitqa  = np.moveaxis(yfitqa, -1, 0)
        write_layers_paths(outyfitqafn, yfitqa, window)

        print(f'Block: {iblock + 1}/{num_block}  finishedtime: {datetime.datetime.now()}')

    # No long-lived dataset handles to close.
