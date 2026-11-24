`timescale 1ns/1ps
// Two-register OSD timing matches m31_text. No source pixels are changed.
module cam1_blc_label(input clk,input[10:0] x,y,input[2:0] phase,output area,pixel);
 reg[127:0] text;reg[7:0] ch;reg[2:0] row,col;reg a0,a1,p1;
 wire[10:0] xx=x-12,yy=y-84;
 always @* case(phase)
  0:text="BLC COVER PREP  ";1:text="BLC A UPDATE    ";
  2:text="BLC B FREEZE    ";3:text="BLC APR RESTORE ";
  4:text="BLC DONE        ";default:text="BLC INVALID     ";
 endcase
 function[34:0] glyph(input[7:0] c);
 begin case(c)
  8'd65:glyph=35'b01110100011000111111100011000110001;
  8'd66:glyph=35'b11110100011000111110100011000111110;
  8'd67:glyph=35'b01111100001000010000100001000001111;
  8'd68:glyph=35'b11110100011000110001100011000111110;
  8'd69:glyph=35'b11111100001000011110100001000011111;
  8'd70:glyph=35'b11111100001000011110100001000010000;
  8'd73:glyph=35'b11111001000010000100001000010011111;
  8'd76:glyph=35'b10000100001000010000100001000011111;
  8'd78:glyph=35'b10001110011100110101100111001110001;
  8'd79:glyph=35'b01110100011000110001100011000101110;
  8'd80:glyph=35'b11110100011000111110100001000010000;
  8'd82:glyph=35'b11110100011000111110101001001010001;
  8'd83:glyph=35'b01111100001000001110000010000111110;
  8'd84:glyph=35'b11111001000010000100001000010000100;
  8'd85:glyph=35'b10001100011000110001100011000101110;
  8'd86:glyph=35'b10001100011000110001100010101000100;
  8'd90:glyph=35'b11111000010001000100010001000011111;
  default:glyph=0;
 endcase end endfunction
 wire[34:0] bits=glyph(ch);
 always @(posedge clk) begin
  ch<=text[127-xx[6:3]*8-:8];row<=yy[3:1];col<=xx[2:0];
  a0<=x>=12 && x<140 && y>=84 && y<98;
  a1<=a0;p1<=col<5 && row<7 ? bits[34-row*5-col]:0;
 end
 assign area=a1;assign pixel=p1;
endmodule
