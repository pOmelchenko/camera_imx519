"""Q6A camera connector -> (CCI master DT symbol, CAMSS CSIPHY index)."""
PORTS = {
    "cam1": ("cci0_i2c0", 0),   # J14
    "cam2": ("cci1_i2c0", 2),   # J16
    "cam3": ("cci1_i2c1", 3),   # J7
}
