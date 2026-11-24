`timescale 1ns/1ps
module cam1_blc_control_tb;
 reg clk=0;always #500 clk=~clk;
 reg rst=0,en=0;tri1 scl,sda;reg low=0;assign sda=low?1'b0:1'bz;
 reg complete=0,token=0;reg[31:0] fid=0,ms=0;
 wire request,ex,failed,restored,resumed;wire[2:0] phase,mask;
 wire[7:0] error;wire[31:0] sid;wire[639:0] pre,post,status;
 cam1_blc_control #(.CLOCK_HZ(1000000),.SCCB_HZ(100000),.COVER_TICKS(10),
 .SETTLE_TICKS(20),.EXPORT_TICKS(50),.CAPTURE_TIMEOUT(300)) dut(
 .clk(clk),.rst_n(rst),.enable(en),.scl(scl),.sda(sda),.milliseconds(ms),.source_frame_id(fid),
 .strip_complete(complete),.strip_token(token),.strip_frame_id(fid),.request_toggle(request),
 .phase(phase),.export_enabled(ex),.failed(failed),.restored(restored),.blc_restored(resumed),
 .error_code(error),.completed_mask(mask),.sample_id(sid),.pre_page(pre),.post_page(post),.status_page(status));
 reg[7:0] mem[0:65535];integer mode=0,writes=0,scans=0,freezes=0,redo=0;
 reg injected=0;reg[7:0] hi,lo,v,adr;reg[15:0] a;
 task start_bus;begin do @(negedge sda);while(scl!==1);end endtask
 task stop_bus;begin do @(posedge sda);while(scl!==1);end endtask
 task getbyte(output[7:0] value);begin for(integer i=7;i>=0;i--)begin @(posedge scl);#1;value[i]=sda;end end endtask
 task ack(input bit reject);begin @(negedge scl);#1;low=!reject;@(posedge scl);@(negedge scl);#1;low=0;end endtask
 task putbyte(input[7:0] value);begin
  for(integer i=7;i>=0;i--)begin low=!value[i];@(posedge scl);@(negedge scl);#1;end
  low=0;@(posedge scl);#1;if(sda!==1)$fatal(1,"read final NACK");@(negedge scl);stop_bus();
 end endtask
 // Pin-level slave: every address and write is independently decoded from SDA.
 initial forever begin : transaction
  bit reject;
  start_bus();getbyte(adr);if(adr!==8'h78)$fatal(1,"SCCB address %h",adr);
  reject=((mode==1 || (mode==7 && dut.state==5)) && !injected);if(reject)injected=1;
  ack(reject);if(reject)begin stop_bus();end
  else begin
   getbyte(hi);ack(0);getbyte(lo);a={hi,lo};ack(0);
   if(dut.state==2 || dut.state==7)begin
    start_bus();getbyte(adr);if(adr!==8'h79)$fatal(1,"read address");ack(0);v=mem[a];
    if(mode==2 && a==16'h3503 && writes==1 && !injected)begin v=v^1;injected=1;end
    if(mode==3 && phase==1 && dut.scan_kind==3 && a==16'h3502 && !injected)begin v=v^16;injected=1;end
    if(mode==4 && phase==2 && dut.scan_kind==3 && a==16'h402c && !injected)begin v=v^1;injected=1;end
    if(mode==6 && dut.program_kind==4 && a==16'h4003) v=v^1;
    putbyte(v);
   end else begin
    getbyte(v);ack(0);stop_bus();writes++;
    if(!(a==16'h3503 || a==16'h3406 || a==16'h4003 || a==16'h4005 ||
       (a>=16'h3500 && a<=16'h3502) || a==16'h350a || a==16'h350b ||
       (a>=16'h3400 && a<=16'h3405)))$fatal(1,"write outside whitelist %h",a);
    if(a==16'h4003 && v[7])$fatal(1,"REDO command replayed");
    if(a==16'h4003 && v[6])begin
      if(mem[16'h4005][1])$fatal(1,"always update not disabled before freeze");
      if(v[5:0]!==6'h01)$fatal(1,"freeze clobbers reserved bits");freezes++;
    end
    mem[a]=v;
   end
  end
 end
 always @(posedge clk) if(!rst) begin complete<=0;token<=0;fid<=0;ms<=0;end
 else begin
  ms<=ms+1;
  if(request!=token && mode!=5)begin token<=request;complete<=1;fid<=fid+1;end
 end
 task defaults;begin
  for(integer i=0;i<65536;i++)mem[i]=0;
  mem['h300a]='h36;mem['h300b]='h60;mem['h3503]='h80;mem['h3406]='h20;
  mem['h4000]='h09;mem['h4002]='hc5;mem['h4003]='h81;mem['h4005]='h12;
  mem['h3501]='h31;mem['h3502]='hc0;mem['h350b]='h60;
  mem['h3400]=4;mem['h3402]=4;mem['h3404]=4;
  mem['h303b]='h18;mem['h303c]='h12;mem['h303d]='h20;mem['h380c]=7;mem['h380d]=8;mem['h380e]=3;mem['h380f]='h20;
  for(integer i=0;i<8;i++)mem['h402c+i]=8'h27+i;
  writes=0;freezes=0;injected=0;
 end endtask
 integer out;reg old_ex=0;
always @(negedge clk)begin
 if(mode==0 && ex && !old_ex)begin $fdisplay(out,"BLCMETA %0160h",pre);$fdisplay(out,"BLCMETA %0160h",post);$fdisplay(out,"BLCMETA %0160h",status);end
 old_ex=ex;end
task run(input integer m);begin
  @(negedge clk);en=0;rst=0;mode=m;defaults();repeat(4)@(negedge clk);
  rst=1;repeat(5)@(negedge clk);if(dut.read_start||dut.write_start)$fatal(1,"preinit bus");en=1;
  wait(dut.state==11);#1;
  if(m==0)begin
   if(failed||!restored||!resumed||phase!=4||mask!=7||freezes!=1||writes!=21)
    $fatal(1,"success flags phase%0d mask%0d w%0d error%0d orig%h fixed%h staging%h",phase,mask,writes,error,dut.original_regs,dut.fixed_regs,dut.staging);
   $fdisplay(out,"BLCMETA %0160h",status);
  end else if(!failed || phase!=5)$fatal(1,"failure falsely successful mode%0d",m);
  if(m==1 && (writes!=0||restored))$fatal(1,"read failed yet changed sensor");
  if(m>1 && m!=6 && !restored)$fatal(1,"best effort restore failed");
  if(m==6 && restored)$fatal(1,"bad restore readback claimed success");
  if(m!=1 && (mem['h4003]!==1||mem['h4005]!=='h12||mem['h3503]!=='h80||mem['h3406]!=='h20))
   $fatal(1,"original operating bits not restored");
  $display("PASS control scenario %0d err%0d writes%0d restored%0d",m,error,writes,restored);
 end endtask
 initial begin out=$fopen("blc_meta_pages.txt","w");for(integer i=0;i<=7;i++)run(i);$fclose(out);$display("PASS BLC actual SCCB: A/B/AP, RMW, command-bit exclusion, NACK, readback/parameter/coeff drift, capture timeout, verified restore failures");$finish;end
 initial begin #4000000000;$fatal(1,"test deadline mode%0d state%0d",mode,dut.state);end
endmodule


