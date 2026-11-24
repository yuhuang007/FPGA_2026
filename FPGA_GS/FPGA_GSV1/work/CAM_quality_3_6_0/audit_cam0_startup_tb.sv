`timescale 1ns/1ps
module GRS_INST; wire GRSNET=1'b1; endmodule
module audit_cam0_startup_tb;
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

 integer edges=0;
 always @(posedge vc) begin
  edges++;
  if(edges<=12) begin
   $display("BEFORE edge=%0d ready=%b vs=%b sof=%b de=%b errors=%b have=%b",edges,monitor.ready_video,ivs,monitor.sof,ide,monitor.errors,monitor.have_frame);
   $strobe("AFTER edge=%0d ready=%b de=%b errors=%b have=%b",edges,monitor.ready_video,ide,monitor.errors,monitor.have_frame);
  end
 end
 initial begin
  rst=1;#1;rst=0;#999;rst=1;repeat(100)@(negedge bc);
  vs=1;repeat(200)@(negedge bc);
  if(monitor.errors!==8'b00000x00)$fatal(1,"startup trace does not explain error");
  $display("PASS isolated cause: stopped legacy pixel clock leaves de_o uninitialised; first accepted SOF sees X DE and latches error bit2; no claim of production valid-frame loss");$finish;
 end
endmodule
