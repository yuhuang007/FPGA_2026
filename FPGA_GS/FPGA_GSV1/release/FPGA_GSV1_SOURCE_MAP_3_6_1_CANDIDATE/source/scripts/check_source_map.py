from pathlib import Path
import os,sys,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];B=Path('E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin');L=Path('E:/XUEXI/FPGA_PDS/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation');os.environ['PATH']=str(B)+os.pathsep+os.environ['PATH']
reuse=['rtl/reuse/'+n+'.v' for n in ['wr_rd_ctrl_top','wr_cmd_trans','wr_ctrl','rd_ctrl']]
cases={
'network':['rtl/network/m3_mac.v','rtl/network/m3_net_core.v','rtl/network/m3_right_store.v','rtl/network/m3_upload.v','rtl/display/m31_rd_buf.v','sim/line_ram_model.sv','sim/m33_packet_model.sv','rtl/frame/dual_ddr_arbiter.v']+reuse,
'health':['rtl/display/m361_source_map.v','rtl/display/m31_osd.v','rtl/display/m31_text.v'],
'event':['rtl/network/m3_net_core.v'],
'cancel':['rtl/network/m3_upload.v','sim/line_ram_model.sv'],
'owner':['rtl/network/m3_right_store.v','rtl/display/m31_rd_buf.v','sim/line_ram_model.sv']+reuse,
'display':['rtl/display/'+n+'.v' for n in ['m361_source_map','m31_video_output','m31_timing','m31_rd_buf','m31_osd','m1_display_gain']]+['sim/line_ram_model.sv','sim/m32_text_model.sv','rtl/frame/dual_ddr_arbiter.v']+reuse,
'keys':['rtl/board/m3_keys.v','rtl/network/m3_network.v','rtl/display/m3_view_select.v','rtl/display/m1_hint_cdc.v'],
}
name=sys.argv[1];top='map_'+name+'_tb';files=['sim/'+top+'.sv']+cases[name];out=R/'reports'/('check_'+name);out.mkdir(exist_ok=True)
hashes={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files};
if name=='network':
 original=(R/'rtl/network/m3_net_core.v').read_text();core=original.split('module m33_packet_ram(',1)[0]
 adapted=out/'core_packet_memory_model.v';adapted.write_text(core+"module m33_packet_ram(input clk,we,input [5:0] wa,ra,input [255:0] wd,output reg [255:0] rd); reg [255:0] m[0:63];always @(posedge clk)begin if(we)m[wa]<=wd;rd<=m[ra];end endmodule\n")
 files[files.index('rtl/network/m3_net_core.v')]=str(adapted)
res={'case':name,'pass':False,'board_measured':False,'input_hashes':hashes}
for stage,cmd in [('compile',[B/'iverilog.exe','-g2012','-s',top,'-y',L,'-Y','.v','-o',out/'run.vvp',*[R/f for f in files]]),('run',[B/'vvp.exe','-i',out/'run.vvp'])]:
 with (out/(stage+'.log')).open('wb') as fp:c=subprocess.run([str(x) for x in cmd],stdout=fp,stderr=subprocess.STDOUT,cwd=out,timeout=3600).returncode
 if c:res['failed_stage']=stage;break
else:res['pass']='MAP_'+name.upper()+'_PASS' in (out/'run.log').read_text()
res['inputs_unchanged']=all(hashlib.sha256((R/f).read_bytes()).hexdigest()==h for f,h in hashes.items());(out/'result.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2),flush=True)
if not res['pass']:print((out/('compile.log' if res.get('failed_stage')=='compile' else 'run.log')).read_text(errors='replace')[-3000:])
raise SystemExit(0 if res['pass'] and res['inputs_unchanged'] else 1)
