from pathlib import Path
r=Path(__file__).resolve().parent;s=r/'rear_blc_source'
# Retain actual DVP, geometry monitor, capture_pipe and vendor DRM from the
# previous pixel oracle. Only the diagnostic trigger/page pacing is changed.
t=(r/'audit_cam1_preddr_tb.sv').read_text()
t=t.replace('module audit_cam1_preddr_tb;','module blc_strip_tb;')
t=t.replace(' cam1_pixel_patch #(.START_TICKS(50),.PAGE_TICKS(200)) patch(',
''' reg request=0,advance=0;wire complete,token;wire[31:0] captured;
 cam1_blc_strip patch(''')
t=t.replace('.frame_id(pid),.result_valid(rv)',
 '''.request_toggle(request),.advance(advance),.complete(complete),.complete_token(token),.captured_id(captured),
  .frame_id(pid),.result_valid(rv)''')
t=t.replace(' function automatic[15:0] pixel',' integer epoch=0;\n function automatic[15:0] pixel')
t=t.replace('   endcase\n  end','   endcase\n   pixel=pixel ^ (epoch*16\'h1237);\n  end',1)
t=t.replace("if(page[607:576]!=0 ||page[575:544]!=32'h00010000)","if(page[607:576]!=epoch*2 ||page[575:544]!=32'h00010000)")
t=t.replace('audit_cam1_preddr_pages.txt','blc_strip_pages.txt')
a=t.index('  send_frame();send_frame();vs=1;href=0;idle(7200);')
b=t.index('  $fclose(outfile);',a)
t=t[:a]+'''  for(epoch=0;epoch<3;epoch=epoch+1) begin
   pages=0;export_pixels=0;seen=0;old_page=0;
   request=~request;idle(100);
   send_frame();send_frame();vs=1;href=0;idle(7200);
   wait(complete && token==request);#1;
   if(captured!=epoch*2)$fatal(1,"captured token/id phase%0d got%0d",epoch,captured);
   // Metadata slots consume no strip page. Only a real pixel snapshot advances.
   while(pages<480)begin
    repeat(3)begin repeat(100)@(negedge sc);end
    advance=1;@(negedge sc);advance=0;repeat(100)@(negedge sc);
   end
   if(export_pixels!=11520||!patch.frozen)$fatal(1,"phase totals");
   $display("PASS stage%0d id%0d complete11520 pixels/480pages",epoch,captured);
  end
  if(total_pixels!=5529600||verdicts!=6)$fatal(1,"production totals %0d %0d",total_pixels,verdicts);
''' +t[b:]
t=t.replace('#100000000;','#300000000;')
t=t.replace('PASS production input flops ->','PASS three rearmed production input flops ->')
(s/'sim/blc_strip_tb.sv').write_text(t)

# Actual UART serializer and the exact top-level metadata/page slot mux.
top=(s/'rtl/board/fpga_gsv1_top.v').read_text(encoding='utf-8')
mux=top[top.index('    reg [639:0] blc_diag_page;'):top.index('    wire [895:0] camera_diagnostics=')]
u='''`timescale 1ns/1ps
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
MUX
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
'''.replace('MUX',mux)
(s/'sim/blc_uart_tb.sv').write_text(u)
print('Prepared targeted production pixel and real-UART tests')
