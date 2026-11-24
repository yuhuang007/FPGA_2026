`timescale 1ns/1ps
// OV3660 preliminary1.3 tables3-7,7-4,7-5,7-13. Diagnostic only.
// 4003[7] is a write-one REDO command: never replay it during freeze/restore.
// 4002 and all BLC coefficients/window/target remain read-only throughout.
module cam1_blc_control #(
 parameter CLOCK_HZ=50000000,SCCB_HZ=100000,
 parameter COVER_TICKS=60*CLOCK_HZ,SETTLE_TICKS=CLOCK_HZ/5,
 parameter EXPORT_TICKS=45*CLOCK_HZ,CAPTURE_TIMEOUT=5*CLOCK_HZ
)(input clk,rst_n,enable,inout scl,sda,input[31:0] milliseconds,source_frame_id,
 input strip_complete,strip_token,input[31:0] strip_frame_id,
 output reg request_toggle,output reg[2:0] phase,
 output reg export_enabled,failed,restored,blc_restored,
 output reg[7:0] error_code,output reg[2:0] completed_mask,
 output reg[31:0] sample_id,output[639:0] pre_page,post_page,status_page);
 localparam WAIT_COVER=0,SCAN_START=1,SCAN_WAIT=2,SCAN_END=3,
  PROGRAM_START=4,PROGRAM_WAIT=5,VERIFY_START=6,VERIFY_WAIT=7,
  SETTLE=8,CAPTURE=9,EXPORT=10,STOP=11;
 localparam ORIGINAL=0,FIXED=1,PRE=2,POST=3;
 localparam PIN=0,HOLD_VALUES=1,FREEZE=2,RESUME=3,RESTORE_ALL=4;
 reg[3:0] state;reg[2:0] scan_kind,program_kind;
 reg[5:0] index;reg[3:0] op_index;
 reg[31:0] timer,scan_start_ms,scan_start_frame,scan_end_ms,scan_end_frame;
 reg[31:0] pre_start,pre_end,pre_f0,pre_f1,post_start,post_end,post_f0,post_f1,export_start;
 reg[447:0] staging,original_regs,fixed_regs,pre_regs,post_regs;
 reg[31:0] scan_crc,pre_crc,post_crc;
 reg saved,mismatch,restore_error;
 reg[31:0] restore_reads;
 reg read_start,write_start;reg[15:0] address_reg;reg[7:0] write_value;
 wire read_done,write_done,read_timeout,write_timeout;wire[3:0] read_nack,write_nack;wire[7:0] data;
 cam_sccb_read16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) reader(
 .clk(clk),.rst_n(rst_n && enable),.start(read_start),.address(7'h3c),.register_address(address_reg),
 .scl(scl),.sda(sda),.done(read_done),.data(data),.nack_mask(read_nack),.bus_timeout(read_timeout));
 cam_sccb_write16 #(.CLOCK_HZ(CLOCK_HZ),.SCCB_HZ(SCCB_HZ)) writer(
 .clk(clk),.rst_n(rst_n && enable),.start(write_start),.address(7'h3c),.register_address(address_reg),
 .value(write_value),.scl(scl),.sda(sda),.done(write_done),.nack_mask(write_nack),.bus_timeout(write_timeout));
 function[7:0] at(input[447:0] v,input integer n);begin at=v[447-n*8-:8];end endfunction
 function[15:0] addr(input[5:0] n);
 begin case(n)
  0:addr=16'h300a;1:addr=16'h300b;2:addr=16'h3503;
  3:addr=16'h3500;4:addr=16'h3501;5:addr=16'h3502;6:addr=16'h350a;7:addr=16'h350b;
  8:addr=16'h3406;9:addr=16'h3400;10:addr=16'h3401;11:addr=16'h3402;
  12:addr=16'h3403;13:addr=16'h3404;14:addr=16'h3405;
  15:addr=16'h380c;16:addr=16'h380d;17:addr=16'h380e;18:addr=16'h380f;
  19:addr=16'h303a;20:addr=16'h303b;21:addr=16'h303c;22:addr=16'h303d;
  23:addr=16'h4000;24:addr=16'h4001;25:addr=16'h4002;26:addr=16'h4003;
  27:addr=16'h4004;28:addr=16'h4005;29:addr=16'h4006;30:addr=16'h4007;31:addr=16'h4009;
  32:addr=16'h402c;33:addr=16'h402d;34:addr=16'h402e;35:addr=16'h402f;
  36:addr=16'h4030;37:addr=16'h4031;38:addr=16'h4032;39:addr=16'h4033;
  40:addr=16'h4740;41:addr=16'h4300;42:addr=16'h5000;43:addr=16'h5001;
  44:addr=16'h3a00;45:addr=16'h503d;46:addr=16'h3820;47:addr=16'h3821;
  48:addr=16'h3509;49:addr=16'h3504;50:addr=16'h3505;
  51:addr=16'h3512;52:addr=16'h3513;53:addr=16'h350c;54:addr=16'h350d;
  default:addr=16'h3008;
 endcase end endfunction
 function[31:0] crc_byte(input[31:0] value,input[7:0] octet);
 reg[31:0] c;integer i;
 begin c=value;for(i=0;i<8;i=i+1)c=(c[0]^octet[i])?((c>>1)^32'hedb88320):(c>>1);crc_byte=c;end endfunction
 function[15:0] prog_addr(input[2:0] p,input[3:0] n);
 begin
  if(p==HOLD_VALUES) begin
   case(n)
    0:prog_addr=16'h3500;1:prog_addr=16'h3501;2:prog_addr=16'h3502;
    3:prog_addr=16'h350a;4:prog_addr=16'h350b;
    5:prog_addr=16'h3400;6:prog_addr=16'h3401;7:prog_addr=16'h3402;
    8:prog_addr=16'h3403;9:prog_addr=16'h3404;default:prog_addr=16'h3405;
   endcase
  end else if(p==PIN) prog_addr=n==0?16'h3503:16'h3406;
  else if(p==FREEZE) prog_addr=n==0?16'h4005:16'h4003;
  else begin case(n)
   0:prog_addr=16'h4003;1:prog_addr=16'h4005;
   2:prog_addr=16'h3503;default:prog_addr=16'h3406;
  endcase end
 end endfunction
 function[7:0] prog_data(input[2:0] p,input[3:0] n,input[447:0] orig,fix);
 begin
  if(p==HOLD_VALUES) prog_data=at(fix,n<5?n+3:n+4);
  else if(p==PIN) prog_data=n==0?(at(orig,2)|8'h03):(at(orig,8)|8'h01);
  else if(p==FREEZE) prog_data=n==0?(at(orig,28)&8'hfd):((at(orig,26)&8'h3f)|8'h40);
  else begin case(n)
   0:prog_data=at(orig,26)&8'h7f;
   1:prog_data=at(orig,28);
   2:prog_data=at(orig,2);
   default:prog_data=at(orig,8);
  endcase end
 end endfunction
 wire[15:0] op_address=prog_addr(program_kind,op_index);
 wire[7:0] op_value=prog_data(program_kind,op_index,original_regs,fixed_regs);
 wire[7:0] op_mask=op_address==16'h4003 ?8'h7f:8'hff;
 wire[3:0] last_op=program_kind==HOLD_VALUES?10:(program_kind==RESTORE_ALL?3:1);
 wire coeff=index>=32 && index<=39;
 wire observed=(index!=26 && index!=28 && !coeff);
 wire expected_match=(index==26)?((data&8'h7f)==((at(original_regs,26)&8'h3f)|(phase==2?8'h40:0))):
   (index==28)?(data==(phase==2?(at(original_regs,28)&8'hfd):at(original_regs,28))):
   (!observed || data==at(fixed_regs,index));
 task abort_experiment(input[7:0] code);
 begin failed<=1;error_code<=code;phase<=5;export_enabled<=0;
  if(saved) begin program_kind<=RESTORE_ALL;op_index<=0;restore_error<=0;state<=PROGRAM_START;end
  else state<=STOP;
 end endtask
 // Snapshot payloads have CRC over all56 raw register bytes. Read intervals
 // and bracketing frame IDs are also exported: never call an updating BLC
 // multi-byte read an atomic value from the captured image frame.
 wire[7:0] flags={3'd0,failed,restored,blc_restored,export_enabled,saved};
 assign pre_page={32'h43314252,phase,5'd0,flags,8'd0,8'd1,sample_id,pre_start,pre_end,pre_crc,pre_regs};
 assign post_page={32'h43314252,phase,5'd0,flags,8'd1,8'd1,sample_id,post_start,post_end,post_crc,post_regs};
 assign status_page={32'h43314254,phase,5'd0,flags,error_code,8'd1,sample_id,milliseconds,
   pre_f0,pre_f1,post_f0,post_f1,pre_crc,post_crc,
   at(original_regs,26),at(original_regs,28),at(original_regs,2),at(original_regs,8),
   restore_reads,24'd0,5'd0,completed_mask,export_start,192'd0};
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=WAIT_COVER;scan_kind<=ORIGINAL;program_kind<=PIN;index<=0;op_index<=0;timer<=0;
   scan_start_ms<=0;scan_end_ms<=0;scan_start_frame<=0;scan_end_frame<=0;
   pre_start<=0;pre_end<=0;pre_f0<=0;pre_f1<=0;post_start<=0;post_end<=0;post_f0<=0;post_f1<=0;
   staging<=0;original_regs<=0;fixed_regs<=0;pre_regs<=0;post_regs<=0;
   scan_crc<=32'hffffffff;pre_crc<=0;post_crc<=0;saved<=0;mismatch<=0;restore_error<=0;
   restore_reads<=0;read_start<=0;write_start<=0;address_reg<=0;write_value<=0;
   request_toggle<=0;phase<=0;export_enabled<=0;failed<=0;restored<=0;blc_restored<=0;
   completed_mask<=0;error_code<=0;sample_id<=0;export_start<=0;
  end else begin
   read_start<=0;write_start<=0;
   if(enable) case(state)
    WAIT_COVER:if(timer==COVER_TICKS-1) begin timer<=0;scan_kind<=ORIGINAL;index<=0;state<=SCAN_START;end
     else timer<=timer+1'b1;
    SCAN_START:begin
     if(index==0) begin scan_start_ms<=milliseconds;scan_start_frame<=source_frame_id;scan_crc<=32'hffffffff;mismatch<=0;end
     address_reg<=addr(index);read_start<=1;state<=SCAN_WAIT;
    end
    SCAN_WAIT:if(read_done) begin
     if(read_timeout || read_nack!=0) abort_experiment(1);
     else begin
      staging<={staging[439:0],data};scan_crc<=crc_byte(scan_crc,data);
      if((scan_kind==PRE || scan_kind==POST) && !expected_match) mismatch<=1;
      if(scan_kind==POST && phase==2 && coeff && data!=at(pre_regs,index)) mismatch<=1;
      if(index==55) begin scan_end_ms<=milliseconds;scan_end_frame<=source_frame_id;state<=SCAN_END;end
      else begin index<=index+1'b1;state<=SCAN_START;end
     end
    end
    SCAN_END:begin
     if(scan_kind==ORIGINAL) begin
      if(at(staging,0)!=8'h36 || at(staging,1)!=8'h60 || (at(staging,2)&3)!=0 ||
         (at(staging,8)&1)!=0 || (at(staging,26)&8'h40)!=0 || (at(staging,28)&2)==0 ||
         (at(staging,23)&1)==0) abort_experiment(2);
      else begin original_regs<=staging;saved<=1;program_kind<=PIN;op_index<=0;state<=PROGRAM_START;end
     end else if(scan_kind==FIXED) begin
      if(at(staging,2)!=(at(original_regs,2)|3) || at(staging,8)!=(at(original_regs,8)|1)) abort_experiment(3);
      else begin fixed_regs<=staging;program_kind<=HOLD_VALUES;op_index<=0;state<=PROGRAM_START;end
     end else if(mismatch) abort_experiment(4);
     else if(scan_kind==PRE) begin
      pre_regs<=staging;pre_start<=scan_start_ms;pre_end<=scan_end_ms;
      pre_f0<=scan_start_frame;pre_f1<=scan_end_frame;pre_crc<=~scan_crc;
      request_toggle<=~request_toggle;timer<=0;state<=CAPTURE;
     end else begin
      post_regs<=staging;post_start<=scan_start_ms;post_end<=scan_end_ms;
      post_f0<=scan_start_frame;post_f1<=scan_end_frame;post_crc<=~scan_crc;
      completed_mask<=completed_mask | (3'b001<<(phase-1));
      if(phase==3) blc_restored<=1;
      export_enabled<=1;timer<=0;export_start<=milliseconds;state<=EXPORT;
     end
    end
    PROGRAM_START:begin address_reg<=op_address;write_value<=op_value;write_start<=1;state<=PROGRAM_WAIT;end
    PROGRAM_WAIT:if(write_done) begin
     if(write_timeout || write_nack!=0) begin
      if(program_kind==RESTORE_ALL) begin restore_error<=1;state<=VERIFY_START;end
      else abort_experiment(5);
     end else state<=VERIFY_START;
    end
    VERIFY_START:begin read_start<=1;state<=VERIFY_WAIT;end
    VERIFY_WAIT:if(read_done) begin
     if(program_kind==RESTORE_ALL) begin
      restore_reads<={restore_reads[23:0],data};
      if(read_timeout || read_nack!=0 || (data&op_mask)!=(op_value&op_mask)) restore_error<=1;
      if(op_index==last_op) begin
       restored<=!restore_error && !read_timeout && read_nack==0 && (data&op_mask)==(op_value&op_mask);
       if(restore_error || read_timeout || read_nack!=0 || (data&op_mask)!=(op_value&op_mask)) begin
        failed<=1;phase<=5;if(error_code==0)error_code<=8;
       end else if(!failed) phase<=4;
       state<=STOP;
      end else begin op_index<=op_index+1'b1;state<=PROGRAM_START;end
     end else if(read_timeout || read_nack!=0 || (data&op_mask)!=(op_value&op_mask)) abort_experiment(6);
     else if(op_index!=last_op) begin op_index<=op_index+1'b1;state<=PROGRAM_START;end
     else begin
      timer<=0;state<=SETTLE;
      if(program_kind==PIN) scan_kind<=FIXED;
      else begin scan_kind<=PRE;phase<=program_kind==HOLD_VALUES?1:(program_kind==FREEZE?2:3);end
     end
    end
    SETTLE:if(timer==SETTLE_TICKS-1) begin timer<=0;index<=0;state<=SCAN_START;end
     else timer<=timer+1'b1;
    CAPTURE:if(strip_complete && strip_token==request_toggle) begin
     sample_id<=strip_frame_id;scan_kind<=POST;index<=0;state<=SCAN_START;
    end else if(timer==CAPTURE_TIMEOUT-1) abort_experiment(7);else timer<=timer+1'b1;
    EXPORT:if(timer==EXPORT_TICKS-1) begin
     timer<=0;export_enabled<=0;op_index<=0;state<=PROGRAM_START;
     program_kind<=phase==1?FREEZE:(phase==2?RESUME:RESTORE_ALL);
    end else timer<=timer+1'b1;
    default:begin end
   endcase
  end
 end
endmodule


