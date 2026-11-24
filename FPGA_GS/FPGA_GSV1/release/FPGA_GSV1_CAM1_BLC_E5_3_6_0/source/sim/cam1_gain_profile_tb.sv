`timescale 1ns/1ps
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
 task automatic check_byte(input [7:0] expected);
   reg [7:0] actual;integer i;
   begin
     actual=0;
     for(i=7;i>=0;i=i-1) begin @(posedge scl);#1;actual[i]=sda;end
     if(actual!==expected) $fatal(1,"wire byte expected %h got %h",expected,actual);
   end
 endtask
 task automatic slave_ack(input bit reject);
   begin
     @(negedge scl);#1;slave_low=!reject;
     @(posedge scl);@(negedge scl);#1;slave_low=0;
   end
 endtask
 task automatic wait_start;
   begin do @(negedge sda);while(scl!==1);end
 endtask
 task automatic wait_stop;
   begin do @(posedge sda);while(scl!==1);end
 endtask
 task automatic sensor(input [15:0] address,input [7:0] value,input integer reject_index);
   integer i;
   begin:respond
     wait_start();check_byte(8'h78);slave_ack(reject_index==0);
     if(reject_index==0) begin wait_stop();disable respond;end
     check_byte(address[15:8]);slave_ack(reject_index==1);
     if(reject_index==1) begin wait_stop();disable respond;end
     check_byte(address[7:0]);slave_ack(reject_index==2);
     if(reject_index==2) begin wait_stop();disable respond;end
     wait_start();check_byte(8'h79);slave_ack(reject_index==3);
     if(reject_index==3) begin wait_stop();disable respond;end
     for(i=7;i>=0;i=i-1) begin
       // ACK task has already observed the first falling data edge.
       slave_low=!value[i];@(posedge scl);@(negedge scl);#1;
     end
     slave_low=0;@(posedge scl);#1;
     if(sda!==1) $fatal(1,"master must NACK final read byte");
     @(negedge scl);wait_stop();
   end
 endtask

 task automatic write_sensor(input[15:0] address,input[7:0] value,input bit reject);
 begin:respond_write
  wait_start();check_byte(8'h78);slave_ack(reject);
  if(reject) begin wait_stop();disable respond_write;end
  check_byte(address[15:8]);slave_ack(0);
  check_byte(address[7:0]);slave_ack(0);
  check_byte(value);slave_ack(0);wait_stop();
 end endtask


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
  expected[0]=16'h300a;
  expected[1]=16'h300b;
  expected[2]=16'h303a;
  expected[3]=16'h303b;
  expected[4]=16'h303c;
  expected[5]=16'h303d;
  expected[6]=16'h3500;
  expected[7]=16'h3501;
  expected[8]=16'h3502;
  expected[9]=16'h3500;
  expected[10]=16'h3501;
  expected[11]=16'h3503;
  expected[12]=16'h350a;
  expected[13]=16'h350b;
  expected[14]=16'h350a;
  expected[15]=16'h350b;
  expected[16]=16'h380c;
  expected[17]=16'h380d;
  expected[18]=16'h380e;
  expected[19]=16'h380f;
  expected[20]=16'h3a00;
  expected[21]=16'h3a05;
  expected[22]=16'h3a02;
  expected[23]=16'h3a03;
  expected[24]=16'h3a14;
  expected[25]=16'h3a15;
  expected[26]=16'h3a18;
  expected[27]=16'h3a19;
  expected[28]=16'h3a08;
  expected[29]=16'h3a09;
  expected[30]=16'h3a0a;
  expected[31]=16'h3a0b;
  expected[32]=16'h3c00;
  expected[33]=16'h3c01;
  expected[34]=16'h3c0c;
  expected[35]=16'h4000;
  expected[36]=16'h4001;
  expected[37]=16'h4002;
  expected[38]=16'h4003;
  expected[39]=16'h4004;
  expected[40]=16'h4005;
  expected[41]=16'h4009;
  expected[42]=16'h503d;
  expected[43]=16'h5308;

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
