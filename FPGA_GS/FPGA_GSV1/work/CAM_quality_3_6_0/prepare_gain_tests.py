from pathlib import Path
r=Path(__file__).resolve().parent
old=(r/'rear_probe_source/sim/cam1_green_probe_tb.sv').read_text()
wire_tasks=old[old.index(' task automatic check_byte'):old.index(' task reset_probe')]
addresses=[0x300a,0x300b,0x303a,0x303b,0x303c,0x303d,
 0x3500,0x3501,0x3502,0x3500,0x3501,0x3503,
 0x350a,0x350b,0x350a,0x350b,0x380c,0x380d,0x380e,0x380f,
 0x3a00,0x3a05,0x3a02,0x3a03,0x3a14,0x3a15,0x3a18,0x3a19,
 0x3a08,0x3a09,0x3a0a,0x3a0b,0x3c00,0x3c01,0x3c0c,
 0x4000,0x4001,0x4002,0x4003,0x4004,0x4005,0x4009,0x503d,0x5308]
head='''`timescale 1ns/1ps
module cam1_gain_profile_tb;
 reg clk=0;always #500 clk=~clk;
 reg rst_n=0,enable=0;
 tri1 scl,sda;reg slave_low=0,hold_clock=0;
 assign sda=slave_low?1'b0:1'bz;
 assign scl=hold_clock?1'b0:1'bz;
 wire[3:0] phase,error_code;wire failed,valid;
 wire[351:0] registers;wire[7:0] seq,errors;
 wire[15:0] target;
 cam1_gain_profile #(.CLOCK_HZ(1000000),.SCCB_HZ(100000),
 .BASELINE_CYCLES(100),.SCAN_PERIOD_CYCLES(100)) dut(
 .clk(clk),.rst_n(rst_n),.enable(enable),.scl(scl),.sda(sda),.phase(phase),
 .failed(failed),.error_code(error_code),.valid(valid),.registers(registers),
 .sequence_number(seq),.errors(errors),.milliseconds(32'd20000),.target_ceiling(target));
 reg[15:0] expected[0:43];reg[7:0] values[0:43];integer j;
'''
init=''.join(f"  expected[{i}]=16'h{a:04x};\n" for i,a in enumerate(addresses))
tail='''
 task defaults;
 begin
  for(j=0;j<44;j=j+1) values[j]=0;
  values[0]=8'h36;values[1]=8'h60;
  values[6]=0;values[7]=8'h31;values[8]=8'hc0;values[9]=0;values[10]=8'h31;
  values[12]=0;values[13]=8'hf8;values[14]=0;values[15]=8'hf8;
  values[16]=7;values[17]=8'h08;values[18]=3;values[19]=8'h20;
  values[26]=8'ha5;values[27]=8'hf8;
 end endtask
 task reset_profile;
 begin
  @(negedge clk);rst_n=0;enable=0;slave_low=0;hold_clock=0;
  repeat(8) @(negedge clk);rst_n=1;repeat(10) @(negedge clk);
  if(dut.read_start||dut.write_start) $fatal(1,"SCCB before init");
  enable=1;
 end endtask
 task scan;
 begin for(integer i=0;i<44;i=i+1) sensor(expected[i],values[i],-1);end
 endtask
 task apply_success(input[7:0] want_hi,want_lo);
 begin
  write_sensor(16'h3a18,want_hi,0);write_sensor(16'h3a19,want_lo,0);
  sensor(16'h3a18,want_hi,-1);sensor(16'h3a19,want_lo,-1);
  wait(phase==2);#1;
  if(failed||valid) $fatal(1,"must await fresh after-profile scan");
 end endtask
 task restore;
 begin
  write_sensor(16'h3a18,values[26],0);write_sensor(16'h3a19,values[27],0);
  sensor(16'h3a18,values[26],-1);sensor(16'h3a19,values[27],-1);
  wait(dut.state==20);#1;
  if(!failed||phase!=7||valid) $fatal(1,"failure incorrectly reported as applied");
 end endtask
 initial begin
'''+init+'''
  defaults();reset_profile();scan();apply_success(8'ha4,8'h80);
  if(target!=128||dut.baseline_gain!=248||dut.baseline_ceiling!=16'ha5f8||
    dut.baseline_exposure!=24'h0031c0||dut.baseline_ms!=20000) $fatal(1,"baseline preservation");
  values[26]=8'ha4;values[27]=8'h80;scan();wait(valid);#1;
  for(j=0;j<44;j=j+1) if(registers[351-j*8-:8]!==values[j]) $fatal(1,"scan byte %0d",j);
  if(seq!=2||errors!=0) $fatal(1,"complete sweep tracking");
  // Reconfiguration releases bus and requires a fresh baseline, not stale apply.
  @(negedge clk);enable=0;repeat(10) @(negedge clk);
  if(valid||phase!=0||dut.read_start||dut.write_start) $fatal(1,"enable reset");
  defaults();values[26]=8'ha4;values[27]=8'h40;
  reset_profile();scan();apply_success(8'ha4,8'h40);
  if(target!=64) $fatal(1,"must not raise a lower existing cap");
  defaults();reset_profile();values[11]=1;scan();wait(failed);#1;
  if(error_code!=2||dut.saved) $fatal(1,"manual AE must not be overwritten");
  defaults();reset_profile();values[0]=8'h56;scan();wait(failed);#1;
  if(error_code!=1||dut.saved) $fatal(1,"wrong sensor must not be written");
  defaults();reset_profile();values[9]=1;scan();wait(dut.state==0);#1;
  if(valid||seq||dut.saved||phase!=1) $fatal(1,"torn exposure published");
  values[9]=0;scan();apply_success(8'ha4,8'h80);
  defaults();reset_profile();sensor(16'h300a,0,0);wait(errors==1);#1;
  if(valid||dut.saved||dut.write_start) $fatal(1,"read ACK failure wrote profile");
  defaults();reset_profile();hold_clock=1;wait(errors==1);#1;
  if(valid||!dut.last_timeout||dut.saved) $fatal(1,"read timeout");
  defaults();reset_profile();scan();write_sensor(16'h3a18,8'ha4,1);restore();
  if(error_code!=3) $fatal(1,"write failure code");
  defaults();reset_profile();scan();
  write_sensor(16'h3a18,8'ha4,0);write_sensor(16'h3a19,8'h80,0);
  sensor(16'h3a18,8'ha5,-1);restore();
  if(error_code!=4) $fatal(1,"readback mismatch code");
  $display("PASS CAM1 gain8x: actual SCCB reads/writes,44-byte scans,baseline preserved,RMW reserved bits,lower cap not raised,ACK/timeout/torn AE,readback mismatch/exact rollback,init/reset exclusion; no exposure/BLC/clock writes");
  $finish;
 end
 initial begin #500000000;$fatal(1,"deadline");end
endmodule
'''
(r/'rear_gain_source/sim/cam1_gain_profile_tb.sv').write_text(head+wire_tasks+tail)
print('Prepared gain profile wire-level checks')
