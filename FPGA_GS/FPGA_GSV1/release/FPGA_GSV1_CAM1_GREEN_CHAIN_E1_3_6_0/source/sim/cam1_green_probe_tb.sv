`timescale 1ns/1ps
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
