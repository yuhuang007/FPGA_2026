module cam1_io_probe(input cmos2_pclk,input [7:0] cmos2_data,input cmos2_href,cmos2_vsync,output probe_out);
wire io_clock;
assign io_clock=cmos2_pclk;
reg [9:0] input_stage;
reg [9:0] second_stage;
always @(posedge io_clock) begin
 input_stage <= {cmos2_vsync,cmos2_href,cmos2_data};
 second_stage <= input_stage;
end
assign probe_out=^second_stage;
endmodule
