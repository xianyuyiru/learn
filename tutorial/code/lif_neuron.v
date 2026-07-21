// LIF (Leaky Integrate-and-Fire) Neuron
// Models: dV/dt = I - V/tau,  when V >= threshold -> spike & reset
module lif_neuron (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  input_current,   // input current (integer)
    output reg         spike,           // output spike pulse
    output wire [15:0] V_out            // membrane potential (for debug)
);

    reg [15:0] V;                        // membrane potential
    assign V_out = V;
    localparam THRESHOLD = 100;          // firing threshold
    localparam TAU = 24;                 // leak time constant (RET-only tuned)

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            V     <= 16'd0;
            spike <= 1'b0;
        end else begin
            // Compute next membrane potential
            // V_next = V + I - V/tau
            // Note: integer division for V/tau is intentional (simplified)
            if (V + input_current - (V / TAU) >= THRESHOLD) begin
                V     <= 16'd0;          // reset after spike
                spike <= 1'b1;
            end else begin
                V     <= V + input_current - (V / TAU);
                spike <= 1'b0;
            end
        end
    end

endmodule
