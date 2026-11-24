from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent
project=r.parents[1]
source=r/'rear_probe_source'
old=(project/'work/CAM0_motion/sim/cam0_ae_profile_tb.sv').read_text()
tasks=old[old.index(' task automatic check_byte'):old.index(' task automatic reset_dut')]
bench='''`timescale 1ns/1ps
module cam1_green_probe_tb;
 reg clk=0;always #500 clk=~clk;
 reg rst_n=0,enable=0;
 tri1 scl,sda;reg slave_low=0,hold_clock=0;
 assign sda=slave_low?1'b0:1'bz;
 assign scl=hold_clock?1'b0:1'bz;
 wire[2:0] phase;wire pattern,failed;wire[3:0] err;wire[7:0] original,last;
 cam1_green_probe #(.CLOCK_HZ(1000000),.SCCB_HZ(100000),
 .START_CYCLES(100),.SENSOR_CYCLES(200),.GAP_CYCLES(100),.FPGA_CYCLES(200)) dut(
 .clk(clk),.rst_n(rst_n),.enable(enable),.scl(scl),.sda(sda),.phase(phase),
 .fpga_pattern(pattern),.failed(failed),.error_code(err),.original_value(original),.last_read(last));
'''+tasks+'''
 task reset_probe;
 begin
  @(negedge clk);rst_n=0;enable=0;slave_low=0;hold_clock=0;
  repeat(8) @(negedge clk);rst_n=1;repeat(10) @(negedge clk);
  if(dut.rs||dut.ws||pattern) $fatal(1,"bus used before config");
  enable=1;
 end endtask
 initial begin
  reset_probe();sensor(16'h503d,8'h3c,-1);
  write_sensor(16'h503d,8'hb0,0);sensor(16'h503d,8'hb0,-1);
  wait(phase==2);#1;
  if(failed||pattern||original!=8'h3c||last!=8'hb0) $fatal(1,"pattern verify");
  write_sensor(16'h503d,8'h3c,0);sensor(16'h503d,8'h3c,-1);
  wait(phase==4);#1;if(!pattern||last!=8'h3c) $fatal(1,"restore not verified");
  wait(phase==5);#1;if(pattern||failed) $fatal(1,"final live not restored");
  repeat(300) @(negedge clk);if(dut.rs||dut.ws) $fatal(1,"not one-shot");
  reset_probe();sensor(16'h503d,0,0);wait(failed);#1;
  if(phase!=7||err!=1||pattern) $fatal(1,"read ACK failure");
  reset_probe();hold_clock=1;wait(failed);#1;
  if(phase!=7||err!=2||pattern) $fatal(1,"read timeout");hold_clock=0;
  reset_probe();sensor(16'h503d,8'h3c,-1);
  write_sensor(16'h503d,8'hb0,0);sensor(16'h503d,8'hb1,-1);
  write_sensor(16'h503d,8'h3c,0);sensor(16'h503d,8'h3c,-1);
  wait(dut.state==19);#1;
  if(phase!=7||err!=5||pattern||last!=8'h3c) $fatal(1,"mismatch recovery");
  reset_probe();sensor(16'h503d,8'h3c,-1);
  write_sensor(16'h503d,8'hb0,1);
  write_sensor(16'h503d,8'h3c,0);sensor(16'h503d,8'h3c,-1);
  wait(dut.state==19);#1;
  if(phase!=7||err!=3||pattern) $fatal(1,"write ACK recovery");
  $display("PASS CAM1 probe: production SCCB, preserve503D non-target bits, exact restore/full verify, ACK/timeout/mismatch/recovery, init mutual exclusion, no fake successful phase");
  $finish;
 end
 initial begin #30000000;$fatal(1,"deadline");end
endmodule
'''
(source/'sim/cam1_green_probe_tb.sv').write_text(bench)
owner=(project/'sim/m3_owner_tb.sv').read_text().replace('.H_NUM(32), .V_NUM(2)', '.H_NUM(32), .V_NUM(2), .BLANKING_GRANT(1)')
(r/'source/sim/cam0_dual_reader_tb.sv').write_text(owner)
changes=[]
base=project/'release/FPGA_GSV1_CAM0_OV5640_3_5_9_READBACK/source'
for folder in ('source','rear_probe_source'):
 for p in (r/folder).rglob('*'):
  if not p.is_file() or p.parts[-2]=='sim' or 'build' in p.relative_to(r/folder).parts: continue
  rel=p.relative_to(r/folder);oldp=base/rel
  if not oldp.exists() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(oldp.read_bytes()).digest():
   changes.append(dict(branch=folder,path=rel.as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(r/'reports/scope.json').write_text(json.dumps(changes,indent=2))
print(json.dumps(changes,indent=2))
