from __future__ import annotations
import math, os, datetime

def run(jsfile: str) -> None:

    import numpy as np
    import rasterio
    import timesat  # external dependency

    from .config import load_config, build_param_array
    from .readers import read_file_lists, open_image_data
    from .fsutils import create_output_folders, memory_plan, close_all
    from .writers import prepare_profiles, write_layers
    from .dateutils import date_with_ignored_day, generate_output_timeseries_dates

    VPP_NAMES = ["SOSD","SOSV","LSLOPE","EOSD","EOSV","RSLOPE","LENGTH",
                 "MINV","MAXD","MAXV","AMPL","TPROD","SPROD"]

    def _build_output_filenames(st_folder: str, vpp_folder: str, p_outindex, yrstart: int, yrend: int, p_ignoreday: int):
        outyfitfn = []
        outyfitqafn = []
        for i_tv in p_outindex:
            yfitdate = date_with_ignored_day(yrstart, int(i_tv), p_ignoreday)
            outyfitfn.append(os.path.join(st_folder, f"TIMESAT_{yfitdate.strftime('%Y%m%d')}.tif"))
            outyfitqafn.append(os.path.join(st_folder, f"TIMESAT_{yfitdate.strftime('%Y%m%d')}_QA.tif"))

        outvppfn = []
        outvppqafn = []
        outnsfn = []
        for i_yr in range(yrstart, yrend + 1):
            for i_seas in range(2):
                for name in VPP_NAMES:
                    outvppfn.append(os.path.join(vpp_folder, f"TIMESAT_{name}_{i_yr}_season_{i_seas+1}.tif"))
                outvppqafn.append(os.path.join(vpp_folder, f"TIMESAT_QA_{i_yr}_season_{i_seas+1}.tif"))
            outnsfn.append(os.path.join(vpp_folder, f"TIMESAT_{i_yr}_numseason.tif"))
        return outyfitfn, outyfitqafn, outvppfn, outvppqafn, outnsfn


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


    timevector, flist, qlist, yr, yrstart, yrend = read_file_lists(s.tv_list, s.image_file_list, s.quality_file_list)
 
    z = len(flist)
    print(f'num of images: {z}')
    print('First image: ' + os.path.basename(flist[0]))
    print('Last  image: ' + os.path.basename(flist[-1]))
    print(yrstart)

    # -------load inputs----------------
    use_s3  = getattr(s, "s3env", None)
    if use_s3:
        from .config_s3 import load_s3_config, build_rasterio_s3_opts, to_vsis3_paths
        cfg_s3 = load_s3_config()
        s3_opts = build_rasterio_s3_opts(cfg_s3)
        flist = [to_vsis3_paths(s3_opts, cfg_s3["S3_BUCKET"], k) for k in flist]
        qlist = [to_vsis3_paths(s3_opts, cfg_s3["S3_BUCKET"], k) for k in qlist] if qlist else []
    else:
        s3_opts = None

    # batch_size = int(getattr(s, "read_batch_size", 32))  # recommended: 16–32 (S3), 64–128 (local SSD)

    # ------load image info---------------
    with rasterio.open(flist[0], "r") as temp:
        img_profile = temp.profile

    if sum(s.imwindow) == 0:
        dx, dy = img_profile['width'], img_profile['height']
    else:
        dx, dy = int(s.imwindow[2]), int(s.imwindow[3])


    # ------output-----------------
    st_folder, vpp_folder = create_output_folders(s.outputfolder)

    p_outindex, p_outindex_num = generate_output_timeseries_dates(s.p_st_timestep, yr, yrstart)

    outyfitfn, outyfitqafn, outvppfn, outvppqafn, outnsfn = _build_output_filenames(st_folder, vpp_folder, p_outindex, yrstart, yrend, s.p_ignoreday)

    img_profile_st, img_profile_vpp, img_profile_qa, img_profile_ns = prepare_profiles(img_profile, s.p_nodata, s.scale, s.offset)
    # Open output datasets once and reuse them for all blocks
    st_datasets = []
    stqa_datasets = []
    vpp_datasets = []
    vppqa_datasets = []
    ns_dataset = []

    # VPP outputs
    if s.outputvariables == 1:
        for path in outvppfn:
            ds = rasterio.open(path, "w", **img_profile_vpp)
            vpp_datasets.append(ds)
        for path in outvppqafn:
            ds = rasterio.open(path, "w", **img_profile_qa)
            vppqa_datasets.append(ds)
        for path in outnsfn:
            ds = rasterio.open(path, "w", **img_profile_ns)
            ns_dataset.append(ds)

    # ST (yfit) outputs
    for path in outyfitfn:
        ds = rasterio.open(path, "w", **img_profile_st)
        st_datasets.append(ds)
    for path in outyfitqafn:
        ds = rasterio.open(path, "w", **img_profile_qa)
        stqa_datasets.append(ds)

    
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
            s.p_a,
            s.p_band_id,
        )

        print('--- start TIMESAT processing ---  starttime: ' + str(datetime.datetime.now()))

        if s.scale != 1 or s.offset != 0:
            vi = vi * s.scale + s.offset

        vpp, vppqa, nseason, yfit, yfitqa, seasonfit, tseq = timesat.tsfprocess(
            yr, vi, qa, timevector, lc, s.p_nclasses, landuse_arr, p_outindex,
            s.p_ignoreday, s.p_ylu, s.p_printflag, p_fitmethod_arr, p_smooth_arr,
            s.p_nodata, s.p_davailwin, s.p_outlier,
            p_nenvi_arr, p_wfactnum_arr, p_startmethod_arr, p_startcutoff_arr,
            p_low_percentile_arr, p_fillbase_arr, s.p_hrvppformat,
            p_seasonmethod_arr, p_seapar_arr, s.outputvariables)

        print('--- start writing geotif ---  starttime: ' + str(datetime.datetime.now()))
        window = (x_map, y_map, x, y)

        if s.outputvariables == 1:
            vpp  = np.moveaxis(vpp, -1, 0)
            write_layers(vpp_datasets, vpp, window)

            vppqa  = np.moveaxis(vppqa, -1, 0)
            write_layers(vppqa_datasets, vppqa, window)

            nseason  = np.moveaxis(nseason, -1, 0)
            write_layers(ns_dataset, nseason, window)

        # Move to (t, y, x)
        yfit = np.moveaxis(yfit, -1, 0)

        nodata_val = img_profile_st.get("nodata", s.p_nodata)
        yfit = np.nan_to_num(yfit, nan=nodata_val, posinf=nodata_val, neginf=nodata_val)

        if s.scale == 1 and s.offset == 0:
            yfit = yfit.astype(img_profile['dtype'])
        else:
            yfit = yfit.astype('float32')
        write_layers(st_datasets, yfit, window)

        yfitqa  = np.moveaxis(yfitqa, -1, 0)
        write_layers(stqa_datasets, yfitqa, window)

        print(f'Block: {iblock + 1}/{num_block}  finishedtime: {datetime.datetime.now()}')

    close_all(
        st_datasets,
        stqa_datasets,
    )

    if s.outputvariables == 1:
        close_all(
            vpp_datasets,
            vppqa_datasets,
            ns_dataset,
        )

    
