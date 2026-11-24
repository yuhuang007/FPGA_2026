`timescale 1ns/1ps
// Controlled CAM1-only experiment, not an image-quality fix.
// OV3660 v1.3 sec3.3 table3-4:503D bit7 enable, bits3:2 style00.
// Preserve every other bit, verify full bytes, restore the exact original byte.
// Existing camera initializer owns SCCB until enable. No clock/geometry changes.
module cam1_green_probe #(
 parameter CLOCK_HZ=50000000,SCCB_HZ=100000,
 parameter START_CYCLES=30*CLOCK_HZ,SENSOR_CYCLES=12*CLOCK_HZ,
 parameter GAP_CYCLES=8*CLOCK_HZ,FPGA_CYCLES=12*CLOCK_HZ
)(input clk,rst_n,enable,inout scl,sda,
 output reg [2:0] phase,output wire fpga_pattern,
 output reg failed,output reg [3:0] error_code,
 output reg [7:0] original_value,last_read);
 localparam WAIT_LIVE=0,READ_START=1,READ_WAIT=2,ON_START=3,ON_WAIT=4,
  ON_CHECK=5,ON_VERIFY=6,SENSOR=7,OFF_START=8,OFF_WAIT=9,
  OFF_CHECK=10,OFF_VERIFY=11,LIVE_GAP=12,FPGA=13,STOP=14,
  RECOVER=15,RECOVER_WAIT=16,RECOVER_CHECK=17,RECOVER_VERIFY=18,FAIL=19;
 reg [4:0] state;reg [31:0] count;
 reg rs,ws,saved;reg [7:0] value;
 wire rd,wd,rt,wt;wire[3:0] rn,wn;wire[7:0] data;
 assign fpga_pattern=phase==4 && !failed;
 cam_sccb_read16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) reader(
 .clk(clk),.rst_n(rst_n&&enable),.start(rs),.address(7'h3c),
 .register_address(16'h503d),.scl(scl),.sda(sda),.done(rd),
 .data(data),.nack_mask(rn),.bus_timeout(rt));
 cam_sccb_write16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) writer(
 .clk(clk),.rst_n(rst_n&&enable),.start(ws),.address(7'h3c),
 .register_address(16'h503d),.value(value),.scl(scl),.sda(sda),
 .done(wd),.nack_mask(wn),.bus_timeout(wt));
 task fail_probe(input[3:0] code);
 begin failed<=1;error_code<=code;phase<=7;state<=saved?RECOVER:FAIL;end
 endtask
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=WAIT_LIVE;count<=0;phase<=0;failed<=0;error_code<=0;
   rs<=0;ws<=0;saved<=0;value<=0;original_value<=0;last_read<=0;
  end else begin
   rs<=0;ws<=0;
   if(!enable) begin
    state<=WAIT_LIVE;count<=0;phase<=0;failed<=0;error_code<=0;saved<=0;
   end else case(state)
    WAIT_LIVE:begin
     phase<=1;
     if(count==START_CYCLES-1) begin count<=0;state<=READ_START;end
     else count<=count+1'b1;
    end
    READ_START:begin rs<=1;state<=READ_WAIT;end
    READ_WAIT:if(rd) begin
     last_read<=data;
     if(rt||rn!=0) fail_probe(rt?2:1);
     else begin original_value<=data;saved<=1;value<=(data&8'h73)|8'h80;state<=ON_START;end
    end
    ON_START:begin ws<=1;state<=ON_WAIT;end
    ON_WAIT:if(wd) begin
     if(wt||wn!=0) fail_probe(wt?4:3);else state<=ON_CHECK;
    end
    ON_CHECK:begin rs<=1;state<=ON_VERIFY;end
    ON_VERIFY:if(rd) begin
     last_read<=data;
     if(rt||rn!=0) fail_probe(rt?2:1);
     else if(data!=value) fail_probe(5);
     else begin count<=0;phase<=2;state<=SENSOR;end
    end
    SENSOR:if(count==SENSOR_CYCLES-1) begin
     value<=original_value;count<=0;state<=OFF_START;
    end else count<=count+1'b1;
    OFF_START:begin ws<=1;state<=OFF_WAIT;end
    OFF_WAIT:if(wd) begin
     if(wt||wn!=0) fail_probe(wt?4:3);else state<=OFF_CHECK;
    end
    OFF_CHECK:begin rs<=1;state<=OFF_VERIFY;end
    OFF_VERIFY:if(rd) begin
     last_read<=data;
     if(rt||rn!=0) fail_probe(rt?2:1);
     else if(data!=original_value) fail_probe(6);
     else begin phase<=3;count<=0;state<=LIVE_GAP;end
    end
    LIVE_GAP:if(count==GAP_CYCLES-1) begin phase<=4;count<=0;state<=FPGA;end
     else count<=count+1'b1;
    FPGA:if(count==FPGA_CYCLES-1) begin phase<=5;state<=STOP;end
     else count<=count+1'b1;
    RECOVER:begin value<=original_value;ws<=1;state<=RECOVER_WAIT;end
    RECOVER_WAIT:if(wd) state<=(wt||wn!=0)?FAIL:RECOVER_CHECK;
    RECOVER_CHECK:begin rs<=1;state<=RECOVER_VERIFY;end
    RECOVER_VERIFY:if(rd) begin last_read<=data;state<=FAIL;end
    default:begin end
   endcase
  end
 end
endmodule

// Known vertical bars injected AFTER DVP unpack, BEFORE capture_pipe/DDR.
// Sync, byte verdict and geometry still come from the live CAM1 sensor.
// CDC mode commits only at VS rising, so no frame contains a mode seam.
module cam1_probe_bars(input clk,rst_n,enable,vs,de,input[15:0] rgb,
 output[15:0] out_rgb,output reg active);
 (* ASYNC_REG="TRUE" *) reg[1:0] mode_sync;
 reg old_vs,old_de;reg[10:0] x;reg[15:0] bar;
 always @(posedge clk or negedge rst_n)
  if(!rst_n) begin mode_sync<=0;active<=0;old_vs<=0;old_de<=0;x<=0;end
  else begin
   mode_sync<={mode_sync[0],enable};old_vs<=vs;old_de<=de;
   if(vs&&!old_vs) active<=mode_sync[1];
   if(vs || !de) x<=0;else x<=x+1'b1;
  end
 always @* begin
  if(x<160) bar=16'hffff;
  else if(x<320) bar=16'hffe0;
  else if(x<480) bar=16'h07ff;
  else if(x<640) bar=16'h07e0;
  else if(x<800) bar=16'hf81f;
  else if(x<960) bar=16'hf800;
  else if(x<1120) bar=16'h001f;
  else bar=0;
 end
 assign out_rgb=active?bar:rgb;
endmodule
