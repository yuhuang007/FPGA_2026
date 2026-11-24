`timescale 1ns/1ps
// Full 1280x720, 1892x740 timing, video42MHz / DDR100MHz.
// Both production owners consume the same source verdict and capture_pipe.
// Native command completion below is a bounded BFM, not electrical DDR proof.
module cam0_turnover_tb;
 reg vc=0,dc=0,sc=0,rst=0;
 always #11.9047619 vc=~vc;
 always #5 dc=~dc;
 always #10 sc=~sc;
 reg vs=0,de=0; wire running,verdict;wire[31:0] id,stamp,result_id;
 wire[7:0] errors; wire[255:0] snapshot;
 video_capture_status monitor(.ref_clk(sc),.video_clk(vc),.rst_n(rst),
 .source_ready(rst),.video_vs(vs),.video_de(de),.byte_frame_error(1'b0),
 .pipeline_rst_n(running),.snapshot(snapshot),.frame_open_id(id),.frame_open_time(stamp),
 .frame_result_valid(verdict),.frame_result_id(result_id),.frame_result_errors(errors));
 wire cvs,cde;wire[31:0] cid,ct;
 capture_pipe pipe(.clk(vc),.rst_n(running),.vs(vs),.de(de),.rgb(16'h5a37),
 .frame_id(id),.frame_time(stamp),.out_vs(cvs),.out_de(cde),.out_id(cid),.out_time(ct));
 reg sof=0;
 initial begin wait(rst);#730000;forever begin
 @(negedge dc);sof=1;@(negedge dc);sof=0;#16666640;
 end end
 wire[31:0] pub[0:1],bad[0:1],did[0:1];
 wire[1:0] wb[0:1],rb[0:1];
 wire[1:0] accepted;
 genvar g;
 generate for(g=0;g<2;g=g+1) begin: comparison
  wire wvs,wde,wrst,wi,ri,enabled,has;
  reg wreq=0,wdone=0;wire line_event;
  reg [1:0] lt=0;reg wd=0,lv=0;reg line_toggle=0;
  reg [8:0] latency=0;
  always @(posedge vc or negedge rst)
   if(!rst) begin wd<=0;line_toggle<=0;end
   else begin wd<=wde;if(wd&&!wde) line_toggle<=~line_toggle;end
  assign line_event=lt[1]!=lv;
  always @(posedge dc or negedge rst)
   if(!rst) begin lt<=0;lv<=0;wreq<=0;wdone<=0;latency<=0;end
   else begin
    lt<={lt[0],line_toggle};lv<=lt[1];wdone<=0;
    if(line_event) begin
     if(wreq||latency!=0) $fatal(1,"line BFM overlap");
     wreq<=1;
    end
    if(wi) begin wreq<=0;latency<=193;end //80 beats, gaps and tail
    else if(latency!=0) begin
     latency<=latency-1'b1;
     if(latency==1) wdone<=1;
    end
   end
  m3_front_owner #(.BLANKING_GRANT(g)) dut(
   .clk(dc),.rst_n(rst),.video_clk(vc),.pipeline_running(running),
   .video_vs(cvs),.video_de(cde),.video_id(cid),.video_time(ct),
   .result_valid(verdict),.result_id(result_id),.result_errors(errors),
   .writer_rst_n(wrst),.writer_vs(wvs),.writer_de(wde),.line_event(line_event),
   .write_request(wreq),.write_ready(1'b1),.write_done(wdone),.write_issue(wi),.write_bank(wb[g]),
   .output_sof(sof),.display_selected(1'b1),.read_request(1'b0),.read_ready(1'b1),.read_done(1'b0),
   .read_issue(ri),.read_bank(rb[g]),.read_enabled(enabled),.has_frame(has),
   .published_count(pub[g]),.rejected_count(bad[g]),.display_id(did[g]),
   .net_acquire(1'b0),.net_release(1'b0));
  assign accepted[g]=wvs;
  always @(posedge dc) if(rst && wi &&
   ((dut.have_reader && wb[g]==rb[g]) || (dut.pending && wb[g]==dut.pending_bank)))
    $fatal(1,"owner %0d overwrote pin",g);
  integer naccept=0;realtime t;
  always @(posedge vc) if(wvs) begin
   naccept++;
   $display("ACCEPT variant=%0d id=%0d blank=%0d t=%0t",g,cid,cvs,$time);
   if(!cvs || cde) $fatal(1,"grant accepted outside blanking");
  end
 end endgenerate
 task automatic idle(input integer cycles);repeat(cycles) @(negedge vc);endtask
 task automatic frame;
  integer y;
  begin
   vs=1;de=0;idle(2*1892);vs=0;idle(8*1892);
   for(y=0;y<720;y++) begin de=1;idle(1280);de=0;idle(1892-1280);end
   idle(10*1892);
  end
 endtask
 initial begin
  rst=1;#1;rst=0;#999;rst=1;idle(100);
  repeat(6) frame();vs=1;idle(2*1892);vs=0;idle(100);
  if(pub[0]!=3 || pub[1]!=6 || bad[0]!=0 || bad[1]!=0)
   $fatal(1,"cadence old=%0d new=%0d bad=%0d/%0d",pub[0],pub[1],bad[0],bad[1]);
  $display("PASS old SOF-only 3/6; blanking grant 6/6 full720; no malformed publication, reader pin protected");
  $finish;
 end
 initial begin #210000000;$fatal(1,"deadline");end
endmodule
