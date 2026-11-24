`timescale 1ns/1ps
module patch_uart_tb;
 reg clk=0,rst=0;always #10 clk=~clk;wire tx;
 wire[1279:0] values={640'd0,640'h43315058000000020001010004600000001002d000000000d3a214ae000000189b8ee63be0a4e351eddae847eaf0f57df7e6f193fc1cfe89f932fbbfc628c0d59ebfe30ae595e660e8ebed76efc1f04c};
 m361_uart_hex #(.TICKS(9000),.BAUD_DIV(2),.REVISION_ASCII("P")) dut(.clk(clk),.rst_n(rst),.values(values),.tx(tx));
 integer f,count=0;reg[7:0] c;
 initial begin f=$fopen("../reports/patch_uart_line.txt","w");#1;rst=0;#80;rst=1;end
 initial forever begin
  @(negedge tx);#60;
  for(integer i=0;i<8;i++) begin c[i]=tx;#40;end
  if(tx!==1) $fatal(1,"UART stop");
  $fwrite(f,"%c",c);count++;if(count==369) begin $fclose(f);$display("PASS production UART369bytes");$finish;end
 end
 initial begin #1000000;$fatal(1,"UART deadline");end
endmodule
