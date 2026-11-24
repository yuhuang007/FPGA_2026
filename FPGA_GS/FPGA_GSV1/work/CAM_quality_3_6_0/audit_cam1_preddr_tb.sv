`timescale 1ns/1ps
module GRS_INST;wire GRSNET=1'b1;endmodule
module audit_cam1_preddr_tb;
 reg sc=0,pclk=0,rst=0,href=0,vs=0;reg[7:0] data=0;
 always #10 sc=~sc;always #6.944444444 pclk=~pclk;
 // Exactly the production top input staging; this is a stable digital stimulus,
 // not an analogue IO timing model or a substitute for pad setup/hold testing.
 reg[7:0] sampled;reg sh,sv;
 always @(posedge pclk) begin sampled<=data;sh<=href;sv<=vs;end
 wire vc,de,ovs,byte_bad;wire[15:0] rgb;
 cam3660_dvp dvp(.pclk(pclk),.rst_n(rst),.de_i(sh),.vs_i(sv),.pdata_i(sampled),
  .pixel_clk(vc),.de_o(de),.vs_o(ovs),.frame_bad(byte_bad),.pdata_o(rgb));
 wire running,rv;wire[31:0] oid,ot,rid;wire[7:0] errors;
 video_capture_status #(.SOURCE_ID(1),.CHECK_BYTE_ERRORS(1)) mon(
  .ref_clk(sc),.video_clk(vc),.rst_n(rst),.source_ready(rst),.video_vs(ovs),
  .video_de(de),.byte_frame_error(byte_bad),.pipeline_rst_n(running),
  .frame_open_id(oid),.frame_open_time(ot),.frame_result_valid(rv),
  .frame_result_id(rid),.frame_result_errors(errors));
 reg prev_raw_vs,closed_bad;
 always @(posedge vc or negedge rst) if(!rst) begin prev_raw_vs<=0;closed_bad<=0;end
 else begin prev_raw_vs<=ovs;if(ovs&&!prev_raw_vs) closed_bad<=byte_bad;end
 wire pvs,pde;wire[15:0] prgb;wire[31:0] pid,pt;wire[639:0] page;
 capture_pipe pipe(.clk(vc),.rst_n(running),.vs(ovs),.de(de),.rgb(rgb),
  .frame_id(oid),.frame_time(ot),.out_vs(pvs),.out_de(pde),.out_rgb(prgb),.out_id(pid),.out_time(pt));
 cam1_pixel_patch #(.START_TICKS(50),.PAGE_TICKS(200)) patch(
  .sc(sc),.vc(vc),.rst_n(rst),.ready(running),.vs(pvs),.de(pde),.rgb(prgb),
  .frame_id(pid),.result_valid(rv),.result_id(rid),.result_errors(errors|{7'd0,closed_bad}),.page(page));
 // Independent source oracle: dark row chroma, byte-sensitive walking bits,
 // alternating high/low bytes and nonrepeating row/column words in every frame.
 function automatic[15:0] pixel(input integer y,x);
  reg[4:0] r,b;reg[5:0] g;
  begin
   r=((y*7)^(x*3))&7;g=((y*11)^x)&15;b=((y*13)^(x*5))&7;
   case(y%4)
    0:pixel={r,g,b};
    1:pixel=16'h1<<(x%16);
    2:pixel=x[0]?16'h55aa:16'haa55;
    3:pixel=(y*16'h3517)^(x*16'h1739);
   endcase
  end
 endfunction
 task idle(input integer n);repeat(n) @(negedge pclk);endtask
 task send_frame;
  reg[15:0] v;
  begin
   vs=1;href=0;idle(7200);vs=0;idle(108001);
   for(integer y=0;y<720;y++) begin
    for(integer x=0;x<1280;x++) begin
     v=pixel(y,x);href=1;data=v[15:8];idle(1);data=v[7:0];idle(1);
    end
    href=0;data=8'he7;idle(1040+(y%2));
   end
   idle(172800);
  end
 endtask
 integer f=-1,x=0,y=0,count=0,verdicts=0,total_pixels=0;
 reg old_vs=0,old_de=0;
 always @(posedge vc) if(rst&&running) begin
  if(pvs&&!old_vs) begin
   if(f>=0 && (y!=720 ||count!=921600)) $fatal(1,"full dimensions %0d/%0d",y,count);
   f=f+1;x=0;y=0;count=0;
  end
  if(pde) begin
   if(pvs || prgb!==pixel(y,x)) $fatal(1,"production pixel f%0d y%0d x%0d got%h expected%h",f,y,x,prgb,pixel(y,x));
   x++;count++;total_pixels++;
  end
  if(old_de&&!pde) begin if(x!=1280)$fatal(1,"line boundary");x=0;y++;end
  old_vs=pvs;old_de=pde;
  if(rv) begin verdicts++;if(errors!=0||closed_bad)$fatal(1,"geometry/tuple error %h",errors);end
 end
 integer pages=0,export_pixels=0,outfile;reg[479:0] seen=0;reg[639:0] old_page=0;
 always @(negedge sc) if(page!=old_page) begin
  old_page=page;
  if(page[639:608]==32'h43315058) begin
   if(page[607:576]!=0 ||page[575:544]!=32'h00010000)$fatal(1,"export descriptor");
   for(integer j=0;j<page[399:384];j++) begin
    integer n;n=page[479:448]+j;
    if(page[383-j*16-:16]!==pixel(n/16,1120+n%16))$fatal(1,"export mismatch n%0d",n);
   end
   if(!seen[page[479:448]/24]) begin
    seen[page[479:448]/24]=1;pages++;export_pixels+=page[399:384];
    $fdisplay(outfile,"C1PX %0160h",page);
   end
  end
 end
 initial begin
  outfile=$fopen("audit_cam1_preddr_pages.txt","w");
  rst=1;#1;rst=0;idle(20);rst=1;idle(200);
  send_frame();send_frame();vs=1;href=0;idle(7200);
  wait(pages==480);idle(50);
  if(total_pixels!=1843200||verdicts!=2||export_pixels!=11520||!patch.frozen)$fatal(1,"totals %0d %0d %0d",total_pixels,verdicts,export_pixels);
  $fclose(outfile);
  $display("PASS production input flops -> cam3660_dvp -> video_capture_status -> capture_pipe -> vendor DRM strip: 2 full720 frames,1843200 independent pixels,11520 exact exported pixels,480pages; dark row chroma/walking16bits/55aa-aa55/row-column data; analogue pad timing NOT covered");$finish;
 end
 initial begin #100000000;$fatal(1,"audit timeout");end
endmodule
