`timescale 1ns/1ps
module map_owner_tb;
 reg c=0,pc=0,rst=0,fs=0,sel=0,beg=0,pub=0,acq=0,rel=0,valid=1;
 always #5 c=~c;always #3.367 pc=~pc;
 wire ack,ready,grant,held;wire av;wire [3:0] al;reg[4:0]rem=0;
 always @(posedge c)if(!rst)rem<=0;else if(av)rem<=al+1;else if(rem!=0)rem<=rem-1;wire [1:0] bank,nb;wire[31:0] id,nt,latest,rawid,session;
 reg [31:0] input_id=42,stamp=100,sid=7;
 m3_right_store #(.HD_DISPLAY(1)) dut(.clk(c),.rst_n(rst),.pc(pc),.fs(fs),.selected(sel),.quarter(1'b0),.request(1'b0),
 .begin_frame(beg),.publish(pub),.frame_id(input_id),.frame_stamp(stamp),.frame_session(sid),.source_valid(valid),
 .net_acquire(acq),.net_release(rel),.net_grant(grant),.net_held(held),.net_bank(nb),.net_id(id),.net_time(nt),.latest_id(latest),.latest_input_id(rawid),.latest_input_session(session),
 .begin_ack(ack),.write_bank(bank),.ready(ready),.arvalid(av),.arlen(al),.arready(1'b1),.rdata(256'd0),.rvalid(rem!=0),.rlast(rem==1));
 task start;begin @(negedge c);beg=1;wait(ack);@(negedge c);beg=0;repeat(5)@(negedge c);end endtask
 task publish;begin @(negedge c);pub=1;@(negedge c);pub=0;repeat(5)@(negedge c);end endtask
 task sof;begin @(negedge pc);fs=1;repeat(3)@(negedge pc);fs=0;repeat(20)@(negedge c);end endtask
 task acquire;begin @(negedge c);acq=1;wait(grant);@(negedge c);acq=0;repeat(3)@(negedge c);end endtask
 integer used=0;reg[1:0] reader_bank,upload_bank,latest_bank;
 initial begin
 #100;rst=1;start;publish;used=used|(1<<bank);
 if(latest!=1||rawid!=42||session!=7)$fatal(1,"initial mapping");
 acquire;upload_bank=nb;if(id!=1||nt!=100)$fatal(1,"upload identity");
 input_id=99;stamp=200;start;publish;used=used|(1<<bank);sel=1;repeat(8)@(negedge c);sof;reader_bank=dut.rbank;
 if(reader_bank==upload_bank)$fatal(1,"need independent reader pins");
 input_id=100;start;publish;used=used|(1<<bank);latest_bank=bank;
 start;used=used|(1<<bank);
 if(bank==upload_bank||bank==reader_bank||bank==latest_bank)$fatal(1,"writer overwrites reader/latest");
 if(used!=15)$fatal(1,"fourth slot not used mask=%h",used);
 // Partial assembly/repeated begin must not alter latest descriptor.
 input_id=101;repeat(4)start;
 if(latest!=3||rawid!=100)$fatal(1,"partial became complete");
 sel=0;repeat(800)@(negedge c);
 if(dut.held || !held || nb!=upload_bank || id!=1)$fatal(1,"hiding view releases/crosses upload");
 sel=1;repeat(10)@(negedge c);sof;
 if(!held || nb!=upload_bank || id!=1)$fatal(1,"reselect changed upload identity");
 rel=1;@(negedge c);rel=0;repeat(4)@(negedge c);valid=0;acq=1;repeat(10)@(negedge c);
 if(grant||held)$fatal(1,"stale acquisition");acq=0;
 // Restart input session and ID. Board-global publication namespace continues.
 input_id=1;sid=8;valid=1;start;publish;acquire;
 if(latest!=4||id!=4||rawid!=1||session!=8)$fatal(1,"restart identity alias");
 $display("MAP_OWNER_PASS four_slots=1 independent_display_upload_pins=1 partial_not_published=1 view_switch_retains_upload=1 stale_denied=1 restart_mapping=1");$finish;
 end
 initial begin #1000000;$fatal(1,"owner timeout");end
endmodule
