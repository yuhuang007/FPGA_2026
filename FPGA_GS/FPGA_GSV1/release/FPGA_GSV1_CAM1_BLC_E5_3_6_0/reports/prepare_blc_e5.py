from pathlib import Path
import shutil,json
r=Path(__file__).resolve().parent;root=r.parents[1]
base=root/'release/FPGA_GSV1_CAM1_IOREG_E4_3_6_0/source';s=r/'rear_blc_source'
assert not s.exists();s.mkdir()
for n in ('rtl','vendor','constraints','config','scripts','sim'):
 shutil.copytree(base/n,s/n,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(base/'flow.tcl',s/'flow.tcl')
# Re-arm the already verified native strip; retain its real vendor DRM path.
p=s/'rtl/capture/cam1_pixel_patch.v';v=p.read_text()
v=v.replace('module cam1_pixel_patch #(','module cam1_blc_strip #(')
v=v.replace(')(input sc,vc,rst_n,ready,vs,de,input[15:0] rgb,input[31:0] frame_id,',
''')(input sc,vc,rst_n,ready,vs,de,input[15:0] rgb,input[31:0] frame_id,
 input request_toggle,advance,output complete,output complete_token,output[31:0] captured_id,''')
a=v.index(' reg[31:0] timer;');b=v.index(' (* ASYNC_REG',a)
v=v[:a]+" wire request=request_toggle;\n"+v[b:]
v=v.replace('reg capture,frozen,vs_d,de_d,have_id;','reg capture,frozen,vs_d,de_d,have_id;reg seen_request,frozen_token;')
v=v.replace('x<=0;y<=0;written<=0;held_id<=0;crc<=32\'hffffffff;held_crc<=0;rejected<=0;',
'''x<=0;y<=0;written<=0;held_id<=0;crc<=32'hffffffff;held_crc<=0;rejected<=0;
  seen_request<=0;frozen_token<=0;''')
v=v.replace('  if(!frozen) begin','''  if(request_v[1]!=seen_request) begin
   seen_request<=request_v[1];frozen<=0;capture<=0;have_id<=0;
   written<=0;x<=0;y<=0;rejected<=0;
  end else if(!frozen) begin''')
v=v.replace('!capture && request_v[1] && vs && !vs_d','!capture && vs && !vs_d && seen_request!=frozen_token')
v=v.replace('frozen<=1;held_crc<=~crc;','frozen<=1;frozen_token<=seen_request;held_crc<=~crc;')
v=v.replace('reg[15:0] valid_count;','''reg[15:0] valid_count;reg first_page,token_s;
 assign complete=done_s[1] && state!=0;
 assign complete_token=token_s;
 assign captured_id=id_s;''')
v=v.replace('valid_count<=0;read_address<=0;page<=0;', 'valid_count<=0;read_address<=0;page<=0;first_page<=1;token_s<=0;')
v=v.replace('  case(state)\n   0:', '''  if(!done_s[1]) begin state<=0;offset<=0;page<=0;first_page<=1;end
  else case(state)
   0:''')
v=v.replace('id_s<=held_id;crc_s<=held_crc;rejected_s<=rejected;state<=1;page_timer<=0;',
 'id_s<=held_id;crc_s<=held_crc;rejected_s<=rejected;token_s<=frozen_token;state<=1;page_timer<=0;')
v=v.replace('1:if(page_timer==PAGE_TICKS-1) begin','1:if(first_page || advance) begin')
v=v.replace("offset<=offset+24>=WORDS?32'd0:offset+24;state<=1;", "offset<=offset+24>=WORDS?32'd0:offset+24;first_page<=0;state<=1;")
p.write_text(v)
flow=(s/'flow.tcl').read_text().replace('add_design "rtl/capture/cam1_pixel_patch.v"',
 'add_design "rtl/capture/cam1_pixel_patch.v"\nadd_design "rtl/capture/cam1_blc_control.v"\nadd_design "rtl/display/cam1_blc_label.v"')
(s/'flow.tcl').write_text(flow)
p=s/'scripts/build_cam0.ps1';v=p.read_text(encoding='utf-8')
v=v.replace('CAM1_IOREG_E4_3_6_0','CAM1_BLC_E5_3_6_0').replace(
 'CAM1 IO input-register E4 controlled comparison; unknown external source timing; no quality fix claimed',
 'CAM1 BLC A-B-A prime E5 controlled diagnostic; not a quality repair')
p.write_text(v,encoding='utf-8')
# Diagnostic UART adds a read-only consumed pulse; no packet MAC/core logic edit.
p=s/'rtl/network/m361_diag.v';v=p.read_text()
v=v.replace('input [1279:0] values,output tx);','input [1279:0] values,output tx,output snapshot_tick);')
assert 'output snapshot_tick' in v
v=v.replace(' assign tx=bits_left!=0', ' assign snapshot_tick=timer==TICKS-1 && !sending;\n assign tx=bits_left!=0')
p.write_text(v)
p=s/'rtl/network/m365_tx_observer.v';v=p.read_text()
v=v.replace('output uart_tx);','output uart_tx,output diagnostic_take);')
assert 'output diagnostic_take' in v
v=v.replace('.REVISION_ASCII("I")','.REVISION_ASCII("B")').replace('.tx(uart_tx));','.tx(uart_tx),.snapshot_tick(diagnostic_take));')
p.write_text(v)
print(s)
