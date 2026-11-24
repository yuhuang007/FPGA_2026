`timescale 1ns/1ps
module map_health_tb;
 reg c=0;always #5 c=~c;reg[3:0] ph=15,sel=0,req=0;wire[3:0] lh,ps,pr;wire[63:0] lp;
 m361_source_map map(.physical_rgb(64'h4444333322221111),.physical_de(4'b1111),.physical_health(ph),.logical_rgb(lp),.logical_health(lh),.logical_de(),.logical_selected(sel),.logical_request(req),.physical_selected(ps),.physical_request(pr));
 reg[10:0] x=340,y=340;reg[2:0]view=0;wire area,pixel;
 m31_osd osd(.clk(c),.x(x),.y(y),.view(view),.mode(3'd0),.hint_visible(1'b0),.hint_code(4'd0),.video_good(lh),.feedback(3'd0),.area(area),.pixel(pixel));
 integer i,physical;integer expected;
 initial begin
 #1;if(lp!=64'h2222111133334444)$fatal(1,"pattern map");
 for(i=0;i<4;i=i+1)begin
  case(i)0:physical=3;1:physical=2;2:physical=0;3:physical=1;endcase
  ph=15^(1<<physical);sel=1<<i;req=sel;view=i;#1;
  if(lh!=(15^(1<<i))||ps!=(1<<physical)||pr!=ps)$fatal(1,"health/request map");
  expected=i==0?9:(i==1?6:7);if(osd.text_id!=expected)$fatal(1,"wrong outage label view=%d text=%d",view,osd.text_id);
  x=16;y=16;#1;expected=i==3?8:i+1;if(osd.text_id!=expected)$fatal(1,"wrong title");x=340;y=340;
 end
 $display("MAP_HEALTH_PASS inverse_requests=1 one_source_outage=1 correct_titles=1 no_CAM0_fallback=1");$finish;
 end
endmodule
