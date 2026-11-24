from pathlib import Path
r=Path(__file__).resolve().parent/'rear_gain_source'
p=r/'rtl/board/fpga_gsv1_top.v'
s=p.read_text()
insert='''    // CAM1-only gain contrast, independent of CAM0 exposure/ownership.
    wire [351:0] rear_gain_registers;
    wire rear_gain_valid,rear_gain_failed,rear_gain_timeout;
    wire [7:0] rear_gain_sequence,rear_gain_errors,rear_gain_original_high,rear_gain_applied_high;
    wire [3:0] rear_gain_nack,rear_gain_error,rear_gain_phase;
    wire [23:0] rear_baseline_exposure;wire[7:0] rear_baseline_manual;
    wire [15:0] rear_baseline_gain,rear_baseline_ceiling,rear_gain_target,rear_row_ticks;
    wire [31:0] rear_baseline_ms,rear_sweep_ms;
    cam1_gain_profile #(.GAIN_CEILING_RAW(128)) rear_gain_profile(
      .clk(sys_clk),.rst_n(cmos2_reset),.enable(cmos_init_done[1]),
      .scl(cmos2_scl),.sda(cmos2_sda),.registers(rear_gain_registers),
      .valid(rear_gain_valid),.sequence_number(rear_gain_sequence),.errors(rear_gain_errors),
      .last_nack(rear_gain_nack),.error_code(rear_gain_error),.last_timeout(rear_gain_timeout),
      .failed(rear_gain_failed),.phase(rear_gain_phase),.baseline_exposure(rear_baseline_exposure),
      .baseline_manual(rear_baseline_manual),.baseline_gain(rear_baseline_gain),
      .baseline_ceiling(rear_baseline_ceiling),.target_ceiling(rear_gain_target),
      .original_high(rear_gain_original_high),.applied_high(rear_gain_applied_high),
      .milliseconds(cam1_ms),.baseline_ms(rear_baseline_ms),.sweep_ms(rear_sweep_ms));
    cam0_row_period rear_row_measure(.clk(sys_clk),.rst_n(cmos2_reset),
      .href(cmos2_href),.vs(cmos2_vsync),.ticks(rear_row_ticks));
'''
marker='    cam_ov3660_config #(.ROTATE_180(CAM1_ROTATE_180))'
assert marker in s
s=s.replace(marker,insert+marker)
old="wire [895:0] camera_diagnostics={cam1_diagnostics,32'h43304f39,"
assert old in s
s=s.replace(old,"wire [639:0] cam0_read_diagnostics={32'h43304f39,")
marker='//CMOS 8bit'
at=s.index(marker)
s=s[:at]+'''    // Alternate CAMERA readback pages; original C0O9 page remains intact.
    // W12..19 always retain C1R8 rates/geometry. UART/network module unchanged.
    wire [639:0] cam1_gain_diagnostics={32'h43315131,
      rear_gain_phase,rear_gain_failed,rear_gain_valid,rear_gain_timeout,1'b0,
      rear_gain_error,rear_gain_nack,rear_gain_sequence,rear_gain_errors,
      rear_baseline_exposure,rear_baseline_manual,
      rear_baseline_gain,rear_baseline_ceiling,
      rear_gain_target,rear_gain_original_high,rear_gain_applied_high,
      rear_row_ticks,16'd0,rear_baseline_ms,rear_sweep_ms,32'd0,rear_gain_registers};
    wire [895:0] camera_diagnostics={cam1_diagnostics,
      cam1_ms[10] ? cam1_gain_diagnostics:cam0_read_diagnostics};
'''+s[at:]
p.write_text(s)
p=r/'flow.tcl';s=p.read_text();assert 'cam1_gain_profile' not in s
s=s.replace('add_design "rtl/capture/cam0_readback.v"',
            'add_design "rtl/capture/cam0_readback.v"\nadd_design "rtl/capture/cam1_gain_profile.v"')
p.write_text(s)
p=r/'scripts/build_cam0.ps1';s=p.read_text()
s=s.replace("$variant='CAM0_OV5640_3_5_9_READBACK'", "$variant='CAM1_GAIN8_E2_3_6_0'")
# The inherited variant spelling is checked instead of silently retaining R0.
if "$variant='CAM1_GAIN8_E2_3_6_0'" not in s:
    import re
    s=re.sub(r"\$variant='[^']+'", "$variant='CAM1_GAIN8_E2_3_6_0'",s)
import re
s=re.sub(r"\$version='[^']+'", "$version='CAM1 gain ceiling8x controlled candidate E2,20s original baseline; CAM0 unchanged'",s)
p.write_text(s)
print('Prepared CAM1-only8x gain contrast; separate R0 source; no CAM0 owner/exposure change')
