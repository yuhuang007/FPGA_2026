`timescale 1ns/1ps
module GRS_INST;wire GRSNET=1'b1;endmodule
module cam1_pixel_patch_tb;
 reg sc=0,vc=0,rst_n=0,ready=0,vs=0,de=0,result_valid=0;
 reg[15:0] rgb=0;reg[31:0] id=0,rid=0;reg[7:0] err=0;
 always #10 sc=~sc;always #13.888888889 vc=~vc;
 wire[639:0] page;
 cam1_pixel_patch #(.START_TICKS(20),.PAGE_TICKS(100)) dut(
  .sc(sc),.vc(vc),.rst_n(rst_n),.ready(ready),.vs(vs),.de(de),.rgb(rgb),
  .frame_id(id),.result_valid(result_valid),.result_id(rid),.result_errors(err),.page(page));
 function automatic[15:0] pixel(input integer f,y,x);
  pixel=(f*16'h1237)^(y*16'h531)^(x*16'h275);
 endfunction
 task automatic idle(input integer n);repeat(n) @(negedge vc);endtask
 task automatic frame(input integer f,input integer bad);
  begin
   vs=1;de=0;id=f;idle(20);vs=0;id=f+1;idle(20);
   for(integer y=0;y<720;y++) begin
    for(integer x=0;x<1280;x++) begin de=1;rgb=pixel(f,y,x);idle(1);end
    de=0;idle(520);
   end
   idle(20);result_valid=1;rid=f;err=bad;idle(1);result_valid=0;idle(30);
  end
 endtask
 integer pages=0,total=0,out;reg[639:0] old_page=0;reg[479:0] seen=0;
 reg[31:0] exported_crc=0;
 always @(negedge sc) if(page!=old_page) begin
  old_page=page;
  if(page[639:608]==32'h43315058) begin
   if(page[607:576]!=2 || page[575:544]!=32'h00010100 || page[543:512]!={16'd1120,16'd0}
      ||page[511:480]!={16'd16,16'd720} ||page[479:448]>=11520 || page[415:400]!=0)
    $fatal(1,"bad patch descriptor %h",page);
   for(integer i=0;i<page[399:384];i++) begin
    integer n;n=page[479:448]+i;
    if(page[383-i*16-:16]!==pixel(2,n/16,1120+n%16))
     $fatal(1,"DRM/pixel oracle offset%0d got%h",n,page[383-i*16-:16]);
   end
   if(!seen[page[479:448]/24]) begin
    $fdisplay(out,"C1PX %0160h",page);total+=page[399:384];pages++;
    seen[page[479:448]/24]=1;exported_crc=page[447:416];
   end
  end
 end
 initial begin
  out=$fopen("../reports/cam1_patch_pages.txt","w");
  #1;rst_n=0;idle(5);rst_n=1;ready=1;idle(50);
  frame(1,1);if(dut.frozen ||dut.rejected!=1) $fatal(1,"bad frame exported");
  frame(2,0);wait(dut.frozen);wait(pages==480);idle(40);
  if(total!=11520 || dut.written!=11520 ||dut.rejected!=1) $fatal(1,"coverage totals");
  // Further active video must not overwrite the accepted buffer/descriptor.
  repeat(100) begin de=1;rgb=16'hdead;idle(1);end de=0;ready=0;idle(50);
  if(dut.held_id!=2 ||dut.written!=11520 || !dut.frozen) $fatal(1,"frozen ownership");
  $fclose(out);
  $display("PASS native1280x720: vendor16DRM, 11520 exact RGB565 pixels across720rows,480pages, bad-frame rejection/recovery, frozen ownership, CRC=%h",exported_crc);
  $finish;
 end
 initial begin #100000000;$fatal(1,"patch deadline pages%0d",pages);end
endmodule
