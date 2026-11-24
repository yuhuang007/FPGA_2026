`timescale 1ns/1ps
module overlay_before #(parameter PROCESSING_ENABLE=1)(input clk,input[23:0]processed_rgb,
 input phs,pvs,pde,pimage,input[10:0]px,py,input[2:0]selected_view,selected_mode,diagnostic_phase,
 input hint_visible,input[3:0]hint_code,show_video,input[2:0]feedback,
 output reg hs_out,vs_out,de_out,output reg[23:0]rgb_out);
    wire osd_area,osd_pixel;
    m31_osd osd(.clk(clk),.x(px),.y(py),.view(selected_view),.mode(PROCESSING_ENABLE ? selected_mode : 3'd0),
        .diagnostic_phase(diagnostic_phase),.hint_visible(hint_visible),.hint_code(hint_code),.video_good(show_video),.feedback(feedback),
        .area(osd_area),.pixel(osd_pixel));
    reg [29:0] overlay_delay[0:1];
    wire dhs,dvs,dde,dimage,alarm;wire [23:0] drgb;
    always @(posedge clk) begin
      overlay_delay[0]<={1'b0,(feedback>=3 && py>=1052),pimage,pde,phs,pvs,processed_rgb};
      overlay_delay[1]<=overlay_delay[0];
    end
    assign {alarm,dimage,dde,dhs,dvs,drgb}=overlay_delay[1][28:0];
    always @(posedge clk) begin
        vs_out<=dvs;hs_out<=dhs;de_out<=dde;
        if(dde && osd_area) rgb_out<=osd_pixel ? (alarm ? 24'hff3030 : 24'hffff00) : 0;
        else if(dimage) rgb_out<=drgb;
        else rgb_out<=0;
    end

endmodule
`timescale 1ns/1ps
module overlay_after #(parameter PROCESSING_ENABLE=1)(input clk,input[23:0]processed_rgb,
 input phs,pvs,pde,pimage,input[10:0]px,py,input[2:0]selected_view,selected_mode,diagnostic_phase,
 input hint_visible,input[3:0]hint_code,show_video,input[2:0]feedback,
 output reg hs_out,vs_out,de_out,output reg[23:0]rgb_out);
    wire osd_area,osd_pixel;
    m31_osd osd(.clk(clk),.x(px),.y(py),.view(selected_view),.mode(PROCESSING_ENABLE ? selected_mode : 3'd0),
        .diagnostic_phase(diagnostic_phase),.hint_visible(hint_visible),.hint_code(hint_code),.video_good(show_video),.feedback(feedback),
        .area(osd_area),.pixel(osd_pixel));
    // E5 STA repair: register composed OSD before high-fanout RGB output.
    // Delay every matching raster/pixel/colour attribute by the same cycle.
    reg osd_area_d,osd_pixel_d;
    reg [29:0] overlay_delay[0:2];
    wire dhs,dvs,dde,dimage,alarm;wire [23:0] drgb;
    always @(posedge clk) begin
      overlay_delay[0]<={1'b0,(feedback>=3 && py>=1052),pimage,pde,phs,pvs,processed_rgb};
      overlay_delay[1]<=overlay_delay[0];
      overlay_delay[2]<=overlay_delay[1];
      osd_area_d<=osd_area;osd_pixel_d<=osd_pixel;
    end
    assign {alarm,dimage,dde,dhs,dvs,drgb}=overlay_delay[2][28:0];
    always @(posedge clk) begin
        vs_out<=dvs;hs_out<=dhs;de_out<=dde;
        if(dde && osd_area_d) rgb_out<=osd_pixel_d ? (alarm ? 24'hff3030 : 24'hffff00) : 0;
        else if(dimage) rgb_out<=drgb;
        else rgb_out<=0;
    end

endmodule


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
