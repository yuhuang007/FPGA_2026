`timescale 1ns/1ps
module blc_uart_tb;
reg sys_clk=0,rstn_out=0;always #10 sys_clk=~sys_clk;
wire diagnostic_take,tx;reg[3:0] blc_slot=0;
reg[639:0] cam1_pixel_page=0;wire[639:0] blc_pre_page={32'h43314252,608'd1};
wire[639:0] blc_post_page={32'h43314252,608'd2},blc_status_page={32'h43314254,608'd3};
wire blc_export=1;integer offset=0,expected=0,lines=0,bytes=0;reg[7:0] ch;
always @(posedge sys_clk)if(!rstn_out)begin blc_slot<=0;offset<=0;end
else if(diagnostic_take)begin
 blc_slot<=blc_slot+1'b1;
 if(blc_slot>=3)offset<=offset+1;
end
always @(posedge sys_clk)cam1_pixel_page<={32'h43315058,32'd123,32'h00010000,32'h04600000,32'h001002d0,offset[31:0],448'd0};
    reg [639:0] blc_diag_page;
    always @(posedge sys_clk) begin
      if(!blc_export || blc_slot==2) blc_diag_page<=blc_status_page;
      else if(blc_slot==0) blc_diag_page<=blc_pre_page;
      else if(blc_slot==1) blc_diag_page<=blc_post_page;
      else blc_diag_page<=cam1_pixel_page;
    end

m361_uart_hex #(.TICKS(9000),.BAUD_DIV(2),.REVISION_ASCII("B")) serial(
 .clk(sys_clk),.rst_n(rstn_out),.values({640'd0,blc_diag_page}),.tx(tx),.snapshot_tick(diagnostic_take));
always @(posedge sys_clk)if(diagnostic_take)begin
 if(blc_slot>=3)begin
  if(blc_diag_page[639:608]!==32'h43315058||blc_diag_page[479:448]!==expected)
   $fatal(1,"mux/take missed page %0d",expected);
  expected=expected+1;
 end
end
integer f;
initial begin f=$fopen("blc_uart_lines.txt","w");#80;rstn_out=1;end
initial forever begin
 @(negedge tx);#60;
 for(integer i=0;i<8;i++)begin ch[i]=tx;#40;end
 if(tx!==1)$fatal(1,"UART stop");$fwrite(f,"%c",ch);bytes++;
 if(bytes==369)begin bytes=0;lines++;end
 if(lines==600)begin if(expected!=486)$fatal(1,"real snapshot count %0d",expected);
 $fclose(f);$display("PASS actual UART 600 complete lines;486 sequential pixel pages and114 metadata pages; no slot skipped");$finish;end
end
initial begin #120000000;$fatal(1,"UART deadline");end
endmodule
