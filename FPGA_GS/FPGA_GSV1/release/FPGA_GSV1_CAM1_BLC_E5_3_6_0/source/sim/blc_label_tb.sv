`timescale 1ns/1ps
module blc_label_tb;
 reg clk=0;always #5 clk=~clk;
 reg[10:0] x=0,y=0;reg[2:0] phase=7;wire area,pixel;
 cam1_blc_label dut(.clk(clk),.x(x),.y(y),.phase(phase),.area(area),.pixel(pixel));
 reg last_area=0,last_pixel=0;integer checked=0;
 task step(input[10:0] xx,yy,input[2:0] pp,input aa,px);begin
  @(negedge clk);x=xx;y=yy;phase=pp;
  @(posedge clk);#1;
  if(checked>0 && (area!==last_area || (last_area && pixel!==last_pixel)))
   $fatal(1,"label timing/bit mismatch area%b pixel%b expected%b/%b ch%h row%d col%d text%h bits%h",area,pixel,last_area,last_pixel,dut.ch,dut.row,dut.col,dut.text,dut.bits);
  last_area=aa;last_pixel=px;checked++;
 end endtask
 initial begin
  step(0,0,0,0,0);
  for(integer p=0;p<6;p++)begin
   step(12,84,p,1,1); // B of BLC
   step(17,84,p,1,0); // spacing after the5-column B
   step(44,84,p,1,(p==2||p==4||p==5)); // C/A/B/A/D/I at char4
   step(140,84,p,0,0);step(12,98,p,0,0);step(0,0,p,0,0);
  end
  step(0,0,0,0,0);$display("PASS BLC OSD label: A/B/AP/DONE glyphs and two-register area/pixel latency, outside-area exclusion");$finish;
 end
endmodule



