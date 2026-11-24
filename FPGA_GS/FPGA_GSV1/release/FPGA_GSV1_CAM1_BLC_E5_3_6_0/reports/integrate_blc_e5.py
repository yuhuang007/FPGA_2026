from pathlib import Path
r=Path(__file__).resolve().parent;s=r/'rear_blc_source'
p=s/'rtl/board/fpga_gsv1_top.v';v=p.read_text(encoding='utf-8')
a=v.index('    wire [639:0] cam1_pixel_page;');b=v.index('//CMOS 8bit',a)
v=v[:a]+'''    wire [639:0] cam1_pixel_page,blc_pre_page,blc_post_page,blc_status_page;
    wire blc_request,blc_complete,blc_token,blc_export,blc_failed,blc_restored,blc_resumed;
    wire [31:0] blc_strip_id,blc_sample_id,blc_source_id;
    wire [7:0] blc_error;wire [2:0] blc_phase,blc_completed,blc_pixel_phase;
    wire diagnostic_take;reg [3:0] blc_slot;
    always @(posedge sys_clk or negedge rstn_out)
      if(!rstn_out) blc_slot<=0;else if(diagnostic_take) blc_slot<=blc_slot+1'b1;
    m361_snapshot #(.W(32)) blc_frame_tag(.sc(cmos2_pclk_16bit),.dc(sys_clk),
      .rst_n(rstn_out),.value(cap_id1),.snapshot(blc_source_id));
    m3_status_mailbox blc_label_cdc(.sc(sys_clk),.dc(pix_clk),.rst_n(rstn_out),
      .value(blc_phase),.out_value(blc_pixel_phase));
    cam1_blc_control rear_blc(.clk(sys_clk),.rst_n(rstn_out && cmos2_reset),
      .enable(cmos_init_done[1]),.scl(cmos2_scl),.sda(cmos2_sda),
      .milliseconds(cam1_ms),.source_frame_id(blc_source_id),
      .strip_complete(blc_complete),.strip_token(blc_token),.strip_frame_id(blc_strip_id),
      .request_toggle(blc_request),.phase(blc_phase),.export_enabled(blc_export),
      .failed(blc_failed),.restored(blc_restored),.blc_restored(blc_resumed),
      .error_code(blc_error),.completed_mask(blc_completed),.sample_id(blc_sample_id),
      .pre_page(blc_pre_page),.post_page(blc_post_page),.status_page(blc_status_page));
    cam1_blc_strip rear_pixel_patch(.sc(sys_clk),.vc(cmos2_pclk_16bit),
      .rst_n(rstn_out),.ready(pipe_rst1),.vs(cap_vs1),.de(cap_de1),.rgb(cap_rgb1),
      .request_toggle(blc_request),.advance(diagnostic_take && blc_export && blc_slot>=3),
      .complete(blc_complete),.complete_token(blc_token),.captured_id(blc_strip_id),
      .frame_id(cap_id1),.result_valid(verdict_valid1),.result_id(verdict_id1),
      .result_errors(verdict_errors1 | {7'd0,cam1_verdict_byte_error}),.page(cam1_pixel_page));
    reg [639:0] blc_diag_page;
    always @(posedge sys_clk) begin
      if(!blc_export || blc_slot==2) blc_diag_page<=blc_status_page;
      else if(blc_slot==0) blc_diag_page<=blc_pre_page;
      else if(blc_slot==1) blc_diag_page<=blc_post_page;
      else blc_diag_page<=cam1_pixel_page;
    end
    wire [895:0] camera_diagnostics={cam1_diagnostics,blc_diag_page};
'''+v[b:]
v=v.replace('.feedback(feedback_pixel),.hint_visible(hint_visible)',
 '.diagnostic_phase(blc_pixel_phase),.feedback(feedback_pixel),.hint_visible(hint_visible)')
assert v.count('.diagnostic_phase(')==1
# Only the passive observer exports diagnostic_take.
v=v.replace('.diagnostic_tx(diagnostic_uart_tx)',
 '.diagnostic_tx(diagnostic_uart_tx),.diagnostic_take(diagnostic_take)')
assert '.diagnostic_take(diagnostic_take)' in v
p.write_text(v,encoding='utf-8')
p=s/'rtl/network/m3_network.v';v=p.read_text()
v=v.replace('output diagnostic_tx,','output diagnostic_tx,output diagnostic_take,')
v=v.replace('.camera_diagnostics(camera_diagnostics),.uart_tx(diagnostic_tx));',
 '.camera_diagnostics(camera_diagnostics),.uart_tx(diagnostic_tx),.diagnostic_take(diagnostic_take));')
