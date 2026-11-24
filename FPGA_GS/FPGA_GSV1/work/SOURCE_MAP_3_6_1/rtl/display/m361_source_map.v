`timescale 1ns/1ps
// Physical order is fixed by DDR addresses: CAM0,CAM1,HDMI,NET.
// Logical order controls KEY5, titles, quadrants and health: FRONT,REAR,LEFT,RIGHT.
module m361_source_map(input [63:0] physical_rgb,input [3:0] physical_de,physical_health,
 output [63:0] logical_rgb,output [3:0] logical_de,logical_health,
 input [3:0] logical_selected,logical_request,output [3:0] physical_selected,physical_request);
 assign logical_rgb={physical_rgb[31:16],physical_rgb[15:0],physical_rgb[47:32],physical_rgb[63:48]};
 assign logical_de={physical_de[1:0],physical_de[2],physical_de[3]};
 assign logical_health={physical_health[1:0],physical_health[2],physical_health[3]};
 assign physical_selected={logical_selected[0],logical_selected[1],logical_selected[3],logical_selected[2]};
 assign physical_request={logical_request[0],logical_request[1],logical_request[3],logical_request[2]};
endmodule
