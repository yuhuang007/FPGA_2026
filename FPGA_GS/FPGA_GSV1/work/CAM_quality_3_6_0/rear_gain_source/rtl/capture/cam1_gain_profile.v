`timescale 1ns/1ps
// OV3660 v1.3 sections3.4/7.9: gain=/16;3A18[1:0],3A19 ceiling.
// Controlled CAM1-only contrast, NOT a proven green-line repair. Never writes
// exposure, BLC, ISP, PLL, geometry, sync or direction. Normal AE stays enabled.
module cam1_gain_profile #(
 parameter CLOCK_HZ=50000000,SCCB_HZ=100000,
 parameter BASELINE_CYCLES=20*CLOCK_HZ,GAIN_CEILING_RAW=128,
 parameter SCAN_PERIOD_CYCLES=CLOCK_HZ
)(input clk,rst_n,enable,inout scl,sda,
 output reg[351:0] registers,output reg valid,output reg[7:0] sequence_number,errors,
 output reg[3:0] last_nack,error_code,output reg last_timeout,failed,
 output reg[3:0] phase,output reg[23:0] baseline_exposure,
 output reg[7:0] baseline_manual,output reg[15:0] baseline_gain,baseline_ceiling,
 output reg[15:0] target_ceiling,output reg[7:0] original_high,applied_high,
 input[31:0] milliseconds,output reg[31:0] baseline_ms,sweep_ms);
 function[15:0] address(input[5:0] i);
 begin case(i)
  0:address=16'h300a;1:address=16'h300b;
  2:address=16'h303a;3:address=16'h303b;4:address=16'h303c;5:address=16'h303d;
  6:address=16'h3500;7:address=16'h3501;8:address=16'h3502;
  9:address=16'h3500;10:address=16'h3501;11:address=16'h3503;
  12:address=16'h350a;13:address=16'h350b;14:address=16'h350a;15:address=16'h350b;
  16:address=16'h380c;17:address=16'h380d;18:address=16'h380e;19:address=16'h380f;
  20:address=16'h3a00;21:address=16'h3a05;
  22:address=16'h3a02;23:address=16'h3a03;24:address=16'h3a14;25:address=16'h3a15;
  26:address=16'h3a18;27:address=16'h3a19;
  28:address=16'h3a08;29:address=16'h3a09;30:address=16'h3a0a;31:address=16'h3a0b;
  32:address=16'h3c00;33:address=16'h3c01;34:address=16'h3c0c;
  35:address=16'h4000;36:address=16'h4001;37:address=16'h4002;
  38:address=16'h4003;39:address=16'h4004;40:address=16'h4005;41:address=16'h4009;
  42:address=16'h503d;43:address=16'h5308;
  default:address=16'h300a;
 endcase end endfunction
 function[7:0] byte_at(input[351:0] data,input integer i);
 begin byte_at=data[351-i*8-:8];end endfunction
 localparam DELAY=0,SCAN_START=1,SCAN_WAIT=2,COMMIT=3,
  WRITE_HI=4,WAIT_HI=5,WRITE_LO=6,WAIT_LO=7,
  CHECK_HI=8,VERIFY_HI=9,CHECK_LO=10,VERIFY_LO=11,
  RESTORE_HI=12,RESTORE_HI_WAIT=13,RESTORE_LO=14,RESTORE_LO_WAIT=15,
  RESTORE_CHECK_HI=16,RESTORE_VERIFY_HI=17,
  RESTORE_CHECK_LO=18,RESTORE_VERIFY_LO=19,STOP=20;
 reg[4:0] state;reg[5:0] index;reg[351:0] staging;
 reg[31:0] elapsed,wait_count;reg read_start,write_start,saved;
 reg[15:0] register_address;reg[7:0] write_value;
 reg[7:0] original_low,target_low;
 wire read_done,write_done,read_timeout,write_timeout;
 wire[3:0] read_nacks,write_nacks;wire[7:0] data;
 wire[15:0] actual_ceiling={byte_at(staging,26),byte_at(staging,27)};
 wire[15:0] requested_ceiling=actual_ceiling[9:0]<GAIN_CEILING_RAW ?
  {6'd0,actual_ceiling[9:0]}:GAIN_CEILING_RAW;
 wire coherent=byte_at(staging,6)==byte_at(staging,9) &&
  byte_at(staging,7)==byte_at(staging,10) &&
  byte_at(staging,12)==byte_at(staging,14) && byte_at(staging,13)==byte_at(staging,15);
 cam_sccb_read16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) reader(
  .clk(clk),.rst_n(rst_n&&enable),.start(read_start),.address(7'h3c),
  .register_address(register_address),.scl(scl),.sda(sda),.done(read_done),
  .data(data),.nack_mask(read_nacks),.bus_timeout(read_timeout));
 cam_sccb_write16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) writer(
  .clk(clk),.rst_n(rst_n&&enable),.start(write_start),.address(7'h3c),
  .register_address(register_address),.value(write_value),.scl(scl),.sda(sda),
  .done(write_done),.nack_mask(write_nacks),.bus_timeout(write_timeout));
 task fail_profile(input[3:0] code);
 begin failed<=1;valid<=0;phase<=7;error_code<=code;
  state<=saved?RESTORE_HI:STOP;
 end endtask
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=DELAY;index<=0;registers<=0;staging<=0;valid<=0;
   sequence_number<=0;errors<=0;last_nack<=0;last_timeout<=0;
   failed<=0;error_code<=0;phase<=0;elapsed<=0;wait_count<=0;
   read_start<=0;write_start<=0;saved<=0;register_address<=0;write_value<=0;
   baseline_exposure<=0;baseline_manual<=0;baseline_gain<=0;baseline_ceiling<=0;
   target_ceiling<=0;original_high<=0;original_low<=0;applied_high<=0;target_low<=0;
   baseline_ms<=0;sweep_ms<=0;
  end else begin
   read_start<=0;write_start<=0;
   if(!enable) begin
    state<=DELAY;index<=0;valid<=0;phase<=0;elapsed<=0;wait_count<=0;
    saved<=0;failed<=0;error_code<=0;
   end else begin
    if(phase==0) phase<=1;
    if(elapsed<BASELINE_CYCLES) elapsed<=elapsed+1'b1;
    case(state)
     DELAY:if(wait_count==SCAN_PERIOD_CYCLES-1) begin wait_count<=0;index<=0;state<=SCAN_START;end
       else wait_count<=wait_count+1'b1;
     SCAN_START:begin register_address<=address(index);read_start<=1;state<=SCAN_WAIT;end
     SCAN_WAIT:if(read_done) begin
      if(read_timeout || read_nacks!=0) begin
       valid<=0;last_nack<=read_nacks;last_timeout<=read_timeout;
       if(errors!=255) errors<=errors+1'b1;
       state<=DELAY;
      end else begin
       staging<={staging[343:0],data};
       if(index==43) state<=COMMIT;else begin index<=index+1'b1;state<=SCAN_START;end
      end
     end
     COMMIT:begin
      state<=DELAY;
      if(coherent) begin
       registers<=staging;valid<=1;sequence_number<=sequence_number+1'b1;
       last_nack<=0;last_timeout<=0;sweep_ms<=milliseconds;
       if(phase==1 && elapsed>=BASELINE_CYCLES) begin
        if(byte_at(staging,0)!=8'h36 || byte_at(staging,1)!=8'h60) fail_profile(1);
        else if((byte_at(staging,11)&8'h03)!=0) fail_profile(2);
        else begin
         baseline_exposure<={byte_at(staging,6),byte_at(staging,7),byte_at(staging,8)};
         baseline_manual<=byte_at(staging,11);
         baseline_gain<={byte_at(staging,12),byte_at(staging,13)};
         baseline_ceiling<=actual_ceiling;baseline_ms<=milliseconds;
         original_high<=byte_at(staging,26);original_low<=byte_at(staging,27);
         applied_high<=(byte_at(staging,26)&8'hfc)|requested_ceiling[9:8];
         target_low<=requested_ceiling[7:0];target_ceiling<=requested_ceiling;
         saved<=1;state<=WRITE_HI;
        end
       end
      end else valid<=0; // retry torn AE update, never report a coherent sample
     end
     WRITE_HI:begin register_address<=16'h3a18;write_value<=applied_high;write_start<=1;state<=WAIT_HI;end
     WAIT_HI:if(write_done) begin
      if(write_timeout||write_nacks!=0) fail_profile(3);else state<=WRITE_LO;
     end
     WRITE_LO:begin register_address<=16'h3a19;write_value<=target_low;write_start<=1;state<=WAIT_LO;end
     WAIT_LO:if(write_done) begin
      if(write_timeout||write_nacks!=0) fail_profile(3);else state<=CHECK_HI;
     end
     CHECK_HI:begin register_address<=16'h3a18;read_start<=1;state<=VERIFY_HI;end
     VERIFY_HI:if(read_done) begin
      if(read_timeout||read_nacks!=0||data!=applied_high) fail_profile(4);else state<=CHECK_LO;
     end
     CHECK_LO:begin register_address<=16'h3a19;read_start<=1;state<=VERIFY_LO;end
     VERIFY_LO:if(read_done) begin
      if(read_timeout||read_nacks!=0||data!=target_low) fail_profile(4);
      else begin phase<=2;valid<=0;wait_count<=0;state<=DELAY;end
     end
     RESTORE_HI:begin register_address<=16'h3a18;write_value<=original_high;write_start<=1;state<=RESTORE_HI_WAIT;end
     RESTORE_HI_WAIT:if(write_done) state<=RESTORE_LO;
     RESTORE_LO:begin register_address<=16'h3a19;write_value<=original_low;write_start<=1;state<=RESTORE_LO_WAIT;end
     RESTORE_LO_WAIT:if(write_done) state<=RESTORE_CHECK_HI;
     RESTORE_CHECK_HI:begin register_address<=16'h3a18;read_start<=1;state<=RESTORE_VERIFY_HI;end
     RESTORE_VERIFY_HI:if(read_done) state<=RESTORE_CHECK_LO;
     RESTORE_CHECK_LO:begin register_address<=16'h3a19;read_start<=1;state<=RESTORE_VERIFY_LO;end
     RESTORE_VERIFY_LO:if(read_done) state<=STOP; // failed stays asserted, no fake restoration claim
     default:begin end
    endcase
   end
  end
 end
endmodule
