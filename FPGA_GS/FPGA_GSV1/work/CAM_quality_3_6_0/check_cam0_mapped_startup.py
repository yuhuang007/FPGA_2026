from pathlib import Path
import re,hashlib,json,subprocess,os
root=Path.cwd(); out=root/'work/CAM_quality_3_6_0/reports/front_mapped_startup';out.mkdir(exist_ok=True)
net=root/'work/CAM_quality_3_6_0/rear_pixels_source/build/CAM1_RAW_E3_3_6_0_20261024_203852_117/synthesize/fpga_gsv1_top_syn.vm'
s=net.read_text(); m=re.search(r'^module cmos_8_16bit\b.*?^endmodule',s,re.M|re.S);assert m
mapped=out/'cmos_8_16bit_mapped.v';mapped.write_text(m.group(0)+'\n')
(out/'source_identity.json').write_text(json.dumps({'mapped_source':str(net),'mapped_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),'extracted_module_sha256':hashlib.sha256(mapped.read_bytes()).hexdigest(),'reason':'Use actual synthesized GRS_EN=TRUE INIT=0 for stopped-clock pipeline; keep original geometry and publication expectations; no production RTL changed.'},indent=2))
src=root/'work/CAM_quality_3_6_0/source'; vbin=Path('E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin');lib=Path('E:/XUEXI/FPGA_PDS/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation')
units=['sim/cam0_front30_tb.sv','sim/line_ram_model.sv','rtl/capture/capture_pipe.v','rtl/reuse/video_capture_status.v','rtl/reuse/fram_buf.v','rtl/frame/m3_front_owner.v','rtl/reuse/frame_buffer_owner.v','rtl/reuse/wr_buf.v','rtl/reuse/wr_rd_ctrl_top.v','rtl/reuse/wr_cmd_trans.v','rtl/reuse/wr_ctrl.v','rtl/reuse/rd_ctrl.v','rtl/display/m31_rd_buf.v','rtl/display/m31_timing.v','rtl/network/m361_diag.v']
env=os.environ.copy();env['PATH']=str(vbin)+';'+env['PATH']
cmd=[str(vbin/'iverilog.exe'),'-g2012','-s','GRS_INST','-s','cam0_front30_tb','-y',str(lib),'-Y','.v','-o',str(out/'check.vvp'),str(mapped),*[str(src/u) for u in units]]
r=subprocess.run(cmd,env=env,capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
with (out/'simulation.log').open('w') as f:
 r=subprocess.run([str(vbin/'vvp.exe'),str(out/'check.vvp')],env=env,stdout=f,stderr=subprocess.STDOUT)
print('simulation exit',r.returncode);print((out/'simulation.log').read_text()[-4000:]);raise SystemExit(r.returncode)
