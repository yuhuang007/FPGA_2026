`timescale 1ns/1ps
module map_cancel_tb;
 reg c=0,rst=0,on=1;always #5 c=~c;wire acq,rel,grant;reg held=0,delayed_req=0;assign grant=delayed_req;reg[1:0]bank=0;reg[31:0]identity=1;
 wire av;reg arr=0,rv=0,last=0;wire[27:0]addr;wire[3:0]len;wire ready;reg taken=0;wire[31:0]frames,aborts;
 m3_upload #(.NET_SOURCE(1)) dut(.clk(c),.rst_n(rst),.online(on),.tick_ms(1'b1),.fps(8'd15),.acquire(acq),.release_frame(rel),.grant(grant),.held(held),.bank(bank),.identity(identity),.stamp(32'd42),.fragment_ready(ready),.fragment_taken(taken),.word_addr(9'd0),.word_data(),.araddr(addr),.arlen(len),.arvalid(av),.arready(arr),.rdata(256'd0),.rvalid(rv),.rlast(last),.frames(frames),.aborts(aborts));
 always @(posedge c)begin delayed_req<=0;if(acq&&!held)begin delayed_req<=1;held<=1;end if(rel)held<=0;end
 integer n,j,k;
 task response;begin wait(av);@(negedge c);n=len+1;arr=1;for(j=0;j<n;j=j+1)begin rv=1;last=j==n-1;@(negedge c);arr=0;end rv=0;last=0;end endtask
 initial begin
 #100;rst=1;wait(acq);@(negedge c);on=0;repeat(10)@(negedge c);if(held||av)$fatal(1,"ACQUIRE cancel pin leak");
 for(k=0;k<4;k=k+1)begin bank=k;identity=k+1;on=1;wait(av);case(k)0:if(addr!=28'h1800000)$fatal;1:if(addr!=28'h1c00000)$fatal;2:if(addr!=28'h2400000)$fatal;3:if(addr!=28'h2c00000)$fatal;endcase
 on=0;response;wait(rel);repeat(5)@(negedge c);if(held)$fatal(1,"drain pin leak");end
 $display("MAP_CANCEL_PASS acquire_race=1 four_slot_upload_addresses=1 source_loss_inflight_drain=1");$finish;
 end
 initial begin #100000;$fatal(1,"cancel timeout state=%d",dut.state);end
endmodule
