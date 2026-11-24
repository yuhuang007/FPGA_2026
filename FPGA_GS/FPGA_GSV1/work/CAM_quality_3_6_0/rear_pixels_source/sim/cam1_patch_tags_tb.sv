`timescale 1ns/1ps
module GRS_INST;wire GRSNET=1;endmodule
module cam1_patch_tags_tb;
 reg sc=0,vc=0,rst=0,vs=0,de=0;reg[15:0] rgb=0;
 always #10 sc=~sc;always #13.888888889 vc=~vc;
 wire running,rv;wire[31:0] open_id,open_time,result_id;wire[7:0] errors;
 video_capture_status #(.SOURCE_ID(1),.H_ACTIVE(4),.V_ACTIVE(3)) monitor(
  .ref_clk(sc),.video_clk(vc),.rst_n(rst),.source_ready(rst),.video_vs(vs),.video_de(de),
  .pipeline_rst_n(running),.frame_open_id(open_id),.frame_open_time(open_time),
  .frame_result_valid(rv),.frame_result_id(result_id),.frame_result_errors(errors));
 wire pvs,pde;wire[15:0] prgb;wire[31:0] pid,pt;
 capture_pipe pipe(.clk(vc),.rst_n(running),.vs(vs),.de(de),.rgb(rgb),
  .frame_id(open_id),.frame_time(open_time),.out_vs(pvs),.out_de(pde),.out_rgb(prgb),.out_id(pid),.out_time(pt));
 wire[639:0] page;
 cam1_pixel_patch #(.START_TICKS(10),.PAGE_TICKS(100),.X0(1),.Y0(0),.WIDTH(2),.HEIGHT(3)) dut(
  .sc(sc),.vc(vc),.rst_n(rst),.ready(running),.vs(pvs),.de(pde),.rgb(prgb),
  .frame_id(pid),.result_valid(rv),.result_id(result_id),.result_errors(errors),.page(page));
 task idle(input integer n);repeat(n) @(negedge vc);endtask
 integer f,y,x;
 initial begin
  #1;rst=0;idle(10);rst=1;idle(100);
  for(f=0;f<2;f++) begin
   vs=1;de=0;idle(20);vs=0;idle(20);
   for(y=0;y<3;y++) begin
    for(x=0;x<4;x++) begin de=1;rgb=f*100+y*4+x;idle(1);end
    de=0;idle(8);
   end
   idle(20);
  end
  wait(page[639:608]==32'h43315058);
  if(page[607:576]!=0 || dut.held_id!=0 || page[399:384]!=6) $fatal(1,"real opening/result tag mismatch");
  for(integer i=0;i<6;i++)
   if(page[383-i*16-:16]!==16'((i/2)*4+1+i%2)) $fatal(1,"production tuple pixel alignment");
  $display("PASS real video_capture_status + capture_pipe: VS opening tag0 retained despite active-pixel tag1; matching verdict closes frame; six exact pixels, no image control feedback");$finish;
 end
 initial begin #1000000;$fatal(1,"real-tag deadline held%0d result%0d frozen%b",dut.held_id,result_id,dut.frozen);end
endmodule
