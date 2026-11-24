`timescale 1ns/1ps
module cam1_probe_bars_tb;
 reg clk=0;always #13.8888889 clk=~clk;
 reg rst=0,enable=0,vs=0,de=0;reg[15:0] rgb=0;
 wire[15:0] actual;wire active;
 cam1_probe_bars dut(.clk(clk),.rst_n(rst),.enable(enable),.vs(vs),.de(de),.rgb(rgb),.out_rgb(actual),.active(active));
 function automatic[15:0] expected(input integer x);
  case(x/160)
   0:expected=16'hffff;1:expected=16'hffe0;2:expected=16'h07ff;3:expected=16'h07e0;
   4:expected=16'hf81f;5:expected=16'hf800;6:expected=16'h001f;7:expected=0;
  endcase
 endfunction
 integer f,y,x,checks=0;
 initial begin
  rst=1;#1;rst=0;#999;rst=1;
  for(f=0;f<3;f++) begin
   @(negedge clk);vs=1;de=0;repeat(20) @(negedge clk);vs=0;
   for(y=0;y<720;y++) begin
    for(x=0;x<1280;x++) begin
     rgb=(x*37)^(y*113);de=1;#1;
     if(actual!==(f==1?expected(x):rgb)) $fatal(1,"bar/pass-through f%0d y%0d x%0d got%h",f,y,x,actual);
     checks++;@(negedge clk);
    end
    de=0;repeat(5) @(negedge clk);
    if(y==99) enable=f==0; // change during active frame, commit NEXT VS only
   end
  end
  $display("PASS %0d pixels:3 full720 frames, native RGB565 8 bars, exact passthrough, first/last pixel and VS-only CDC mode commit",checks);
  $finish;
 end
endmodule
