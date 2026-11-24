add_design probe.v
add_constraint probe.fdc
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
compile -top_module cam1_io_probe
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -optimize_multi_corner_timing -fix_hold_violation
report_timing -report_io_datasheet -input_pins TRUE
exit
