`timescale 1ns/1ps
module map_network_tb;
 GTP_GRS GRS_INST(.GRS_N(1'b1));
 reg clk=0,nc=0,pc=0,rst=0,link=1;always #5 clk=~clk;always #4 nc=~nc;always #3.367 pc=~pc;
 reg [1:0] rxv=0;reg [15:0] rxd=0;wire[15:0] txd;wire[1:0] txv;
 wire[7:0] pend,ack;wire[127:0] lengths;wire[25:0] rxaddr;wire[15:0] rxdata;
 wire[1:0] tw,tr,tack;wire[21:0] ta;wire[15:0] td;wire[31:0] tl;
 wire[63:0] crc,over;wire[127:0] stats;
 genvar z;generate for(z=0;z<2;z=z+1)begin:port_mac
 m3_mac mac(.nc(nc),.nrst(rst && (z==1 || link)),.rxd(rxd[z*8+:8]),.rxv(rxv[z]),.rxe(1'b0),.txd(txd[z*8+:8]),.txv(txv[z]),
 .dc(clk),.drst(rst && (z==1 || link)),.rx_pending(pend[z*4+:4]),.rx_ack(ack[z*4+:4]),.rx_lengths(lengths[z*64+:64]),.rx_addr(rxaddr[z*13+:13]),.rx_data(rxdata[z*8+:8]),
 .tx_we(tw[z]),.tx_addr(ta[z*11+:11]),.tx_data(td[z*8+:8]),.tx_req(tr[z]),.tx_length(tl[z*16+:16]),.tx_ack(tack[z]),.crc_errors(crc[z*32+:32]),.rx_overruns(over[z*32+:32]),.rx_stats(stats[z*64+:64]));
 end endgenerate
 wire begin_frame,begin_ack,publish,healthy,store_ready;wire[1:0] wb;
 wire[31:0] input_id,input_stamp,pub_count,session1;wire[31:0] latest_id;
 wire acq,rel,grant,held;wire[1:0] nb;wire[31:0] nid,ntime;
 wire online1,online2,tick;wire[7:0] fps;reg ke=0;reg[3:0] kc=0;wire[2:0] feedback;
 wire frag,taken;wire[31:0] fid,ft,off;wire[15:0] fi;wire[8:0] wa;wire[31:0] word,uploaded,aborted;
 wire front_valid=healthy&&store_ready;
 wire[139:0] saw,sar;wire[19:0] swlen,srlen;wire[4:0] swv,srv,swr,srr,sready,slast,svalid,srlast;wire[1279:0] swdata;
 wire[27:0] aw,ar;wire[3:0] wl,rl;wire awv,arv;wire[255:0] wd;reg awr=0,arr=0,wr=0,wlast=0,rv=0,rlast=0;reg[255:0] rd=0;
 assign saw[83:0]=0;assign saw[139:112]=0;assign swlen[11:0]=0;assign swlen[19:16]=0;assign swv={1'b0,1'b0,3'b0}|{1'b0,core1.awvalid,3'b0};
 assign swdata[767:0]=0;assign swdata[1279:1024]=0;
 assign sar[83:0]=0;assign srlen[11:0]=0;assign srv[2:0]=0;
 m3_net_core #(.MS_CYCLES(10000),.ENABLE_CONTROL(0),.ENABLE_UPLOAD(0),.REQUIRE_LINK(1)) core1(
 .clk(clk),.rst_n(rst),.rx_reset_n(link),.rx_pending(pend[3:0]),.rx_ack(ack[3:0]),.rx_lengths(lengths[63:0]),.rx_addr(rxaddr[12:0]),.rx_data(rxdata[7:0]),
 .tx_we(tw[0]),.tx_addr(ta[10:0]),.tx_data(td[7:0]),.tx_req(tr[0]),.tx_length(tl[15:0]),.tx_ack(tack[0]),
 .right_begin(begin_frame),.right_begin_ack(begin_ack),.right_bank(wb),.right_publish(publish),.right_id(input_id),.right_stamp(input_stamp),.right_healthy(healthy),
 .awaddr(saw[111:84]),.awlen(swlen[15:12]),.awvalid(),.awready(swr[3]),.wdata(swdata[1023:768]),.wstrb(),.wready(sready[3]),.wlast(slast[3]),
 .key_event(1'b0),.key_code(4'd0),.latest_front_id(32'd0),.front_valid(1'b0),.feedback(),.online(online1),.tick_ms(),.upload_fps(),
 .fragment_ready(1'b0),.front_id(32'd0),.front_time(32'd0),.front_offset(32'd0),.front_index(16'd0),.front_word_data(32'd0),
 .mac_crc_errors(stats[63:32]),.mac_overruns(stats[31:0]),.displayed_frames(32'd0),.session(session1),.right_frames(pub_count));
 m3_net_core #(.LOCAL_MAC(48'h020047535632),.LOCAL_IP(32'hc0a83c02),.HOST_IP(32'hc0a83c01),.MS_CYCLES(10000),.ENABLE_VIDEO(0),.REQUIRE_LINK(1),.REQUIRE_FRONT(1)) core2(
 .clk(clk),.rst_n(rst),.rx_reset_n(1'b1),.rx_pending(pend[7:4]),.rx_ack(ack[7:4]),.rx_lengths(lengths[127:64]),.rx_addr(rxaddr[25:13]),.rx_data(rxdata[15:8]),
 .tx_we(tw[1]),.tx_addr(ta[21:11]),.tx_data(td[15:8]),.tx_req(tr[1]),.tx_length(tl[31:16]),.tx_ack(tack[1]),
 .right_begin_ack(1'b0),.right_bank(2'd0),.awready(1'b0),.wready(1'b0),.wlast(1'b0),
 .key_event(ke),.key_code(kc),.latest_front_id(latest_id),.front_valid(front_valid),.feedback(feedback),.online(online2),.tick_ms(tick),.upload_fps(fps),
 .fragment_ready(frag),.fragment_taken(taken),.front_id(fid),.front_time(ft),.front_offset(off),.front_index(fi),.front_word_addr(wa),.front_word_data(word),
 .mac_crc_errors(stats[127:96]),.mac_overruns(stats[95:64]),.displayed_frames(32'd0));
 reg fs=0,selected=1;always begin #16666000;fs=1;#100;fs=0;end
 m3_right_store #(.HD_DISPLAY(1)) store(.clk(clk),.rst_n(rst),.pc(pc),.fs(fs),.selected(selected),.quarter(1'b0),.request(1'b0),
 .begin_frame(begin_frame),.begin_ack(begin_ack),.write_bank(wb),.publish(publish),.frame_id(input_id),.frame_stamp(input_stamp),.frame_session(session1),.source_valid(front_valid),
 .net_acquire(acq),.net_release(rel),.net_grant(grant),.net_held(held),.net_bank(nb),.net_id(nid),.net_time(ntime),.latest_id(latest_id),.ready(store_ready),
 .araddr(sar[111:84]),.arlen(srlen[15:12]),.arvalid(srv[3]),.arready(srr[3]),.rdata(rd),.rvalid(svalid[3]),.rlast(srlast[3]));
 m3_upload #(.NET_SOURCE(1)) upload(.clk(clk),.rst_n(rst),.online(online2&&front_valid),.tick_ms(tick),.fps(fps),
 .acquire(acq),.release_frame(rel),.grant(grant),.held(held),.bank(nb),.identity(nid),.stamp(ntime),.fragment_ready(frag),.fragment_taken(taken),.frame_id(fid),.frame_time(ft),.offset(off),.index(fi),.word_addr(wa),.word_data(word),
 .araddr(sar[139:112]),.arlen(srlen[19:16]),.arvalid(srv[4]),.arready(srr[4]),.rdata(rd),.rvalid(svalid[4]),.rlast(srlast[4]),.frames(uploaded),.aborts(aborted));
 dual_ddr_arbiter #(.PORTS(5)) arb(.clk(clk),.rst_n(rst),.s_awaddr(saw),.s_awlen(swlen),.s_awvalid(swv),.s_awready(swr),.s_wdata(swdata),.s_wstrb({160{1'b1}}),.s_wready(sready),.s_wlast(slast),
 .s_araddr(sar),.s_arlen(srlen),.s_arvalid(srv),.s_arready(srr),.s_rvalid(svalid),.s_rlast(srlast),.awaddr(aw),.awlen(wl),.awvalid(awv),.awready(awr),.wdata(wd),.wready(wr),.wlast(wlast),.araddr(ar),.arlen(rl),.arvalid(arv),.arready(arr),.rvalid(rv),.rlast(rlast));
 reg[255:0] mem[0:230399];integer cycles=0,writes=0,reads=0,overlap=0;always @(posedge clk)cycles<=cycles+1;
 function integer slot(input[27:0] a);case(a>>22)6:slot=0;7:slot=1;9:slot=2;11:slot=3;default:begin $fatal(1,"non NET address %h",a);slot=0;end endcase endfunction
 function integer ix(input[27:0] a);begin if(a[21:0]>=460800||a%8)$fatal(1,"DDR bounds %h",a);ix=slot(a)*57600+(a[21:0]>>3);end endfunction
 reg write_active=0;integer waddr,raddr,wn,rn,wi,ri;
 initial begin wait(rst);forever begin wait(awv);@(negedge clk);waddr=ix(aw);wn=wl+1;if(held&&slot(aw)==nb || store.held&&slot(aw)==store.rbank)$fatal(1,"overwrites reader");
 if(writes%1703==3)repeat(100)@(negedge clk);while(rv)@(negedge clk);write_active=1;awr=1;
 if(writes%2)begin @(posedge clk);@(negedge clk);awr=0;end
 for(wi=0;wi<wn;wi=wi+1)begin wr=1;wlast=wi==wn-1;@(posedge clk);mem[waddr+wi]=wd;@(negedge clk);awr=0;wr=0;wlast=0;end
 write_active=0;writes=writes+1;if(held)overlap=overlap+1;end end
 initial begin wait(rst);forever begin wait(arv);@(negedge clk);raddr=ix(ar);rn=rl+1;while(write_active)@(negedge clk);arr=1;
 if(reads%2)begin @(posedge clk);@(negedge clk);arr=0;end
 for(ri=0;ri<rn;ri=ri+1)begin if(ri%5==2)repeat(2)@(negedge clk);while(write_active)@(negedge clk);rd=mem[raddr+ri];rv=1;rlast=ri==rn-1;@(posedge clk);@(negedge clk);arr=0;rv=0;rlast=0;end reads=reads+1;end end
 reg[7:0] packet_mem[0:4095];
 function[31:0] crc_byte(input[31:0] c,input[7:0] d);reg[31:0] v;integer j;begin v=c;for(j=0;j<8;j=j+1)v=(v[0]^d[j])?((v>>1)^32'hedb88320):(v>>1);crc_byte=v;end endfunction
 task put16(input integer p,o,v);begin packet_mem[p*2048+o]=v>>8;packet_mem[p*2048+o+1]=v;end endtask
 task put32(input integer p,o,input[31:0] v);begin packet_mem[p*2048+o]=v>>24;packet_mem[p*2048+o+1]=v>>16;packet_mem[p*2048+o+2]=v>>8;packet_mem[p*2048+o+3]=v;end endtask
 function[15:0] pattern(input integer rawid,px);pattern=(16'hbd01^(rawid*16'h031d)^(px*16'h9e37)^(px/1280*16'h0101));endfunction
 // Both independent hosts call this task concurrently. Per-call storage is
 // required across the GMII waits; static locals corrupt the other port.
 task automatic packet(input integer p,kind,input[31:0] sid,rawid,input integer idx,eid,seq,ttl,code);
 integer n,b,i,s;reg[15:0] v;reg[31:0] cv;begin
 b=p*2048;n=kind==16?1370:90;for(i=0;i<n;i=i+1)packet_mem[b+i]=0;
 packet_mem[b]=2;packet_mem[b+2]=8'h47;packet_mem[b+3]=8'h53;packet_mem[b+4]=8'h56;packet_mem[b+5]=8'h31+p;
 for(i=6;i<12;i=i+1)packet_mem[b+i]=8'ha0+i+p;
 put16(p,12,16'h0800);packet_mem[b+14]=8'h45;put16(p,16,n-14);put16(p,20,16'h4000);packet_mem[b+22]=64;packet_mem[b+23]=17;
 put32(p,26,p==0?32'hc0a83201:32'hc0a83c01);put32(p,30,p==0?32'hc0a83202:32'hc0a83c02);put16(p,34,50000);put16(p,36,50000);put16(p,38,n-34);
 put32(p,42,32'h47535633);packet_mem[b+46]=1;packet_mem[b+47]=kind;packet_mem[b+48]=kind==16?3:0;packet_mem[b+49]=1;
 put32(p,50,sid);put32(p,54,rawid);put32(p,58,999);put16(p,62,1280);put16(p,64,720);put32(p,66,idx*1280);put16(p,70,kind==16?1280:0);put16(p,72,idx);put16(p,74,kind==16?1440:0);put32(p,78,eid);put32(p,82,seq);put16(p,86,ttl);packet_mem[b+88]=code;packet_mem[b+89]=kind==1&&p==1?15:0;
 if(kind==16)for(i=0;i<640;i=i+1)begin v=pattern(rawid,idx*640+i);packet_mem[b+90+i*2]=v;packet_mem[b+91+i*2]=v>>8;end
 s=0;for(i=14;i<34;i=i+2)s=s+{packet_mem[b+i],packet_mem[b+i+1]};s=(s&65535)+(s>>16);put16(p,24,~s);
 s=16'hc0a8+(p==0?16'h3201:16'h3c01)+16'hc0a8+(p==0?16'h3202:16'h3c02)+17+n-34;
 for(i=34;i<n;i=i+2)s=s+{packet_mem[b+i],packet_mem[b+i+1]};s=(s&65535)+(s>>16);s=(s&65535)+(s>>16);put16(p,40,(~s)&65535);
 @(negedge nc);rxv[p]=1;rxd[p*8+:8]=8'h55;repeat(7)@(negedge nc);rxd[p*8+:8]=8'hd5;@(negedge nc);cv=~0;
 for(i=0;i<n;i=i+1)begin rxd[p*8+:8]=packet_mem[b+i];cv=crc_byte(cv,rxd[p*8+:8]);@(negedge nc);end
 cv=~cv;for(i=0;i<4;i=i+1)begin rxd[p*8+:8]=cv>>(8*i);@(negedge nc);end
 rxv[p]=0;repeat(12)@(negedge nc);
 end endtask
 reg [7:0] txmem[0:2047];reg txactive=0;integer txsize=0,rawpackets=0,rawcomplete=0,eventpackets=0,accepted=0,rejected=0,txi,ridx,rfid,expected_raw;
 reg[31:0] txcrc,expected_event=0;reg[15:0] want;
 function[31:0] gettx(input integer o);gettx={txmem[o],txmem[o+1],txmem[o+2],txmem[o+3]};endfunction
 always @(negedge nc)begin
 if(txv[1])begin
  if(!txactive)begin if(txd[15:8]==8'hd5)begin txactive=1;txsize=0;txcrc=~0;end end
  else begin txmem[txsize]=txd[15:8];txsize=txsize+1;txcrc=crc_byte(txcrc,txd[15:8]);end
 end else if(txactive)begin
  if(txcrc!==32'hdebb20e3)$fatal(1,"port2 output FCS");
  if(txmem[47]==17)begin
   rfid=gettx(54);ridx={txmem[72],txmem[73]};case(rfid)1:expected_raw=42;2:expected_raw=44;3:expected_raw=1;default:$fatal(1,"unexpected upload ID %d",rfid);endcase
   if(txmem[48]!=0||txsize!=1374||gettx(66)!=ridx*1280)$fatal(1,"upload profile");
   for(txi=0;txi<640;txi=txi+1)begin want=pattern(expected_raw,ridx*640+txi);if({txmem[91+txi*2],txmem[90+txi*2]}!==want)$fatal(1,"raw content/ID mismatch fid=%d idx=%d pixel=%d",rfid,ridx,txi);end
   rawpackets=rawpackets+1;if(ridx==1439)rawcomplete=rawcomplete+1;
  end
  if(txmem[47]==4)begin if(gettx(54)!=expected_event)$fatal(1,"EVENT namespace mismatch %d/%d",gettx(54),expected_event);eventpackets=eventpackets+1;end
  if(txmem[47]==7)begin if(txmem[88]==1)accepted=accepted+1;else rejected=rejected+1;end
  txactive=0;
 end end
 reg p2busy=0;
 initial begin wait(online2);forever begin #20000000;if(!p2busy)begin p2busy=1;packet(1,3,32'h22222222,0,0,0,0,2000,0);p2busy=0;end end end
 task key(input integer code);begin @(negedge clk);expected_event=front_valid?latest_id:0;kc=code;ke=1;@(negedge clk);ke=0;repeat(10)@(negedge clk);if(core2.event_frame!=expected_event)$fatal(1,"latched wrong event ID");end endtask
 integer j,before_frames,saved;
 initial begin
 #500;rst=1;packet(0,1,32'h11111111,0,0,0,0,2000,0);packet(1,1,32'h22222222,0,0,0,0,2000,0);wait(online1&&online2);
 for(j=0;j<1440;j=j+1)begin packet(0,16,32'h11111111,42,j,0,0,2000,0);#35000;
 if(core1.bad_packets || core1.sequence_errors || crc || over)$fatal(1,"frame42 RX faults idx=%d bad=%d seq=%d crc=%h over=%h",j,core1.bad_packets,core1.sequence_errors,crc,over);
 if(j%360==359)$display("NETWORK_PROGRESS input42 fragments=%d simulated_ns=%t",j+1,$time);end
 wait(latest_id==1);$display("NETWORK_PROGRESS first publication id=1 time=%t",$time);if(!front_valid)$fatal(1,"complete not healthy");key(3);
 wait(eventpackets>0);while(p2busy)@(negedge clk);p2busy=1;packet(1,6,32'h22222222,1,0,1,1,2000,1);p2busy=0;wait(accepted==1);
 if(feedback!=1)$fatal(1,"RESULT acceptance");
 // A partial newer input cannot change EVENT or upload identity.
 for(j=0;j<40;j=j+1)begin packet(0,16,32'h11111111,43,j,0,0,2000,0);#35000;end
 if(latest_id!=1)$fatal(1,"partial publication");
 for(j=0;j<1440;j=j+1)begin packet(0,16,32'h11111111,44,j,0,0,2000,0);#35000;end
 wait(latest_id==2);wait(rawcomplete>=2);$display("NETWORK_PROGRESS second complete upload time=%t",$time);if(overlap==0)$fatal(1,"no simultaneous RX/write and upload");
 // Model ingress link epoch loss only. Port2 remains alive, no CAM0 fallback.
 @(negedge clk);link=0;repeat(20)@(negedge clk);if(front_valid||feedback!=0)$fatal(1,"stale feedback");key(1);if(core2.event_frame!=0)$fatal(1,"stale KEY borrowed frame");
 while(p2busy)@(negedge clk);p2busy=1;packet(1,6,32'h22222222,2,0,2,1,2000,1);p2busy=0;wait(rejected>0);saved=rawcomplete;
 #210000000;link=1;repeat(30)@(negedge clk);$display("NETWORK_PROGRESS ingress epoch restore time=%t",$time);if(held)$fatal(1,"offline leaked reader pin");if(rawcomplete!=saved)$fatal(1,"stale complete uploads");
 packet(0,1,32'h33333333,0,0,0,0,2000,0);wait(session1==32'h33333333);
 for(j=0;j<1440;j=j+1)begin packet(0,16,32'h33333333,1,j,0,0,2000,0);#35000;end
 wait(latest_id==3);wait(rawcomplete>=3);key(4);
 if(crc!=0||over!=0||pub_count!=3||core1.bad_packets!=0)$fatal(1,"RX faults crc=%h over=%h bad=%d pubs=%d",crc,over,core1.bad_packets,pub_count);
 $display("MAP_NETWORK_PASS complete_inputs=%0d uploaded_complete=%0d pixel_checks=%0d dual_MAC_FCS=1 event_exact=1 stale_no_fallback=1 restart_namespace=1 overlapped_writes=%0d DDR_stalls=1",pub_count,rawcomplete,rawpackets*640,overlap);$finish;
 end
 initial begin #600000000;$fatal(1,"timeout pubs=%d uploads=%d frontvalid=%b p1=%d p2=%b",pub_count,uploaded,front_valid,core1.rs,online2);end
endmodule
