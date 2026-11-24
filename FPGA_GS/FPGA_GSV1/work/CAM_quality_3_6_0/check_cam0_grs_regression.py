from pathlib import Path
import subprocess,os
r=Path.cwd();o=r/'work/CAM_quality_3_6_0/reports/front_grs_regression';s=r/'work/CAM_quality_3_6_0/source';v=Path('E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin');lib=Path('E:/XUEXI/FPGA_PDS/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation');env=os.environ.copy();env['PATH']=str(v)+';'+env['PATH']
units=['sim/line_ram_model.sv','rtl/capture/capture_pipe.v','rtl/reuse/video_capture_status.v','rtl/reuse/fram_buf.v','rtl/frame/m3_front_owner.v','rtl/reuse/frame_buffer_owner.v','rtl/reuse/wr_buf.v','rtl/reuse/wr_rd_ctrl_top.v','rtl/reuse/wr_cmd_trans.v','rtl/reuse/wr_ctrl.v','rtl/reuse/rd_ctrl.v','rtl/display/m31_rd_buf.v','rtl/display/m31_timing.v','rtl/network/m361_diag.v']
cmd=[str(v/'iverilog.exe'),'-g2012','-s','GRS_INST','-s','cam0_front30_tb','-y',str(lib),'-Y','.v','-o',str(o/'check.vvp'),str(o/'cam0_front30_grs_tb.sv'),str(o/'cmos_8_16bit_grs_fixture.v'),*[str(s/u) for u in units]]
a=subprocess.run(cmd,env=env,capture_output=True,text=True);(o/'compile.log').write_text(a.stdout+a.stderr);assert a.returncode==0,a.stderr
with (o/'simulation.log').open('w') as f:a=subprocess.run([str(v/'vvp.exe'),str(o/'check.vvp')],env=env,stdout=f,stderr=subprocess.STDOUT)
print('exit',a.returncode);print((o/'simulation.log').read_text()[-4000:]);raise SystemExit(a.returncode)
