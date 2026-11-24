`timescale 1ns/1ps
// Passive native RGB565 strip BEFORE DDR, scaling, filtering and OSD.
// Freeze one geometrically accepted frame; no signal feeds the video pipeline.
// C1PX pages are repeated over the existing UART; frame ID + whole-strip CRC
// prevent incomplete/mixed dumps from being presented as an image.
module cam1_blc_strip #(
 parameter START_TICKS=1000000000,PAGE_TICKS=2500000,
 parameter X0=1120,Y0=0,WIDTH=16,HEIGHT=720
)(input sc,vc,rst_n,ready,vs,de,input[15:0] rgb,input[31:0] frame_id,
 input request_toggle,advance,output complete,output complete_token,output[31:0] captured_id,
 input result_valid,input[31:0] result_id,input[7:0] result_errors,
 output reg[639:0] page);
 localparam WORDS=WIDTH*HEIGHT;
 localparam[15:0] ROI_X=X0,ROI_Y=Y0,ROI_WIDTH=WIDTH,ROI_HEIGHT=HEIGHT;
 function[31:0] crc_byte(input[31:0] value,input[7:0] octet);
  reg[31:0] c;integer i;
  begin c=value;for(i=0;i<8;i=i+1)
   c=(c[0]^octet[i])?((c>>1)^32'hedb88320):(c>>1);
   crc_byte=c;end
 endfunction
 wire request=request_toggle;
 (* ASYNC_REG="TRUE" *) reg[1:0] request_v,done_s;
 reg capture,frozen,vs_d,de_d,have_id;reg seen_request,frozen_token;
 reg[10:0] x,y;reg[14:0] written;
 reg[31:0] held_id,crc,held_crc;
 reg[7:0] rejected;
 wire in_roi=x>=X0 && x<X0+WIDTH && y>=Y0 && y<Y0+HEIGHT;
 wire we=capture && ready && !vs && de && in_roi && written<WORDS;
 wire[15:0] ram_data;reg[13:0] read_address;
 reg[2:0] state;
 cam1_patch_ram memory(.wc(vc),.we(we),.wa(written[13:0]),.wd(rgb),
  .rc(sc),.re(state==2),.ra(read_address),.qd(ram_data));
 always @(posedge vc or negedge rst_n) if(!rst_n) begin
  request_v<=0;capture<=0;frozen<=0;vs_d<=0;de_d<=0;have_id<=0;
  x<=0;y<=0;written<=0;held_id<=0;crc<=32'hffffffff;held_crc<=0;rejected<=0;
  seen_request<=0;frozen_token<=0;
 end else begin
  request_v<={request_v[0],request};vs_d<=vs;de_d<=de;
  if(request_v[1]!=seen_request) begin
   seen_request<=request_v[1];frozen<=0;capture<=0;have_id<=0;
   written<=0;x<=0;y<=0;rejected<=0;
  end else if(!frozen) begin
   if(!ready) capture<=0;
   else if(!capture && vs && !vs_d && seen_request!=frozen_token) begin
    // capture_pipe's ID is an OPENING tag at VS. The monitor advertises the
    // *next* opening tag during active pixels, so never latch it at first DE.
    capture<=1;have_id<=1;held_id<=frame_id;x<=0;y<=0;written<=0;crc<=32'hffffffff;
   end else if(capture) begin
    if(de && !vs) begin
     x<=x+1'b1;
    end else x<=0;
    if(de_d && !de) y<=y+1'b1;
    if(we) begin
     written<=written+1'b1;crc<=crc_byte(crc_byte(crc,rgb[15:8]),rgb[7:0]);
    end
    if(have_id && result_valid && result_id==held_id) begin
     capture<=0;
     if(result_errors==0 && written==WORDS) begin frozen<=1;frozen_token<=seen_request;held_crc<=~crc;end
     else if(rejected!=255) rejected<=rejected+1'b1;
    end
   end
  end
 end
 // Bundled descriptor and RAM remain frozen before this two-stage indication
 // crosses to sc, and for the remainder of the download's lifetime.
 reg[31:0] page_timer,offset,id_s,crc_s;
 reg[7:0] rejected_s;reg[4:0] item;reg[383:0] assembling;
 reg[15:0] valid_count;reg first_page,token_s;
 assign complete=done_s[1] && state!=0;
 assign complete_token=token_s;
 assign captured_id=id_s;
 always @(posedge sc or negedge rst_n) if(!rst_n) begin
  done_s<=0;state<=0;page_timer<=0;offset<=0;id_s<=0;crc_s<=0;
  rejected_s<=0;item<=0;assembling<=0;valid_count<=0;read_address<=0;page<=0;first_page<=1;token_s<=0;
 end else begin
  done_s<={done_s[0],frozen};
  if(!done_s[1]) begin state<=0;offset<=0;page<=0;first_page<=1;end
  else case(state)
   0:if(done_s[1]) begin
    id_s<=held_id;crc_s<=held_crc;rejected_s<=rejected;token_s<=frozen_token;state<=1;page_timer<=0;
   end
   1:if(first_page || advance) begin
    page_timer<=0;item<=0;assembling<=0;read_address<=offset[13:0];
    valid_count<=WORDS-offset>=24?16'd24:WORDS-offset;state<=2;
   end else page_timer<=page_timer+1'b1;
   2:state<=3; // Actual synchronous DRM read; no zero-latency assumption.
   3:begin
    assembling<={assembling[367:0],item<valid_count?ram_data:16'd0};
    if(item==23) state<=4;
    else begin item<=item+1'b1;read_address<=read_address+1'b1;state<=2;end
   end
   4:begin
    page<={32'h43315058,id_s,16'd1,rejected_s,8'd0,
      ROI_X,ROI_Y,ROI_WIDTH,ROI_HEIGHT,offset,crc_s,16'd0,valid_count,assembling};
    offset<=offset+24>=WORDS?32'd0:offset+24;first_page<=0;state<=1;
   end
   default:state<=0;
  endcase
 end
endmodule

// Eight2048-word banks, each made of two9-bit DRM primitives. Only16 useful
// bits/pixel. Two unrelated clock ports; sys never reads a live write buffer.
module cam1_patch_ram(input wc,we,input[13:0] wa,input[15:0] wd,
 input rc,re,input[13:0] ra,output[15:0] qd);
 wire[15:0] q[0:7];reg[2:0] bank;
 always @(posedge rc) bank<=ra[13:11];
 genvar b,k;
 generate for(b=0;b<8;b=b+1) begin: banks
  for(k=0;k<2;k=k+1) begin: octets
   wire[17:0] qb;
   GTP_DRM18K #(.GRS_EN("FALSE"),.DATA_WIDTH_A(9),.DATA_WIDTH_B(9),
    .WRITE_MODE_A("NORMAL_WRITE"),.DOA_REG(0),.DOB_REG(0),
    .RST_TYPE("ASYNC"),.RAM_MODE("TRUE_DUAL_PORT"),.SIM_DEVICE("LOGOS")) ram(
    .CLKA(wc),.CEA(we && wa[13:11]==b),.WEA(we && wa[13:11]==b),
    .ADDRA({wa[10:0],1'b0,2'b11}),.ADDRA_HOLD(1'b0),.DIA({10'd0,wd[k*8+:8]}),
    .CSA(3'd0),.DOA(),.ORCEA(1'b0),.RSTA(1'b0),
    .CLKB(rc),.CEB(re && ra[13:11]==b),.WEB(1'b0),.ADDRB({ra[10:0],1'b0,2'b11}),
    .ADDRB_HOLD(1'b0),.DIB(18'd0),.CSB(3'd0),.DOB(qb),.ORCEB(1'b0),.RSTB(1'b0),.WWCONF());
   assign q[b][k*8+:8]=qb[7:0];
  end
 end endgenerate
 assign qd=q[bank];
endmodule
