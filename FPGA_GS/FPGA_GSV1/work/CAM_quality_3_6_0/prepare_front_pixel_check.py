"""Adapt the accepted full-size CAM1 fixture to the actual unchanged CAM0 unpacker.
Only the owner blanking parameter is new. Production geometry/RAM/read paths stay.
"""
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'source/sim/cam1_rotate25_tb.sv'
s=p.read_text()
s=s.replace('cam1_rotate25_tb','cam0_front30_tb')
s=s.replace('always #6.944444444 bc=~bc;', 'always #5.952380952 bc=~bc;')
start=s.index(' cam3660_dvp gearbox(')
end=s.index(' wire running,result_valid;',start)
s=s[:start]+''' reg[7:0] od=0;reg hd=0,vd=0;
 always @(posedge bc) begin od<=octet;hd<=href;vd<=vs;end
 wire[15:0] packed_rgb;
 cmos_8_16bit gearbox(.pclk(bc),.rst_n(rst),.de_i(hd),.vs_i(vd),.pdata_i(od),
  .pixel_clk(vc),.de_o(ide),.pdata_o(packed_rgb));
 assign ivs=vd;assign byte_bad=0;
 assign rgb={packed_rgb[4:0],packed_rgb[10:5],packed_rgb[15:11]};
'''+s[end:]
s=s.replace('.SOURCE_ID(1)', '.SOURCE_ID(0)')
s=s.replace('.CAM1_CONTINUOUS(1)', '.M3_FRONT(1),.FRONT_BLANKING_GRANT(1),.OBSERVE_DISPLAY(1)')
s=s.replace('idle(7200)', 'idle(7568)').replace('idle(3600*14)', 'idle(3784*8)')
s=s.replace('idle(3600-2*w)', 'idle(3784-2*w)').replace('idle(3600*64)', 'idle(3784*10)')
s=s.replace('value=pattern(tag,yy,xx);href=1;',
 '''value=pattern(tag,yy,xx);value={value[4:0],value[10:5],value[15:11]};href=1;''')
s=s.replace("28'h2800000", "28'h2000000")
s=s.replace("a[27:22]!=6'h02 && a[27:22]!=6'h03 && a[27:22]!=6'h0a", "a[27:22]!=6'h00 && a[27:22]!=6'h01 && a[27:22]!=6'h08")
s=s.replace('39990000', '33324000').replace('40010000', '33346000')
s=s.replace('CAM1', 'CAM0').replace('25fps', '30fps')
s=s.replace('byte72/pixel36', 'production OV5640 byte84/pixel42')
s=s.replace('180deg coordinate oracle', 'independent full-colour coordinate oracle')
(r/'source/sim/cam0_front30_tb.sv').write_text(s)
print('Prepared full720 CAM0 production unpacker/DDR/read fixture')
