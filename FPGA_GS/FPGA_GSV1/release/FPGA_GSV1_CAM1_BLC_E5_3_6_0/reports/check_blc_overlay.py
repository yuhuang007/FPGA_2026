"""Exact retiming equivalence of changed output slice; no video algorithm test."""
from pathlib import Path
import os,subprocess
r=Path(__file__).resolve().parent;s=r/'rear_blc_source'
first=s/'build/CAM1_BLC_E5_3_6_0_20261025_131849_467'
header='''`timescale 1ns/1ps
module NAME #(parameter PROCESSING_ENABLE=1)(input clk,input[23:0]processed_rgb,
 input phs,pvs,pde,pimage,input[10:0]px,py,input[2:0]selected_view,selected_mode,diagnostic_phase,
 input hint_visible,input[3:0]hint_code,show_video,input[2:0]feedback,
 output reg hs_out,vs_out,de_out,output reg[23:0]rgb_out);
'''
mods=[]
for name,path in [('overlay_before',first/'rtl/display/m31_video_output.v'),('overlay_after',s/'rtl/display/m31_video_output.v')]:
 text=path.read_text(encoding='utf-8-sig');tail=text[text.index('    wire osd_area,osd_pixel;'):]
 mods.append(header.replace('NAME',name)+tail)
tb='''
module blc_overlay_tb;
 reg clk=0;always #3.367 clk=~clk;
 reg[23:0]rgb=0;reg hs=0,vs=0,de=0,image=0;reg[10:0]x=0,y=0;
 reg[2:0]view=0,mode=0,phase=7,feedback=0;reg hint=0;reg[3:0]code=0,good=15;
 wire[26:0]old_out,new_out;reg[26:0]history;
 overlay_before a(.clk(clk),.processed_rgb(rgb),.phs(hs),.pvs(vs),.pde(de),.pimage(image),.px(x),.py(y),
 .selected_view(view),.selected_mode(mode),.diagnostic_phase(phase),.hint_visible(hint),.hint_code(code),
 .show_video(good),.feedback(feedback),.hs_out(old_out[26]),.vs_out(old_out[25]),.de_out(old_out[24]),.rgb_out(old_out[23:0]));
 overlay_after b(.clk(clk),.processed_rgb(rgb),.phs(hs),.pvs(vs),.pde(de),.pimage(image),.px(x),.py(y),
 .selected_view(view),.selected_mode(mode),.diagnostic_phase(phase),.hint_visible(hint),.hint_code(code),
 .show_video(good),.feedback(feedback),.hs_out(new_out[26]),.vs_out(new_out[25]),.de_out(new_out[24]),.rgb_out(new_out[23:0]));
 initial begin
  for(integer i=0;i<12000;i++)begin
   @(negedge clk);
   rgb=$random;hs=(i%19==0);vs=(i%431==0);de=(i%11!=0);image=(i%7!=0);
   view=(i/900)%5;mode=(i/400)%6;phase=(i/100)%6;feedback=(i/67)%6;hint=i%2;code=(i/97)%12;good=i/51;
   case((i/256)%5)
    0:begin x=12+i%256;y=12+(i/16)%16;end
    1:begin x=12+i%128;y=84+(i/8)%14;end
    2:begin x=12+i%256;y=1052+(i/16)%16;end
    3:begin x=972+i%256;y=64+(i/16)%16;end
    4:begin x=(i*31)%1920;y=(i*7)%1080;end
   endcase
   @(posedge clk);#1;
   if(i>8 && new_out!==history)$fatal(1,"output retiming i%0d got%h expected%h",i,new_out,history);
   history=old_out;
  end
  $display("PASS12000cycles exact one-cycle retiming of RGB/HS/VS/DE, real Chinese font and E5 labels, viewport/mode/blanking/alarm/source-invalid boundaries; no clock/format change");$finish;
 end
endmodule
'''
(s/'sim/blc_overlay_tb.sv').write_text(''.join(mods)+tb)
env=dict(os.environ);env['PATH']='E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin;'+env['PATH']
cmd=['E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin/iverilog.exe','-g2012','-s','blc_overlay_tb','-o',str(r/'reports/blc_overlay.vvp'),str(s/'sim/blc_overlay_tb.sv')]
cmd += [str(s/'rtl/display'/f) for f in ('m31_osd.v','m31_text.v','cam1_blc_label.v')]
p=subprocess.run(cmd,capture_output=True,text=True,env=env);assert p.returncode==0,p.stderr
p=subprocess.run(['E:/zhoumian/FPGA/tmp/v5_tools/ucrt64/bin/vvp.exe',str(r/'reports/blc_overlay.vvp')],capture_output=True,text=True,env=env)
(r/'reports/blc_overlay.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr);assert p.returncode==0