v=v.replace(' wire phase,phase_d,pll_lock,nc;',
 ' generate if(!E1_PHY || !PHY_INTERNAL_DELAY) begin: no_diagnostic_take\n assign diagnostic_take=1\'b0;end endgenerate\n wire phase,phase_d,pll_lock,nc;')
p.write_text(v)
p=s/'rtl/display/m31_video_output.v';v=p.read_text()
v=v.replace('input [2:0] feedback,input hint_visible', 'input [2:0] diagnostic_phase,input [2:0] feedback,input hint_visible')
v=v.replace('.hint_visible(hint_visible),.hint_code(hint_code),.video_good(show_video)',
 '.diagnostic_phase(diagnostic_phase),.hint_visible(hint_visible),.hint_code(hint_code),.video_good(show_video)')
p.write_text(v)
p=s/'rtl/display/m31_osd.v';v=p.read_text()
v=v.replace('input [3:0] video_good,', 'input [2:0] diagnostic_phase,input [3:0] video_good,')
v=v.replace(' assign area=area_d[1];',''' wire diag_area,diag_pixel,font_pixel;
 cam1_blc_label blc_label(.clk(clk),.x(x),.y(y),.phase(diagnostic_phase),.area(diag_area),.pixel(diag_pixel));
 assign area=diag_area || area_d[1];
 assign pixel=diag_area ? diag_pixel:font_pixel;''')
v=v.replace('.pixel(pixel));','.pixel(font_pixel));')
p.write_text(v)
glyphs={
 'A':['01110','10001','10001','11111','10001','10001','10001'],
 'B':['11110','10001','10001','11110','10001','10001','11110'],
 'C':['01111','10000','10000','10000','10000','10000','01111'],
 'D':['11110','10001','10001','10001','10001','10001','11110'],
 'E':['11111','10000','10000','11110','10000','10000','11111'],
 'F':['11111','10000','10000','11110','10000','10000','10000'],
 'I':['11111','00100','00100','00100','00100','00100','11111'],
 'L':['10000','10000','10000','10000','10000','10000','11111'],
 'N':['10001','11001','11001','10101','10011','10011','10001'],
 'O':['01110','10001','10001','10001','10001','10001','01110'],
 'P':['11110','10001','10001','11110','10000','10000','10000'],
 'R':['11110','10001','10001','11110','10100','10010','10001'],
 'S':['01111','10000','10000','01110','00001','00001','11110'],
 'T':['11111','00100','00100','00100','00100','00100','00100'],
 'U':['10001','10001','10001','10001','10001','10001','01110'],
 'V':['10001','10001','10001','10001','10001','01010','00100'],
 'Z':['11111','00001','00010','00100','01000','10000','11111']}
v='''`timescale 1ns/1ps
// Two-register OSD timing matches m31_text. No source pixels are changed.
module cam1_blc_label(input clk,input[10:0] x,y,input[2:0] phase,output area,pixel);
 reg[127:0] text;reg[7:0] ch;reg[2:0] row,col;reg a0,a1,p1;
 wire[10:0] xx=x-12,yy=y-84;
 always @* case(phase)
  0:text="BLC COVER PREP  ";1:text="BLC A UPDATE    ";
  2:text="BLC B FREEZE    ";3:text="BLC APR RESTORE ";
  4:text="BLC DONE        ";default:text="BLC INVALID     ";
 endcase
 function[34:0] glyph(input[7:0] c);
 begin case(c)
'''
for c,rows in glyphs.items():v+=f'  8\'d{ord(c)}:glyph=35\'b'+''.join(rows)+';\n'
v+='''  default:glyph=0;
 endcase end endfunction
 wire[34:0] bits=glyph(ch);
 always @(posedge clk) begin
  ch<=text[127-xx[6:3]*8-:8];row<=yy[3:1];col<=xx[2:0];
  a0<=x>=12 && x<140 && y>=84 && y<98;
  a1<=a0;p1<=col<5 && row<7 ? bits[34-row*5-col]:0;
 end
 assign area=a1;assign pixel=p1;
endmodule
'''
(s/'rtl/display/cam1_blc_label.v').write_text(v)
for file in ('read_net2_diag.ps1','decode_cam1_rate.py'):
 p=s/'scripts'/file;v=p.read_text(encoding='utf-8')
 if file.endswith('ps1'):v=v.replace('35[OPI]','35[OPIB]').replace('35O/35P/35I','35O/35P/35I/35B')
 else:v=v.replace("'N2 35I '","'N2 35I ', 'N2 35B '")
 p.write_text(v,encoding='utf-8')
print('Integrated single E5 BLC experiment; E4 FDC and sensor initialization untouched')
