module cmos_8_16bit
(
    input [7:0] pdata_i,
    input de_i,
    input pclk,
    input rst_n,
    input vs_i,
    output [15:0] pdata_o,
    output de_o,
    output pixel_clk
);
    wire N0_1;
    wire N11;
    wire [1:0] N17;
    wire N48;
    wire _N142617;
    wire _N142619;
    wire [1:0] cnt;
    wire de_i_r;
    wire de_i_r1;
    wire de_out1;
    wire de_out2;
    wire de_out3;
    wire enble;
    wire pclk_IOCLKBUF;
    wire [7:0] pdata_i_reg;
    wire [15:0] pdata_out1;
    wire [15:0] pdata_out2;
    wire [15:0] pdata_out3;
    wire vs_i_reg;

    GTP_INV N0_1_vname (
            .Z (N0_1),
            .I (rst_n));
    // defparam N0_1_vname.orig_name = N0_1;

    GTP_LUT3 /* N11_3 */ #(
            .INIT(8'b00001000))
        N11_3 (
            .Z (N11),
            .I0 (de_i),
            .I1 (cnt[0]),
            .I2 (cnt[1]));
	// LUT = I0&I1&~I2 ;

    GTP_LUT2 /* N17_sum1 */ #(
            .INIT(4'b0110))
        N17_sum1 (
            .Z (N17[1]),
            .I0 (cnt[0]),
            .I1 (cnt[1]));
	// LUT = (I0&~I1)|(~I0&I1) ;

    GTP_LUT4 /* N48 */ #(
            .INIT(16'b0011001110110011))
        N48_vname (
            .Z (N48),
            .I0 (de_i),
            .I1 (rst_n),
            .I2 (cnt[0]),
            .I3 (cnt[1]));
    // defparam N48_vname.orig_name = N48;
	// LUT = (~I1)|(I0&I2&~I3) ;
	// ../rtl/reuse/cmos_8_16bit.v:39

    GTP_DFF_RE /* \cnt[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \cnt[0]  (
            .Q (cnt[0]),
            .CE (de_i),
            .CLK (pclk),
            .D (N17[0]),
            .R (N48));
	// ../rtl/reuse/cmos_8_16bit.v:77

    GTP_LUT1 /* \cnt[1:0]_inv  */ #(
            .INIT(2'b01))
        \cnt[1:0]_inv  (
            .Z (N17[0]),
            .I0 (cnt[0]));
	// LUT = ~I0 ;

    GTP_DFF_RE /* \cnt[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \cnt[1]  (
            .Q (cnt[1]),
            .CE (de_i),
            .CLK (pclk),
            .D (N17[1]),
            .R (N48));
	// ../rtl/reuse/cmos_8_16bit.v:77

    GTP_DFF /* de_i_r */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_i_r_vname (
            .Q (de_i_r),
            .CLK (pclk),
            .D (de_i));
    // defparam de_i_r_vname.orig_name = de_i_r;
	// ../rtl/reuse/cmos_8_16bit.v:105

    GTP_DFF /* de_i_r1 */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_i_r1_vname (
            .Q (de_i_r1),
            .CLK (pclk),
            .D (de_i_r));
    // defparam de_i_r1_vname.orig_name = de_i_r1;
	// ../rtl/reuse/cmos_8_16bit.v:105

    GTP_DFF /* de_o */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_o_vname (
            .Q (de_o),
            .CLK (pixel_clk),
            .D (de_out3));
    // defparam de_o_vname.orig_name = de_o;
	// ../rtl/reuse/cmos_8_16bit.v:123

    GTP_DFF /* de_out1 */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_out1_vname (
            .Q (de_out1),
            .CLK (pclk),
            .D (_N142619));
    // defparam de_out1_vname.orig_name = de_out1;
	// ../rtl/reuse/cmos_8_16bit.v:109

    GTP_LUT4 /* de_out1_rs_mux */ #(
            .INIT(16'b1000101000001000))
        de_out1_rs_mux (
            .Z (_N142619),
            .I0 (rst_n),
            .I1 (de_i_r),
            .I2 (de_i_r1),
            .I3 (de_out1));
	// LUT = (I0&I1&~I2)|(I0&~I2&I3)|(I0&I1&I3) ;

    GTP_DFF /* de_out2 */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_out2_vname (
            .Q (de_out2),
            .CLK (pixel_clk),
            .D (de_out1));
    // defparam de_out2_vname.orig_name = de_out2;
	// ../rtl/reuse/cmos_8_16bit.v:123

    GTP_DFF /* de_out3 */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        de_out3_vname (
            .Q (de_out3),
            .CLK (pixel_clk),
            .D (de_out2));
    // defparam de_out3_vname.orig_name = de_out3;
	// ../rtl/reuse/cmos_8_16bit.v:123

    GTP_DFF /* enble */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        enble_vname (
            .Q (enble),
            .CLK (pclk),
            .D (_N142617));
    // defparam enble_vname.orig_name = enble;
	// ../rtl/reuse/cmos_8_16bit.v:50

    GTP_LUT4 /* enble_rs_mux */ #(
            .INIT(16'b1100000011001000))
        enble_rs_mux (
            .Z (_N142617),
            .I0 (vs_i),
            .I1 (rst_n),
            .I2 (enble),
            .I3 (vs_i_reg));
	// LUT = (I1&I2)|(I0&I1&~I3) ;

    GTP_DFF_RE /* \pdata_i_reg[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[0]  (
            .Q (pdata_i_reg[0]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[0]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[1]  (
            .Q (pdata_i_reg[1]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[1]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[2]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[2]  (
            .Q (pdata_i_reg[2]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[2]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[3]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[3]  (
            .Q (pdata_i_reg[3]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[3]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[4]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[4]  (
            .Q (pdata_i_reg[4]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[4]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[5]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[5]  (
            .Q (pdata_i_reg[5]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[5]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[6]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[6]  (
            .Q (pdata_i_reg[6]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[6]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF_RE /* \pdata_i_reg[7]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_i_reg[7]  (
            .Q (pdata_i_reg[7]),
            .CE (de_i),
            .CLK (pclk),
            .D (pdata_i[7]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:88

    GTP_DFF /* \pdata_o[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[0]  (
            .Q (pdata_o[0]),
            .CLK (pixel_clk),
            .D (pdata_out3[0]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[1]  (
            .Q (pdata_o[1]),
            .CLK (pixel_clk),
            .D (pdata_out3[1]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[2]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[2]  (
            .Q (pdata_o[2]),
            .CLK (pixel_clk),
            .D (pdata_out3[2]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[3]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[3]  (
            .Q (pdata_o[3]),
            .CLK (pixel_clk),
            .D (pdata_out3[3]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[4]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[4]  (
            .Q (pdata_o[4]),
            .CLK (pixel_clk),
            .D (pdata_out3[4]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[5]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[5]  (
            .Q (pdata_o[5]),
            .CLK (pixel_clk),
            .D (pdata_out3[5]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[6]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[6]  (
            .Q (pdata_o[6]),
            .CLK (pixel_clk),
            .D (pdata_out3[6]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[7]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[7]  (
            .Q (pdata_o[7]),
            .CLK (pixel_clk),
            .D (pdata_out3[7]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[8]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[8]  (
            .Q (pdata_o[8]),
            .CLK (pixel_clk),
            .D (pdata_out3[8]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[9]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[9]  (
            .Q (pdata_o[9]),
            .CLK (pixel_clk),
            .D (pdata_out3[9]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[10]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[10]  (
            .Q (pdata_o[10]),
            .CLK (pixel_clk),
            .D (pdata_out3[10]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[11]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[11]  (
            .Q (pdata_o[11]),
            .CLK (pixel_clk),
            .D (pdata_out3[11]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[12]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[12]  (
            .Q (pdata_o[12]),
            .CLK (pixel_clk),
            .D (pdata_out3[12]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[13]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[13]  (
            .Q (pdata_o[13]),
            .CLK (pixel_clk),
            .D (pdata_out3[13]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[14]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[14]  (
            .Q (pdata_o[14]),
            .CLK (pixel_clk),
            .D (pdata_out3[14]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_o[15]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_o[15]  (
            .Q (pdata_o[15]),
            .CLK (pixel_clk),
            .D (pdata_out3[15]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF_RE /* \pdata_out1[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[0]  (
            .Q (pdata_out1[0]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[0]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[1]  (
            .Q (pdata_out1[1]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[1]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[2]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[2]  (
            .Q (pdata_out1[2]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[2]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[3]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[3]  (
            .Q (pdata_out1[3]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[3]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[4]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[4]  (
            .Q (pdata_out1[4]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[4]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[5]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[5]  (
            .Q (pdata_out1[5]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[5]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[6]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[6]  (
            .Q (pdata_out1[6]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[6]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[7]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[7]  (
            .Q (pdata_out1[7]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i[7]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[8]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[8]  (
            .Q (pdata_out1[8]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[0]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[9]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[9]  (
            .Q (pdata_out1[9]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[1]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[10]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[10]  (
            .Q (pdata_out1[10]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[2]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[11]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[11]  (
            .Q (pdata_out1[11]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[3]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[12]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[12]  (
            .Q (pdata_out1[12]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[4]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[13]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[13]  (
            .Q (pdata_out1[13]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[5]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[14]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[14]  (
            .Q (pdata_out1[14]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[6]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF_RE /* \pdata_out1[15]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out1[15]  (
            .Q (pdata_out1[15]),
            .CE (N11),
            .CLK (pclk),
            .D (pdata_i_reg[7]),
            .R (N0_1));
	// ../rtl/reuse/cmos_8_16bit.v:96

    GTP_DFF /* \pdata_out2[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[0]  (
            .Q (pdata_out2[0]),
            .CLK (pixel_clk),
            .D (pdata_out1[0]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[1]  (
            .Q (pdata_out2[1]),
            .CLK (pixel_clk),
            .D (pdata_out1[1]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[2]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[2]  (
            .Q (pdata_out2[2]),
            .CLK (pixel_clk),
            .D (pdata_out1[2]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[3]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[3]  (
            .Q (pdata_out2[3]),
            .CLK (pixel_clk),
            .D (pdata_out1[3]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[4]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[4]  (
            .Q (pdata_out2[4]),
            .CLK (pixel_clk),
            .D (pdata_out1[4]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[5]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[5]  (
            .Q (pdata_out2[5]),
            .CLK (pixel_clk),
            .D (pdata_out1[5]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[6]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[6]  (
            .Q (pdata_out2[6]),
            .CLK (pixel_clk),
            .D (pdata_out1[6]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[7]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[7]  (
            .Q (pdata_out2[7]),
            .CLK (pixel_clk),
            .D (pdata_out1[7]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[8]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[8]  (
            .Q (pdata_out2[8]),
            .CLK (pixel_clk),
            .D (pdata_out1[8]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[9]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[9]  (
            .Q (pdata_out2[9]),
            .CLK (pixel_clk),
            .D (pdata_out1[9]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[10]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[10]  (
            .Q (pdata_out2[10]),
            .CLK (pixel_clk),
            .D (pdata_out1[10]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[11]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[11]  (
            .Q (pdata_out2[11]),
            .CLK (pixel_clk),
            .D (pdata_out1[11]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[12]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[12]  (
            .Q (pdata_out2[12]),
            .CLK (pixel_clk),
            .D (pdata_out1[12]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[13]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[13]  (
            .Q (pdata_out2[13]),
            .CLK (pixel_clk),
            .D (pdata_out1[13]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[14]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[14]  (
            .Q (pdata_out2[14]),
            .CLK (pixel_clk),
            .D (pdata_out1[14]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out2[15]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out2[15]  (
            .Q (pdata_out2[15]),
            .CLK (pixel_clk),
            .D (pdata_out1[15]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[0]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[0]  (
            .Q (pdata_out3[0]),
            .CLK (pixel_clk),
            .D (pdata_out2[0]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[1]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[1]  (
            .Q (pdata_out3[1]),
            .CLK (pixel_clk),
            .D (pdata_out2[1]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[2]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[2]  (
            .Q (pdata_out3[2]),
            .CLK (pixel_clk),
            .D (pdata_out2[2]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[3]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[3]  (
            .Q (pdata_out3[3]),
            .CLK (pixel_clk),
            .D (pdata_out2[3]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[4]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[4]  (
            .Q (pdata_out3[4]),
            .CLK (pixel_clk),
            .D (pdata_out2[4]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[5]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[5]  (
            .Q (pdata_out3[5]),
            .CLK (pixel_clk),
            .D (pdata_out2[5]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[6]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[6]  (
            .Q (pdata_out3[6]),
            .CLK (pixel_clk),
            .D (pdata_out2[6]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[7]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[7]  (
            .Q (pdata_out3[7]),
            .CLK (pixel_clk),
            .D (pdata_out2[7]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[8]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[8]  (
            .Q (pdata_out3[8]),
            .CLK (pixel_clk),
            .D (pdata_out2[8]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[9]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[9]  (
            .Q (pdata_out3[9]),
            .CLK (pixel_clk),
            .D (pdata_out2[9]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[10]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[10]  (
            .Q (pdata_out3[10]),
            .CLK (pixel_clk),
            .D (pdata_out2[10]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[11]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[11]  (
            .Q (pdata_out3[11]),
            .CLK (pixel_clk),
            .D (pdata_out2[11]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[12]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[12]  (
            .Q (pdata_out3[12]),
            .CLK (pixel_clk),
            .D (pdata_out2[12]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[13]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[13]  (
            .Q (pdata_out3[13]),
            .CLK (pixel_clk),
            .D (pdata_out2[13]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[14]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[14]  (
            .Q (pdata_out3[14]),
            .CLK (pixel_clk),
            .D (pdata_out2[14]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_DFF /* \pdata_out3[15]  */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        \pdata_out3[15]  (
            .Q (pdata_out3[15]),
            .CLK (pixel_clk),
            .D (pdata_out2[15]));
	// ../rtl/reuse/cmos_8_16bit.v:128

    GTP_IOCLKBUF /* u_GTP_IOCLKBUF */ #(
            .GATE_EN("FALSE"))
        u_GTP_IOCLKBUF (
            .CLKOUT (pclk_IOCLKBUF),
            .CLKIN (pclk),
            .DI (enble));
	// ../rtl/reuse/cmos_8_16bit.v:62

    GTP_IOCLKDIV /* u_GTP_IOCLKDIV */ #(
            .GRS_EN("TRUE"), 
            .DIV_FACTOR("2"))
        u_GTP_IOCLKDIV (
            .CLKDIVOUT (pixel_clk),
            .CLKIN (pclk_IOCLKBUF),
            .RST_N (enble));
	// ../rtl/reuse/cmos_8_16bit.v:71
	// SDC constraint : (object CLKDIVOUT) (id 1014) (clock cmos1_pclk_16bit) (745 : E:/zhoumian/FPGA/FPGA_GS/FPGA_GSV1/work/CAM_quality_3_6_0/rear_pixels_source/build/CAM1_RAW_E3_3_6_0_20261024_203852_117/constraints/mes50hp.fdc)

    GTP_DFF /* vs_i_reg */ #(
            .GRS_EN("TRUE"), 
            .INIT(1'b0))
        vs_i_reg_vname (
            .Q (vs_i_reg),
            .CLK (pclk),
            .D (vs_i));
    // defparam vs_i_reg_vname.orig_name = vs_i_reg;
	// ../rtl/reuse/cmos_8_16bit.v:47


endmodule
