`timescale 1ns/1ps
module GRS_INST; wire GRSNET=1'b1; endmodule
module audit_cam0_geometry_tb;
 reg bc=0,dc=0,sc=0,pc=0,rst=0;
 always #5.952380952 bc=~bc; // actual byte72MHz, not accelerated geometry
 
 always #10 sc=~sc;
 // // actual1080p60
 reg vs=0,href=0;reg [7:0] octet=0;
 wire vc,ivs,ide,byte_bad;wire [15:0] rgb;
 reg[7:0] od=0;reg hd=0,vd=0;
 always @(posedge bc) begin od<=octet;hd<=href;vd<=vs;end
 wire[15:0] packed_rgb;
 cmos_8_16bit gearbox(.pclk(bc),.rst_n(rst),.de_i(hd),.vs_i(vd),.pdata_i(od),
  .pixel_clk(vc),.de_o(ide),.pdata_o(packed_rgb));
 assign ivs=vd;assign byte_bad=0;
 assign rgb={packed_rgb[4:0],packed_rgb[10:5],packed_rgb[15:11]};
 wire running,result_valid;wire [31:0] open_id,open_time,result_id;
 wire [7:0] errors;wire [255:0] status;
 video_capture_status #(.SOURCE_ID(0)) monitor(.ref_clk(sc),.video_clk(vc),.rst_n(rst),
  .source_ready(rst),.video_vs(ivs),.video_de(ide),.pipeline_rst_n(running),
  .snapshot(status),.frame_open_id(open_id),.frame_open_time(open_time),
  .frame_result_valid(result_valid),.frame_result_id(result_id),.frame_result_errors(errors));
 reg vs_old=0,closed_bad=0;
 always @(posedge vc or negedge rst) if(!rst) begin vs_old<=0;closed_bad<=0;end
  else begin vs_old<=ivs;if(ivs&&!vs_old) closed_bad<=byte_bad;end
 wire cvs,cde;wire [15:0] crgb;wire [31:0] cid,ctime;
 capture_pipe pipe(.clk(vc),.rst_n(running),.vs(ivs),.de(ide),.rgb(rgb),
  .frame_id(open_id),.frame_time(open_time),.out_vs(cvs),.out_de(cde),.out_rgb(crgb),
  .out_id(cid),.out_time(ctime));
 function automatic [15:0] pattern(input integer f,yy,xx);
  pattern=(f*16'h2937)^((719-yy)*16'h317) ^ ((1279-xx)*16'h65);
 endfunction
 task automatic idle(input integer n);repeat(n) @(negedge bc);endtask
 task automatic frame(input integer number);
  integer yy,xx,w,tag;reg [15:0] value;
  begin
   tag=open_id;vs=1;href=0;idle(7568);vs=0; //2*HTS SYS cycles
   idle(3784*8); // total blank16 rows before active
   for(yy=0;yy<720;yy=yy+1) begin
    w=(number==5 && yy==311) ? 1279:1280;
    for(xx=0;xx<w;xx=xx+1) begin
     value=pattern(tag,yy,xx);value={value[4:0],value[10:5],value[15:11]};href=1;octet=value[15:8];idle(1);
     octet=value[7:0];idle(1);
    end
    href=0;idle(3784-2*w);
   end
   idle(3784*10); // exactly1800*800 SYS cycles,40ms per new input
  end
 endtask

 integer nresults=0;
 always @(posedge vc) if(rst) begin
  if(result_valid) begin
   nresults++;
   $display("VERDICT id=%0d errors=%02h monitor_good=%0d monitor_bad=%0d previous_rows=%0d",result_id,errors,monitor.good_frames,monitor.bad_frames,monitor.reported_rows);
   $fflush();
  end
  if(monitor.close_line && monitor.columns!=1280)
   $display("SHORT_LINE active_id=%0d row=%0d cols=%0d errors=%02h",monitor.frame_id,monitor.rows,monitor.columns,monitor.errors);
 end
 initial begin
  rst=1;#1;rst=0;#999;rst=1;idle(100);
  for(integer f=1;f<=6;f++)frame(f);
  vs=1;idle(7568);vs=0;idle(6000);
  $display("GEOMETRY_TOTALS results=%0d good=%0d bad=%0d status=%h",nresults,monitor.good_frames,monitor.bad_frames,status);
  $finish;
 end
endmodule
