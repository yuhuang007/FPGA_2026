from pathlib import Path
import shutil

r=Path(__file__).resolve().parent
src=r/'rear_gain_source'
dst=r/'rear_pixels_source'
assert not dst.exists(), 'Do not overwrite an existing candidate'
dst.mkdir()
for name in ('rtl','vendor','constraints','config','scripts','sim'):
    shutil.copytree(src/name,dst/name,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(src/'flow.tcl',dst/'flow.tcl')
p=dst/'rtl/board/fpga_gsv1_top.v'
s=p.read_text(encoding='utf-8')
a=s.index('    wire [351:0] rear_gain_registers;')
b=s.index('    cam_ov3660_config #',a)
s=s[:a]+s[b:]
a=s.index('    wire [639:0] cam1_gain_diagnostics=')
b=s.index('//CMOS8',a) if '//CMOS8' in s[a:] else s.index('//CMOS 8',a)
# Replace only the quality diagnostic page, up to the next CMOS section comment.
tail=s.index('camera_diagnostics={cam1_diagnostics,cam1_gain_diagnostics};',a)+len('camera_diagnostics={cam1_diagnostics,cam1_gain_diagnostics};')
s=s[:a]+'''    wire [639:0] cam1_pixel_page;
    cam1_pixel_patch rear_pixel_patch(.sc(sys_clk),.vc(cmos2_pclk_16bit),
      .rst_n(rstn_out),.ready(pipe_rst1),.vs(cap_vs1),.de(cap_de1),.rgb(cap_rgb1),
      .frame_id(cap_id1),.result_valid(verdict_valid1),.result_id(verdict_id1),
      .result_errors(verdict_errors1 | {7'd0,cam1_verdict_byte_error}),.page(cam1_pixel_page));
    wire [895:0] camera_diagnostics={cam1_diagnostics,cam1_pixel_page};'''+s[tail:]
p.write_text(s,encoding='utf-8')
p=dst/'flow.tcl';s=p.read_text().replace('add_design "rtl/capture/cam1_gain_profile.v"','add_design "rtl/capture/cam1_pixel_patch.v"');p.write_text(s)
p=dst/'rtl/network/m365_tx_observer.v';s=p.read_text().replace('m361_uart_hex #(.REVISION_ASCII("O"))','m361_uart_hex #(.TICKS(2500000),.REVISION_ASCII("P"))');p.write_text(s)
p=dst/'scripts/build_cam0.ps1';s=p.read_text().replace('CAM1_GAIN8_E2_3_6_0','CAM1_RAW_E3_3_6_0').replace('CAM1 gain ceiling8x controlled candidate E2,20s original baseline; CAM0 unchanged','CAM1 pre-DDR native pixel patch E3; original sensor settings; no quality fix claimed');p.write_text(s)
print(dst)
