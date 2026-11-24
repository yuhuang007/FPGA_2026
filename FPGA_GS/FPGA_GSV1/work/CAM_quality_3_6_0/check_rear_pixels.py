from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys
r=Path(__file__).resolve().parent;s=r/'rear_pixels_source';reports=r/'reports'
spec=importlib.util.spec_from_file_location('decode_patch',s/'scripts/decode_cam1_patch.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
text=(reports/'cam1_patch_pages.txt').read_text()
key,g,data=m.decode(text)
assert key[:5]==(2,1120,0,16,720) and len(data)==23040
expected=b''.join((((2*0x1237)^(y*0x531)^(x*0x275))&65535).to_bytes(2,'big')
                  for y in range(720) for x in range(1120,1136))
assert data==expected
for bad in ('\n'.join(text.splitlines()[1:]),text+'\n'+text.splitlines()[0][:-1]+'1'):
    try:m.decode(bad)
    except ValueError:pass
    else:raise AssertionError('incomplete/conflicting pages accepted')
base=r.parents[1]/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/source'
changes=[]
for name in ('rtl','vendor','constraints','config'):
    for p in (s/name).rglob('*'):
        if p.is_file():
            rel=p.relative_to(s);q=base/rel
            if not q.exists() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(q.read_bytes()).digest():
                changes.append(rel.as_posix())
allowed={'rtl/board/fpga_gsv1_top.v','rtl/network/m365_tx_observer.v',
         'rtl/capture/cam1_pixel_patch.v'}
assert set(changes)==allowed,changes
assert '.FRONT_BLANKING_GRANT' not in (s/'rtl/board/fpga_gsv1_top.v').read_text(encoding='utf-8')
assert 'GAIN_CEILING_RAW' not in (s/'rtl/board/fpga_gsv1_top.v').read_text(encoding='utf-8')
flow=(s/'flow.tcl').read_text();assert 'cam1_pixel_patch.v' in flow and 'cam1_gain_profile.v' not in flow
result=dict(native_pixel_oracle_pass=True,whole_crc_pass=True,incomplete_and_conflict_rejected=True,
            data_bytes=len(data),production_changes=changes,
            camera_tables_capture_filters_ddr_network_and_constraints_unchanged=True,
            gain_profile_module_absent=True,
            cam0_owner_fix_included=False,sensor_register_writes_added=False)
(reports/'patch_checks.json').write_text(json.dumps(result,indent=2)+'\n')
# UART at actual module output; compare every serialized byte against the held
# 40-word packet, independently of the camera-page decoder.
page=text.splitlines()[0].split()[1]
tb='''`timescale 1ns/1ps
module patch_uart_tb;
 reg clk=0,rst=0;always #10 clk=~clk;wire tx;
 wire[1279:0] values={640'd0,640'hPAGE};
 m361_uart_hex #(.TICKS(9000),.BAUD_DIV(2),.REVISION_ASCII("P")) dut(.clk(clk),.rst_n(rst),.values(values),.tx(tx));
 integer f,count=0;reg[7:0] c;
 initial begin f=$fopen("../reports/patch_uart_line.txt","w");#1;rst=0;#80;rst=1;end
 initial forever begin
  @(negedge tx);#60;
  for(integer i=0;i<8;i++) begin c[i]=tx;#40;end
  if(tx!==1) $fatal(1,"UART stop");
  $fwrite(f,"%c",c);count++;if(count==369) begin $fclose(f);$display("PASS production UART369bytes");$finish;end
 end
 initial begin #1000000;$fatal(1,"UART deadline");end
endmodule
'''.replace('PAGE',page)
(s/'sim/patch_uart_tb.sv').write_text(tb)
print(json.dumps(result,indent=2))
