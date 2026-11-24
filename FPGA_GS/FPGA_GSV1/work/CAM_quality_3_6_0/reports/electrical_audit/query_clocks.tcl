open_project E:/zhoumian/FPGA/FPGA_GS/FPGA_GSV1/work/CAM_quality_3_6_0/rear_pixels_source/build/CAM1_RAW_E3_3_6_0_20261024_203852_117/build.pds
set_dir -impl_directory E:/zhoumian/FPGA/FPGA_GS/FPGA_GSV1/work/CAM_quality_3_6_0/reports/electrical_audit/clock_paths
report_timing -force_to_run -input_db_file E:/zhoumian/FPGA/FPGA_GS/FPGA_GSV1/work/CAM_quality_3_6_0/rear_pixels_source/build/CAM1_RAW_E3_3_6_0_20261024_203852_117/place_route/fpga_gsv1_top_pnr.adf -from {cmos2_d_d0* cmos2_href_d0* cmos2_vsync_d0*} -max_path 160 -nworst 4 -input_pins TRUE
exit
